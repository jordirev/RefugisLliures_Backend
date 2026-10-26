"""
Esquema fisic de `visits.0001` (chunk 4; docs/design/postgres-schema.md §2.10, §2.11, §4.1, §6.3, §7.2):

- app `apps.visits` (`INSTALLED_APPS`), migracio `visits.0001_*` que depen d'`accounts` (FK a `users.users`) i `refuges`;
- `activity.refuge_visits`: PK `id uuid DEFAULT uuidv7()`, `UNIQUE (refuge_id, visit_date)` (`visits_refuge_date_uq`),
  index `(visit_date)`, FK `refuge_visits_refuge_id_fk` CASCADE;
- `activity.refuge_visit_participants`: PK composta `(visit_id, user_uid)` (`participants_pk`, D18), `CHECK num_visitors >= 1`,
  index `(user_uid) INCLUDE (visit_id, num_visitors)`, FK `..._visit_id_fk` i `..._user_uid_fk` CASCADE;
- vista `activity.refuge_visit_totals` (propietat del `migrator`, sense `security_invoker`): `visit_id`, `total_visitors`;
- RLS activada (sense FORCE), politiques i grants de `app` segons §2.10/§2.11/§7.2; `RunSQL` reversibles.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

VISITS, PARTS = 'activity.refuge_visits', 'activity.refuge_visit_participants'
FKS = [
    (VISITS, 'refuge_id', 'refuges.refuges', 'refuge_visits_refuge_id_fk'),
    (PARTS, 'visit_id', 'activity.refuge_visits', 'refuge_visit_participants_visit_id_fk'),
    (PARTS, 'user_uid', 'users.users', 'refuge_visit_participants_user_uid_fk'),
]


def _columns(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _indexes(conn, table):
    """`{nom: definicio}` d'`pg_indexes`."""
    schema, name = table.split('.')
    return dict(fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
                          [schema, name]))


def _index_cols(definition):
    """`(columnes, columnes_include_o_None)` d'un `CREATE INDEX ... (a, b) INCLUDE (c)`."""
    return re.search(r'\((.*?)\)(?: INCLUDE \((.*?)\))?(?: WHERE.*)?$', definition).groups()


def test_l_app_visits_es_a_installed_apps(settings):
    assert 'apps.visits' in settings.INSTALLED_APPS


def test_migracio_0001_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'visits' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts_i_de_refuges():
    """Les FK cap a `users.users` i `refuges.refuges` exigeixen que existeixin (graf aciclic, §6.2)."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = next((k for k in loader.graph.node_map if k[0] == 'visits' and k[1].startswith('0001')), None)
    assert node, 'cal una migracio `visits.0001_*`'
    plan = {app for app, _ in loader.graph.forwards_plan(node)}
    assert {'accounts', 'refuges'} <= plan


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'visits', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_la_migracio_es_reversible(migrator_db):
    """Cada `RunSQL` (FK, RLS, grants, vista) ha de dur `reverse_sql`."""
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'visits' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql, 'la 0001 crea FK, vista, RLS i grants per RunSQL'
    assert all(op.reversible for op in run_sql)


@pytest.mark.parametrize('table', [VISITS, PARTS])
def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row == (True, False, 'migrator'), f'falta la taula {table} o no compleix RLS/propietari'


# ---------- Columnes ----------

def test_columnes_de_refuge_visits(migrator_db):
    c = _columns(migrator_db, VISITS)
    assert set(c) == {'id', 'refuge_id', 'visit_date', 'created_at'}           # sense `total_visitors` (M3)
    assert (c['id'][1], c['id'][2], c['id'][3]) == ('uuid', 'NO', 'uuidv7()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'NO')
    assert (c['visit_date'][1], c['visit_date'][2], c['visit_date'][3]) == ('date', 'NO', None)
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


def test_columnes_de_participants(migrator_db):
    c = _columns(migrator_db, PARTS)
    assert set(c) == {'visit_id', 'user_uid', 'num_visitors', 'created_at'}      # sense `id`
    assert (c['visit_id'][1], c['visit_id'][2]) == ('uuid', 'NO')
    assert (c['user_uid'][1], c['user_uid'][2], c['user_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['num_visitors'][1], c['num_visitors'][2]) == ('int4', 'NO')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


# ---------- Restriccions ----------

def test_pk_de_visits_es_l_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [VISITS])
    assert row == (['id'],)


def test_unique_refuge_data_amb_el_nom_del_disseny(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.conname, (SELECT array_agg(a.attname::text ORDER BY k.ord)
                             FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'u' AND c.conrelid = %s::regclass""", [VISITS])
    assert row == ('visits_refuge_date_uq', ['refuge_id', 'visit_date'])      # fixa M4


def test_pk_composta_visit_id_user_uid_sense_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.conname, (SELECT array_agg(a.attname::text ORDER BY k.ord)
                             FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [PARTS])
    assert row == ('participants_pk', ['visit_id', 'user_uid'])                # D18


def test_check_num_visitors_major_o_igual_que_1(migrator_db):
    defs = [r[0] for r in fetch_all(migrator_db, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                                 "WHERE contype = 'c' AND conrelid = %s::regclass", [PARTS])]
    assert any(re.search(r'num_visitors\s*>=\s*1', d) for d in defs), defs


def _fk(conn, table, column):
    rows = fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])
    return [r for r in rows if r[5] == [column]]


@pytest.mark.parametrize('table,column,target,name', FKS)
def test_fk_real_cascade_diferible_amb_el_nom_del_disseny(migrator_db, table, column, target, name):
    fks = _fk(migrator_db, table, column)
    assert len(fks) == 1, f'falta la FK {table}.{column} (db_constraint=False + RunSQL, §6.3)'
    assert fks[0][:5] == (name, 'c', True, True, target)


# ---------- Index ----------

def test_index_de_visit_date_per_al_job_diari(migrator_db):
    cols = [_index_cols(d) for d in _indexes(migrator_db, VISITS).values()]
    assert ('visit_date', None) in cols, cols


def test_index_unique_refuge_data_cobreix_el_llistat_del_refugi(migrator_db):
    cols = [_index_cols(d)[0] for d in _indexes(migrator_db, VISITS).values()]
    assert 'refuge_id, visit_date' in cols, cols


def test_index_de_user_uid_amb_include_per_a_les_visites_d_un_usuari(migrator_db):
    """B5: `GET /users/{uid}/visits/` i l'esborrat d'usuari no recorren tota la taula."""
    cols = [_index_cols(d) for d in _indexes(migrator_db, PARTS).values()]
    assert any(k == 'user_uid' and inc and {i.strip() for i in inc.split(',')} == {'visit_id', 'num_visitors'}
               for k, inc in cols), cols


def test_cap_index_like_de_django_al_schema_activity(migrator_db):
    rows = fetch_all(migrator_db, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'activity'")
    assert [n for n, d in rows if n.endswith('_like') or 'pattern_ops' in d] == []


# ---------- Vista ----------

def test_la_vista_de_totals_es_del_migrator_i_sense_security_invoker(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.relkind, pg_get_userbyid(c.relowner), coalesce(c.reloptions::text, '')
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'activity' AND c.relname = 'refuge_visit_totals'""")
    assert row is not None, 'falta la vista activity.refuge_visit_totals'
    assert row[0] == 'v' and row[1] == 'migrator'
    assert 'security_invoker' not in row[2]                                       # §4.1: s'executa com a propietari


def test_columnes_de_la_vista(migrator_db):
    c = _columns(migrator_db, 'activity.refuge_visit_totals')
    assert set(c) == {'visit_id', 'total_visitors'}
    assert c['visit_id'][1] == 'uuid' and c['total_visitors'][1] == 'int4'        # `sum(...)::integer`


# ---------- RLS i grants ----------

def _policies(conn, table):
    schema, name = table.split('.')
    return fetch_all(conn, "SELECT policyname, cmd, roles::text FROM pg_policies "
                           "WHERE schemaname = %s AND tablename = %s ORDER BY policyname", [schema, name])


def test_politiques_de_visits(migrator_db):
    rows = _policies(migrator_db, VISITS)
    assert [(r[0], r[1]) for r in rows] == [('visits_delete', 'DELETE'), ('visits_insert', 'INSERT'),
                                            ('visits_select', 'SELECT')]
    assert all('app' in r[2] for r in rows)


def test_politiques_de_participants(migrator_db):
    rows = _policies(migrator_db, PARTS)
    assert [(r[0], r[1]) for r in rows] == [('vparts_delete', 'DELETE'), ('vparts_insert', 'INSERT'),
                                            ('vparts_select', 'SELECT'), ('vparts_update', 'UPDATE')]
    assert all('app' in r[2] for r in rows)


@pytest.mark.parametrize('table,expected', [
    (VISITS, {'SELECT', 'INSERT', 'DELETE'}),                       # sense UPDATE; el DELETE nomes el cobreix `{SYS}`
    (PARTS, {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('activity.refuge_visit_totals', {'SELECT'}),
])
def test_matriu_de_grants_d_app(app_db, table, expected):
    """§7.2: minim privilegi. `app` mai te TRUNCATE, REFERENCES ni TRIGGER."""
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == expected
