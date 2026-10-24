"""
Context de RLS per transacció i helpers de polítiques (docs/design/postgres-schema.md §2, §7.3, §7.4).

El context (`app.uid`, `app.is_admin`, `app.is_system`) viu **sempre** a la transacció: `set_config(..., true)`.
Així no es filtra a altres clients quan el pooler de Neon (PgBouncer, mode transacció) reutilitza la connexió.
Tots els valors van com a paràmetres; mai es concatena SQL.
"""
import re
from contextlib import contextmanager

from django.db import connections, transaction

DEFAULT_ALIAS = 'default'

# Sentència única que fixa el context (és la que també executa el hook de `APIView`).
SET_CONTEXT_SQL = (
    "SELECT set_config('app.uid', %s, true), "
    "set_config('app.is_admin', %s, true), "
    "set_config('app.is_system', 'false', true)"
)
_SET_RAW_SQL = (
    "SELECT set_config('app.uid', %s, true), "
    "set_config('app.is_admin', %s, true), "
    "set_config('app.is_system', %s, true)"
)
_SET_SYSTEM_SQL = "SELECT set_config('app.is_system', %s, true)"
_READ_SQL = (
    "SELECT COALESCE(current_setting('app.uid', true), ''), "
    "COALESCE(current_setting('app.is_admin', true), ''), "
    "COALESCE(current_setting('app.is_system', true), '')"
)


def bool_text(value):
    return 'true' if value else 'false'


def apply_context(conn, uid, is_admin):
    """Fixa `app.uid`/`app.is_admin` i reinicia `app.is_system` a la transacció en curs (una sola sentència)."""
    with conn.cursor() as cur:
        cur.execute(SET_CONTEXT_SQL, [uid or '', bool_text(is_admin)])


def _read_context(conn):
    with conn.cursor() as cur:
        cur.execute(_READ_SQL)
        return cur.fetchone()


def _restore(conn, previous):
    # Si la transacció ja és inservible (error no capturat) no es pot executar res: el rollback ja
    # descarta els valors locals.
    if conn.needs_rollback:
        return
    with conn.cursor() as cur:
        cur.execute(_SET_RAW_SQL, list(previous))


@contextmanager
def rls_context(uid=None, is_admin=False, system=False, using=DEFAULT_ALIAS):
    """
    Obre una transacció (`transaction.atomic`) amb el context de RLS indicat.

    Si ja hi ha una transacció, el context anterior es restaura en sortir (un context intern no pot deixar
    privilegis a l'extern). Fora de les peticions HTTP (comandes, jobs, tests) és l'equivalent del hook de
    `APIView.initial()`.
    """
    conn = connections[using]
    nested = conn.in_atomic_block
    previous = _read_context(conn) if nested else None
    try:
        with transaction.atomic(using=using):
            with conn.cursor() as cur:
                cur.execute(_SET_RAW_SQL, [uid or '', bool_text(is_admin), bool_text(system)])
            yield
    finally:
        if previous is not None:
            _restore(conn, previous)


@contextmanager
def system_context(using=DEFAULT_ALIAS):
    """
    Activa `app.is_system` a la transacció en curs (o en obre una) i el restableix en sortir.

    Només per a blocs curts i revisats (jobs, efectes creuats de moderació; §7.4).
    """
    conn = connections[using]
    previous = None
    try:
        with transaction.atomic(using=using):
            with conn.cursor() as cur:
                cur.execute(_READ_SQL)
                previous = cur.fetchone()[2]
                cur.execute(_SET_SYSTEM_SQL, ['true'])
            yield
    finally:
        if previous is not None:
            if not conn.needs_rollback and conn.in_atomic_block:
                with conn.cursor() as cur:
                    cur.execute(_SET_SYSTEM_SQL, [previous])


# ---------- Polítiques ----------

MACROS = {
    'U': '(SELECT core.uid())',
    'ADM': '(SELECT core.is_admin())',
    'SYS': '(SELECT core.is_system())',
}
_MACRO_RE = re.compile(r'\{([A-Za-z_]+)\}')
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$')
_COMMANDS = ('SELECT', 'INSERT', 'UPDATE', 'DELETE')


def expand_macros(expression):
    """Expandeix `{U}`, `{ADM}` i `{SYS}` literalment (§2). Una macro desconeguda és un error."""
    def repl(match):
        name = match.group(1)
        if name not in MACROS:
            raise ValueError(f"Macro de RLS desconeguda: {{{name}}}")
        return MACROS[name]
    return _MACRO_RE.sub(repl, expression)


def _check_ident(value, what):
    if not isinstance(value, str) or not _IDENT_RE.match(value):
        raise ValueError(f"{what} no vàlid: {value!r}")
    return value


def create_policy_sql(name, table, cmd, using=None, with_check=None, role='app'):
    """
    SQL d'una política `PERMISSIVE` (`CREATE POLICY name ON table FOR cmd TO role ...`).

    `SELECT`/`DELETE` només admeten `using`; `INSERT` només `with_check`; `UPDATE` ambdós.
    """
    _check_ident(name, 'Nom de política')
    _check_ident(table, 'Nom de taula')
    _check_ident(role, 'Rol')
    cmd = (cmd or '').upper()
    if cmd not in _COMMANDS:
        raise ValueError(f"Ordre de política no vàlida: {cmd!r}")
    if cmd == 'INSERT' and using is not None:
        raise ValueError('Una política INSERT no admet USING')
    if cmd in ('SELECT', 'DELETE') and with_check is not None:
        raise ValueError(f'Una política {cmd} no admet WITH CHECK')
    if cmd == 'INSERT' and with_check is None:
        raise ValueError('Una política INSERT necessita WITH CHECK')
    if cmd in ('SELECT', 'DELETE') and using is None:
        raise ValueError(f'Una política {cmd} necessita USING')
    if cmd == 'UPDATE' and using is None and with_check is None:
        raise ValueError('Cal alguna expressió (USING o WITH CHECK)')

    sql = f'CREATE POLICY {name} ON {table} FOR {cmd} TO {role}'
    if using is not None:
        sql += f' USING ({expand_macros(using)})'
    if with_check is not None:
        sql += f' WITH CHECK ({expand_macros(with_check)})'
    return sql


def drop_policy_sql(name, table):
    """SQL per esborrar una política (idempotent)."""
    _check_ident(name, 'Nom de política')
    _check_ident(table, 'Nom de taula')
    return f'DROP POLICY IF EXISTS {name} ON {table}'
