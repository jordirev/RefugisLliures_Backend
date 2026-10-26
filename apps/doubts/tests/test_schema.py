"""
Esquema físic de `doubts.0001` (chunk 6; docs/design/postgres-schema.md §2.16, §2.17, §6.3, §7.2):
taules `activity.doubts` i `activity.answers`, PK UUID v7 de la BD, `CHECK` del missatge, `UNIQUE (doubt_id, id)` +
FK composta del pare al mateix dubte (`RunSQL`, `ON DELETE CASCADE`), `answers_not_self_parent_ck`, índexs, FK reals
amb `ON DELETE CASCADE`, RLS (polítiques `doubts_*` / `answers_*`) i grants `SELECT, INSERT, DELETE`.

La migració és `apps/doubts/migrations/0001_initial.py` i depèn d'`accounts` (`users.users`) i `refuges`
(`refuges.refuges`); el schema `activity` el crea `core`.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLES = ('activity.doubts', 'activity.answers')


def _columns(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _indexes(conn, table):
    """`{nom: (unique, 'cols amb ordre')}` a partir de `pg_get_indexdef` (p. ex. `refuge_id, created_at DESC, id DESC`)."""
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'activity' AND tablename = %s",
                     [table.split('.')[1]])
    out = {}
    for name, definition in rows:
        cols = re.search(r'\((.*)\)(?: WHERE.*)?$', definition).group(1)
        out[name] = ('UNIQUE' in definition, cols)
    return out


def _fks(conn, table):
    """Totes les FK de la taula: `[(nom, confdeltype, deferrable, deferred, taula destí, columnes, columnes destí, match)]`."""
    return fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum),
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.confkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.attnum),
               c.confmatchtype
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])


def _constraints(conn, table, kind):
    return fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                           "WHERE contype = %s AND conrelid = %s::regclass", [kind, table])


# ---------- migració ----------

def test_migracio_0001_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'doubts' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts_i_refuges():
    """Les FK cap a `users.users` i `refuges.refuges` exigeixen que existeixin (`accounts.0001`, `refuges.0001`)."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'doubts' and k[1].startswith('0001')]
    assert node, 'cal una migracio `doubts.0001_*`'
    plan = set(loader.graph.forwards_plan(node[0]))
    assert any(app == 'accounts' for app, _ in plan) and any(app == 'refuges' for app, _ in plan)


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'doubts', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_la_migracio_es_reversible():
    """Cada `RunSQL` ha de dur `reverse_sql` (FK, RLS, grants)."""
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'doubts' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql, 'la 0001 crea FK, RLS i grants per RunSQL'
    assert all(op.reversible for op in run_sql)


def test_cap_index_like_de_django(migrator_db):
    """§6.5: cap índex `*_like` a les taules de dubtes (les PK són `uuid`, no n'han de sortir)."""
    rows = fetch_all(migrator_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'activity' "
                                  "AND tablename IN ('doubts', 'answers') AND indexname LIKE %s", ['%\\_like'])
    assert rows == []
    assert fetch_one(migrator_db, "SELECT count(*) FROM pg_tables WHERE schemaname = 'activity' "
                                  "AND tablename IN ('doubts', 'answers')") == (2,)


# ---------- taules ----------

@pytest.mark.parametrize('table', TABLES)
def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row == (True, False, 'migrator'), f'falta la taula {table} o no compleix RLS/propietari'


def test_columnes_de_doubts(migrator_db):
    c = _columns(migrator_db, 'activity.doubts')
    assert set(c) == {'id', 'refuge_id', 'creator_uid', 'message', 'created_at'}      # sense answers_count (§4)
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'NO')
    assert (c['creator_uid'][1], c['creator_uid'][2], c['creator_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['message'][1], c['message'][2]) == ('text', 'NO')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


def test_columnes_d_answers(migrator_db):
    c = _columns(migrator_db, 'activity.answers')
    assert set(c) == {'id', 'doubt_id', 'creator_uid', 'parent_answer_id', 'message', 'created_at'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['doubt_id'][1], c['doubt_id'][2]) == ('uuid', 'NO')
    assert (c['creator_uid'][1], c['creator_uid'][2], c['creator_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['parent_answer_id'][1], c['parent_answer_id'][2]) == ('uuid', 'YES')    # NULL = resposta directa
    assert (c['message'][1], c['message'][2]) == ('text', 'NO')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


@pytest.mark.parametrize('table', TABLES)
def test_pk_uuid_a_id(migrator_db, table):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [table])
    assert row == (['id'],)


# ---------- CHECK ----------

@pytest.mark.parametrize('table', TABLES)
def test_check_del_missatge_no_buit_i_com_a_molt_2000(migrator_db, table):
    checks = [d for _, d in _constraints(migrator_db, table, 'c') if 'message' in d]
    assert len(checks) == 1, checks
    definition = checks[0]
    assert 'btrim' in definition and '2000' in definition and 'char_length' in definition


def test_answers_not_self_parent_ck(migrator_db):
    checks = dict(_constraints(migrator_db, 'activity.answers', 'c'))
    assert 'answers_not_self_parent_ck' in checks
    assert 'parent_answer_id' in checks['answers_not_self_parent_ck']


# ---------- UNIQUE i FK ----------

def test_answers_doubt_id_uq_unique_doubt_id_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.conname, (SELECT array_agg(a.attname::text ORDER BY k.ord)
                             FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'u' AND c.conrelid = 'activity.answers'::regclass""")
    assert row == ('answers_doubt_id_uq', ['doubt_id', 'id'])


@pytest.mark.parametrize('table,column,target', [
    ('activity.doubts', 'refuge_id', 'refuges.refuges'),
    ('activity.doubts', 'creator_uid', 'users.users'),
    ('activity.answers', 'doubt_id', 'activity.doubts'),
    ('activity.answers', 'creator_uid', 'users.users'),
])
def test_fk_real_cascade_diferible_amb_el_nom_del_disseny(migrator_db, table, column, target):
    fks = [f for f in _fks(migrator_db, table) if f[5] == [column]]
    assert len(fks) == 1, f'falta la FK {table}.{column} (db_constraint=False + RunSQL, §6.3)'
    name, deltype, deferrable, deferred, ref, _, _, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, target)
    assert name == f'{table.split(".")[1]}_{column}_fk'


def test_answers_parent_same_doubt_fk_composta(migrator_db):
    fks = [f for f in _fks(migrator_db, 'activity.answers') if f[5] == ['doubt_id', 'parent_answer_id']]
    assert len(fks) == 1, 'falta la FK composta (doubt_id, parent_answer_id) -> answers (doubt_id, id) (RunSQL, §2.17)'
    name, deltype, deferrable, deferred, ref, _, ref_cols, match = fks[0]
    assert name == 'answers_parent_same_doubt_fk'
    assert (ref, ref_cols) == ('activity.answers', ['doubt_id', 'id'])
    assert deltype == 'c'                               # ON DELETE CASCADE: s'esborra el subarbre
    assert match == 's'                                 # MATCH SIMPLE: parent_answer_id NULL no es comprova


def test_nomes_hi_ha_les_fk_del_disseny(migrator_db):
    assert len(_fks(migrator_db, 'activity.doubts')) == 2
    assert len(_fks(migrator_db, 'activity.answers')) == 3


# ---------- índexs ----------

def test_indexs_de_doubts(migrator_db):
    cols = {c for _, c in _indexes(migrator_db, 'activity.doubts').values()}
    assert 'refuge_id, created_at DESC, id DESC' in cols, cols        # llista d'un refugi (keyset) + FK
    assert 'creator_uid' in cols, cols                                # esborrat d'usuari + FK
    assert 'id' in cols


def test_indexs_d_answers(migrator_db):
    idx = _indexes(migrator_db, 'activity.answers')
    cols = {c for _, c in idx.values()}
    assert 'doubt_id, created_at, id' in cols, idx                    # respostes d'un dubte ASC + answers_count
    assert 'doubt_id, parent_answer_id' in cols, idx                  # cascada de la FK composta
    assert 'creator_uid' in cols, idx                                 # esborrat d'usuari + FK
    assert any(u and c == 'doubt_id, id' for u, c in idx.values()), idx   # UNIQUE (doubt_id, id)


# ---------- RLS i grants ----------

@pytest.mark.parametrize('table,prefix', [('activity.doubts', 'doubts'), ('activity.answers', 'answers')])
def test_politiques_rls_noms_i_ordres(migrator_db, table, prefix):
    schema, name = table.split('.')
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = %s AND tablename = %s", [schema, name])
    assert {(r[0], r[1]) for r in rows} == {(f'{prefix}_select', 'SELECT'), (f'{prefix}_insert', 'INSERT'),
                                            (f'{prefix}_delete', 'DELETE')}       # sense UPDATE
    assert all('app' in r[2] for r in rows)


@pytest.mark.parametrize('table', TABLES)
def test_matriu_de_grants_d_app_select_insert_delete(app_db, table):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == {'SELECT', 'INSERT', 'DELETE'}
