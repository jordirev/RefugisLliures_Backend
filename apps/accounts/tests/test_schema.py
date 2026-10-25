"""
Esquema fisic de `accounts.0002` (chunk 3; docs/design/postgres-schema.md §2.3, §2.4, §6.3, §7.2):
taules de preferits i visitats, PK composta, indexs, FK reals amb ON DELETE CASCADE, RLS i grants.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLES = {
    'users.user_favourite_refuges': ('favourites_pk', 'user_favourite_refuges'),
    'users.user_visited_refuges': ('visited_pk', 'user_visited_refuges'),
}


def _columns(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _index_columns(conn, table):
    """`{nom: (unique, 'cols amb ordre')}` a partir de `pg_get_indexdef` (p. ex. `user_uid, created_at DESC, refuge_id`)."""
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'users' AND tablename = %s",
                     [table.split('.')[1]])
    out = {}
    for name, definition in rows:
        cols = re.search(r'\((.*)\)(?: WHERE.*)?$', definition).group(1)
        out[name] = ('UNIQUE' in definition, cols)
    return out


def test_migracio_0002_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'accounts' "
                                  "AND name LIKE '0002%%'")[0] == 1


def test_la_migracio_0002_depen_de_refuges():
    """Les FK cap a `refuges.refuges` exigeixen que la taula existeixi (`refuges.0001`)."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'accounts' and k[1].startswith('0002')]
    assert node, 'cal una migracio `accounts.0002_*`'
    assert any(app == 'refuges' for app, _ in loader.graph.node_map[node[0]].parents) or \
        ('refuges', '0001_initial') in loader.graph.forwards_plan(node[0])


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'accounts', 'refuges', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


@pytest.mark.parametrize('table', TABLES)
def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row == (True, False, 'migrator'), f'falta la taula {table} o no compleix RLS/propietari'


@pytest.mark.parametrize('table', TABLES)
def test_columnes(migrator_db, table):
    c = _columns(migrator_db, table)
    assert set(c) == {'user_uid', 'refuge_id', 'created_at'}               # sense `id`
    assert (c['user_uid'][1], c['user_uid'][2], c['user_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'NO')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


@pytest.mark.parametrize('table,pk', [(t, v[0]) for t, v in TABLES.items()])
def test_pk_composta_user_uid_refuge_id(migrator_db, table, pk):
    row = fetch_one(migrator_db, """
        SELECT c.conname, (SELECT array_agg(a.attname::text ORDER BY k.ord)
                             FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [table])
    assert row == (pk, ['user_uid', 'refuge_id'])


def test_index_keyset_i_index_de_refugi_de_preferits(migrator_db):
    idx = _index_columns(migrator_db, 'users.user_favourite_refuges')
    cols = {c for _, c in idx.values()}
    assert 'user_uid, created_at DESC, refuge_id' in cols, idx            # llista paginada per cursor
    assert 'refuge_id' in cols, idx                                       # FK/cascada en esborrar un refugi
    assert 'user_uid, refuge_id' in cols                                  # la PK


def test_index_keyset_i_index_de_visitors_de_visitats(migrator_db):
    idx = _index_columns(migrator_db, 'users.user_visited_refuges')
    cols = {c for _, c in idx.values()}
    assert 'user_uid, created_at DESC, refuge_id' in cols, idx
    assert 'refuge_id, user_uid' in cols, idx                             # llista `visitors` del refugi
    assert 'user_uid, refuge_id' in cols


def _fk(conn, table, column):
    rows = fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])
    return [r for r in rows if r[5] == [column]]


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('column,target', [('user_uid', 'users.users'), ('refuge_id', 'refuges.refuges')])
def test_fk_real_cascade_diferible_amb_el_nom_del_disseny(migrator_db, table, column, target):
    fks = _fk(migrator_db, table, column)
    assert len(fks) == 1, f'falta la FK {table}.{column} (db_constraint=False + RunSQL, §6.3)'
    name, deltype, deferrable, deferred, ref, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, target)
    assert name == f'{TABLES[table][1]}_{column}_fk'


@pytest.mark.parametrize('table', TABLES)
def test_politiques_rls_noms_i_ordres(migrator_db, table):
    schema, name = table.split('.')
    rows = fetch_all(migrator_db, "SELECT cmd, roles::text FROM pg_policies WHERE schemaname = %s AND tablename = %s",
                     [schema, name])
    assert sorted(r[0] for r in rows) == ['DELETE', 'INSERT', 'SELECT']    # sense UPDATE
    assert all('app' in r[1] for r in rows)


@pytest.mark.parametrize('table', TABLES)
def test_matriu_de_grants_d_app_select_insert_delete(app_db, table):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == {'SELECT', 'INSERT', 'DELETE'}


def test_la_migracio_0002_es_reversible(migrator_db):
    """Cada `RunSQL` ha de dur `reverse_sql` (el graf de migracions es pot desfer)."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'accounts' and k[1].startswith('0002'))
    migration = loader.get_migration(*key)
    from django.db.migrations.operations.special import RunSQL
    run_sql = [op for op in migration.operations if isinstance(op, RunSQL)]
    assert run_sql, 'la 0002 crea FK, RLS i grants per RunSQL'
    assert all(op.reversible for op in run_sql)
