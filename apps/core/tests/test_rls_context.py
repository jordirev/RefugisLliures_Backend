"""`rls_context` / `system_context` (§7.3-7.4): el context és local a la transacció i es restaura en sortir."""
import pytest
from django.db import transaction

from apps.core.testing import fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.rls]

CTX = 'SELECT core.uid(), core.is_admin(), core.is_system()'


@pytest.fixture
def ctx():
    from apps.core.rls import rls_context, system_context
    return rls_context, system_context


def test_rls_context_fixa_uid_i_admin(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(uid='u1', is_admin=True):
        assert fetch_one(app_db, CTX) == ('u1', True, False)


def test_rls_context_per_defecte_es_anonim(app_db, ctx):
    rls_context, _ = ctx
    with rls_context():
        assert fetch_one(app_db, CTX) == (None, False, False)


def test_rls_context_system(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(system=True):
        assert fetch_one(app_db, CTX) == (None, False, True)


def test_rls_context_obre_una_transaccio(app_db, ctx):
    rls_context, _ = ctx
    assert not app_db.in_atomic_block
    with rls_context(uid='u1'):
        assert app_db.in_atomic_block
    assert not app_db.in_atomic_block


def test_el_context_mor_en_acabar_la_transaccio(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(uid='u1', is_admin=True, system=True):
        pass
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_despres_del_context_current_setting_pot_ser_buit_pero_uid_es_null(app_db, ctx):
    """Cas del pooler: en reutilitzar la connexió current_setting retorna '' (no NULL)."""
    rls_context, _ = ctx
    with rls_context(uid='u1', is_admin=True):
        pass
    raw = fetch_one(app_db, "SELECT current_setting('app.uid', true), current_setting('app.is_admin', true)")
    assert raw[0] in (None, '') and raw[1] in (None, '', 'false')
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_setting_buit_amb_set_config_de_sessio_es_null(app_db):
    with app_db.cursor() as cur:
        cur.execute("SELECT set_config('app.uid', '', false), set_config('app.is_admin', '', false)")
        cur.execute(CTX)
        assert cur.fetchone() == (None, False, False)


def test_set_config_local_no_es_filtra_a_la_transaccio_seguent(app_db):
    with transaction.atomic():
        with app_db.cursor() as cur:
            cur.execute("SELECT set_config('app.uid', 'filtrat', true), set_config('app.is_admin', 'true', true)")
            cur.execute(CTX)
            assert cur.fetchone() == ('filtrat', True, False)
    with transaction.atomic():
        assert fetch_one(app_db, CTX) == (None, False, False)
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_dues_transaccions_seqüencials_amb_contextos_diferents(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(uid='u1', is_admin=True):
        assert fetch_one(app_db, CTX)[:2] == ('u1', True)
    with rls_context(uid='u2'):
        assert fetch_one(app_db, CTX)[:2] == ('u2', False)
    with rls_context():
        assert fetch_one(app_db, CTX)[:2] == (None, False)


def test_uid_amb_cometes_es_parametritza(app_db, ctx):
    rls_context, _ = ctx
    raro = "u'; DROP SCHEMA core CASCADE;--"
    with rls_context(uid=raro):
        assert fetch_one(app_db, CTX)[0] == raro


def test_excepcio_dins_del_context_es_propaga_i_desfa_la_transaccio(app_db, ctx):
    rls_context, _ = ctx
    with app_db.cursor() as cur:
        cur.execute('CREATE TEMP TABLE zz_rb (i int)')
    try:
        with pytest.raises(ValueError):
            with rls_context(uid='u1', is_admin=True):
                with app_db.cursor() as cur:
                    cur.execute('INSERT INTO zz_rb VALUES (1)')
                raise ValueError('boom')
        assert fetch_one(app_db, 'SELECT count(*) FROM zz_rb')[0] == 0
        assert fetch_one(app_db, CTX) == (None, False, False)
    finally:
        with app_db.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS zz_rb')


def test_commit_normal_conserva_les_dades_pero_no_el_context(app_db, ctx):
    rls_context, _ = ctx
    with app_db.cursor() as cur:
        cur.execute('CREATE TEMP TABLE zz_ok (i int)')
    try:
        with rls_context(uid='u1'):
            with app_db.cursor() as cur:
                cur.execute('INSERT INTO zz_ok VALUES (1)')
        assert fetch_one(app_db, 'SELECT count(*) FROM zz_ok')[0] == 1
        assert fetch_one(app_db, CTX)[0] is None
    finally:
        with app_db.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS zz_ok')


# ---------- system_context ----------

def test_system_context_independent(app_db, ctx):
    _, system_context = ctx
    with system_context():
        assert fetch_one(app_db, CTX) == (None, False, True)
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_system_context_dins_de_rls_context_conserva_uid_i_es_restableix(app_db, ctx):
    rls_context, system_context = ctx
    with rls_context(uid='u1'):
        with system_context():
            assert fetch_one(app_db, CTX) == ('u1', False, True)
        assert fetch_one(app_db, CTX) == ('u1', False, False)   # restablert a 'false' en sortir


def test_system_context_restableix_encara_que_hi_hagi_excepcio(app_db, ctx):
    rls_context, system_context = ctx
    with rls_context(uid='u1'):
        with pytest.raises(RuntimeError):
            with system_context():
                raise RuntimeError('x')
        assert fetch_one(app_db, CTX) == ('u1', False, False)


def test_system_context_amb_rollback_total(app_db, ctx):
    rls_context, system_context = ctx
    with pytest.raises(RuntimeError):
        with rls_context(uid='u1'):
            with system_context():
                raise RuntimeError('x')
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_system_context_restaura_el_valor_anterior_si_ja_era_true(app_db, ctx):
    rls_context, system_context = ctx
    with rls_context(system=True):
        with system_context():
            assert fetch_one(app_db, CTX)[2] is True
        assert fetch_one(app_db, CTX)[2] is True


# ---------- imbricació (un context intern no pot deixar privilegis a l'extern) ----------

def test_rls_context_imbricat_restaura_l_extern(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(uid='u1'):
        with rls_context(uid='u2', is_admin=True):
            assert fetch_one(app_db, CTX) == ('u2', True, False)
        assert fetch_one(app_db, CTX) == ('u1', False, False), "l'admin de l'intern no pot sobreviure"
    assert fetch_one(app_db, CTX) == (None, False, False)


def test_rls_context_imbricat_amb_excepcio_restaura_l_extern(app_db, ctx):
    rls_context, _ = ctx
    with rls_context(uid='u1'):
        with pytest.raises(ValueError):
            with rls_context(uid='u2', is_admin=True):
                raise ValueError
        assert fetch_one(app_db, CTX) == ('u1', False, False)


# ---------- integració amb polítiques generades pel helper ----------

@pytest.fixture
def taula_amb_rls(migrator_db):
    """Taula `core.zz_rls_probe` amb polítiques generades pel helper (la crea el migrator i s'esborra al final)."""
    from apps.core.rls import create_policy_sql
    with migrator_db.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS core.zz_rls_probe')
        cur.execute('CREATE TABLE core.zz_rls_probe (id int PRIMARY KEY, owner_uid text NOT NULL)')
        cur.execute("INSERT INTO core.zz_rls_probe VALUES (1, 'u1'), (2, 'u2')")
        cur.execute('ALTER TABLE core.zz_rls_probe ENABLE ROW LEVEL SECURITY')
        cur.execute('GRANT SELECT, INSERT, DELETE ON core.zz_rls_probe TO app')
        cur.execute(create_policy_sql('zz_sel', 'core.zz_rls_probe', 'SELECT', using='owner_uid = {U} OR {ADM} OR {SYS}'))
        cur.execute(create_policy_sql('zz_ins', 'core.zz_rls_probe', 'INSERT', with_check='owner_uid = {U} OR {SYS}'))
    try:
        yield 'core.zz_rls_probe'
    finally:
        with migrator_db.cursor() as cur:
            cur.execute('DROP TABLE IF EXISTS core.zz_rls_probe')


def _ids(conn, tbl):
    with conn.cursor() as cur:
        cur.execute(f'SELECT id FROM {tbl} ORDER BY id')
        return [r[0] for r in cur.fetchall()]


def test_politiques_del_helper_filtren_segons_el_context(app_db, taula_amb_rls, ctx):
    rls_context, system_context = ctx
    t = taula_amb_rls
    assert _ids(app_db, t) == [], "fail-closed: sense context no es veu res"
    with rls_context():
        assert _ids(app_db, t) == []
    with rls_context(uid='u1'):
        assert _ids(app_db, t) == [1]
    with rls_context(uid='u2'):
        assert _ids(app_db, t) == [2]
    with rls_context(uid='u3'):
        assert _ids(app_db, t) == []
    with rls_context(uid='u3', is_admin=True):
        assert _ids(app_db, t) == [1, 2]
    with rls_context(uid='u3'):
        with system_context():
            assert _ids(app_db, t) == [1, 2]
        assert _ids(app_db, t) == []
    assert _ids(app_db, t) == []


def test_politica_insert_with_check_sota_rol_app(app_db, taula_amb_rls, ctx):
    from django.db.utils import ProgrammingError
    rls_context, _ = ctx
    t = taula_amb_rls
    with rls_context(uid='u1'):
        with app_db.cursor() as cur:
            cur.execute(f"INSERT INTO {t} VALUES (10, 'u1')")
    with pytest.raises(ProgrammingError):          # new row violates row-level security policy
        with rls_context(uid='u1', is_admin=True):  # {ADM} no autoritza l'INSERT en aquesta política
            with app_db.cursor() as cur:
                cur.execute(f"INSERT INTO {t} VALUES (11, 'u2')")
    with rls_context(uid='u1'):
        assert _ids(app_db, t) == [1, 10]
