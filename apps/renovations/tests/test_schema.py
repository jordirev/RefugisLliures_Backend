"""
Esquema físic de `renovations.0001` (chunk 5; docs/design/postgres-schema.md §2.12, §2.12.1, §2.13, §2.14, §6.3, §7.2):
taules `activity.renovations`, `renovation_group_links`, `renovation_participants`, `renovation_expelled`, PK, FK reals
amb el seu ON DELETE, CHECK, EXCLUDE de solapaments, índexs, funcions i *triggers*, RLS (sense FORCE) i grants d'`app`.

Contracte de la migració `apps/renovations/migrations/0001_initial.py`:
- depèn d'`accounts` i `refuges`; crea FK, RLS, grants, funcions i *triggers* amb `RunSQL` reversible (`reverse_sql`);
- extensió `btree_gist` (bootstrap §1.3) necessària per a l'`EXCLUDE`.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

REN, LNK, PAR, EXP = ('activity.renovations', 'activity.renovation_group_links', 'activity.renovation_participants',
                      'activity.renovation_expelled')
TABLES = [REN, LNK, PAR, EXP]


def _columns(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _indexes(conn, table):
    """`{nom: (unique, columnes, predicat | None, mètode)}` a partir de `pg_indexes`."""
    schema, name = table.split('.')
    out = {}
    for iname, definition in fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s "
                                             "AND tablename = %s", [schema, name]):
        m = re.search(r'USING (\w+) \((.*?)\)(?: WHERE (.*))?$', definition)
        out[iname] = ('UNIQUE' in definition, m.group(2), m.group(3), m.group(1))
    return out


def _constraints(conn, table, kind):
    return {r[0]: r[1] for r in fetch_all(conn, """
        SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass AND contype = %s""",
                                          [table, kind])}


# ----------------------------------------------- migració -----------------------------------------------

def test_migracio_0001_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'renovations' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts_i_refuges():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'renovations' and k[1].startswith('0001')]
    assert node, 'cal una migracio `renovations.0001_*`'
    plan = {app for app, _ in loader.graph.forwards_plan(node[0])}
    assert {'accounts', 'refuges'} <= plan


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'renovations', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_la_migracio_es_reversible():
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'renovations' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql, 'la 0001 crea FK, RLS, grants, funcions i triggers per RunSQL'
    assert all(op.reversible for op in run_sql)


def test_extensio_btree_gist_instal_lada(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM pg_extension WHERE extname = 'btree_gist'")[0] == 1


# ----------------------------------------------- taules, RLS, propietari -----------------------------------------------

@pytest.mark.parametrize('table', TABLES)
def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row == (True, False, 'migrator'), f'falta la taula {table} o no compleix RLS/propietari'


# ----------------------------------------------- columnes -----------------------------------------------

def test_columnes_de_renovations(migrator_db):
    c = _columns(migrator_db, REN)
    assert set(c) == {'id', 'refuge_id', 'creator_uid', 'ini_date', 'fin_date', 'description', 'materials_needed',
                      'created_at'}                                   # `group_link` NO hi és (taula pròpia, §2.12.1)
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and 'uuidv7()' in c['id'][3]
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'NO')
    assert (c['creator_uid'][1], c['creator_uid'][2], c['creator_uid'][4]) == ('varchar', 'YES', 128)
    assert (c['ini_date'][1], c['ini_date'][2]) == ('date', 'NO')
    assert (c['fin_date'][1], c['fin_date'][2]) == ('date', 'NO')
    assert (c['description'][1], c['description'][2]) == ('text', 'NO')
    assert (c['materials_needed'][1], c['materials_needed'][2]) == ('text', 'YES')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO')
    assert c['created_at'][3].lower().startswith('now()')


def test_columnes_de_group_links(migrator_db):
    c = _columns(migrator_db, LNK)
    assert set(c) == {'renovation_id', 'group_link'}
    assert (c['renovation_id'][1], c['renovation_id'][2]) == ('uuid', 'NO')
    assert (c['group_link'][1], c['group_link'][2]) == ('text', 'NO')


@pytest.mark.parametrize('table,stamp', [(PAR, 'created_at'), (EXP, 'expelled_at')])
def test_columnes_de_participants_i_expulsats(migrator_db, table, stamp):
    c = _columns(migrator_db, table)
    assert set(c) == {'renovation_id', 'user_uid', stamp}              # sense `id`
    assert (c['renovation_id'][1], c['renovation_id'][2]) == ('uuid', 'NO')
    assert (c['user_uid'][1], c['user_uid'][2], c['user_uid'][4]) == ('varchar', 'NO', 128)
    assert (c[stamp][1], c[stamp][2]) == ('timestamptz', 'NO') and c[stamp][3].lower().startswith('now()')


# ----------------------------------------------- PK -----------------------------------------------

@pytest.mark.parametrize('table,cols', [(REN, ['id']), (LNK, ['renovation_id'])])
def test_pk_simple(migrator_db, table, cols):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text ORDER BY k.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [table])
    assert row[0] == cols


@pytest.mark.parametrize('table,name', [(PAR, 'renovation_participants_pk'), (EXP, 'renovation_expelled_pk')])
def test_pk_composta_renovation_user(migrator_db, table, name):
    row = fetch_one(migrator_db, """
        SELECT c.conname, (SELECT array_agg(a.attname::text ORDER BY k.ord)
                             FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [table])
    assert row == (name, ['renovation_id', 'user_uid'])


# ----------------------------------------------- FK (ON DELETE reals, §6.3) -----------------------------------------------

FKS = [
    (REN, 'refuge_id', 'refuges.refuges', 'c'),
    (REN, 'creator_uid', 'users.users', 'n'),                          # SET NULL: reformes passades anònimes
    (LNK, 'renovation_id', 'activity.renovations', 'c'),
    (PAR, 'renovation_id', 'activity.renovations', 'c'),
    (PAR, 'user_uid', 'users.users', 'c'),
    (EXP, 'renovation_id', 'activity.renovations', 'c'),
    (EXP, 'user_uid', 'users.users', 'c'),
]


@pytest.mark.parametrize('table,column,target,deltype', FKS)
def test_fk_real_amb_el_seu_on_delete(migrator_db, table, column, target, deltype):
    rows = fetch_all(migrator_db, """
        SELECT c.confdeltype, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])
    fks = [r for r in rows if r[2] == [column]]
    assert len(fks) == 1, f'falta la FK {table}.{column} (db_constraint=False + RunSQL, §6.3)'
    assert (fks[0][0], fks[0][1]) == (deltype, target)


# ----------------------------------------------- CHECK i EXCLUDE -----------------------------------------------

def test_check_de_dates_permet_reformes_d_un_dia(migrator_db):
    checks = _constraints(migrator_db, REN, 'c')
    assert 'renovations_dates_ck' in checks
    definition = re.sub(r'[()\s]', '', checks['renovations_dates_ck'])
    assert 'ini_date<=fin_date' in definition


def test_check_de_description_no_buida(migrator_db):
    checks = _constraints(migrator_db, REN, 'c')
    assert 'renovations_description_ck' in checks
    assert 'btrim' in checks['renovations_description_ck']


def test_check_de_group_link_http_i_longitud(migrator_db):
    checks = _constraints(migrator_db, LNK, 'c')
    assert checks, 'cal un CHECK sobre `group_link`'
    definition = ' '.join(checks.values())
    assert '^https?://' in definition and '2048' in definition and 'char_length' in definition


def test_exclusio_de_solapaments_gist_amb_limits_inclusius(migrator_db):
    excl = _constraints(migrator_db, REN, 'x')
    assert 'renovations_no_overlap' in excl
    definition = excl['renovations_no_overlap']
    assert 'gist' in definition.lower() and 'refuge_id WITH =' in definition
    assert 'daterange(ini_date, fin_date' in definition and "'[]'" in definition and '&&' in definition


# ----------------------------------------------- índexs (§2.12) -----------------------------------------------

def test_index_de_refugi_i_data_per_a_la_llista_d_un_refugi(migrator_db):
    cols = {c for _, c, _, _ in _indexes(migrator_db, REN).values()}
    assert 'refuge_id, fin_date, ini_date' in cols


def test_index_de_data_per_a_la_llista_global(migrator_db):
    cols = {c for _, c, _, _ in _indexes(migrator_db, REN).values()}
    assert 'fin_date, ini_date' in cols


def test_index_parcial_per_creador(migrator_db):
    partial = [(c, p) for _, c, p, _ in _indexes(migrator_db, REN).values() if p]
    assert any(c == 'creator_uid, fin_date' and 'creator_uid IS NOT NULL' in p for c, p in partial), partial


def test_index_gist_de_l_exclusio(migrator_db):
    assert any(m == 'gist' for _, _, _, m in _indexes(migrator_db, REN).values())


@pytest.mark.parametrize('table', [PAR, EXP])
def test_index_per_usuari_a_participants_i_expulsats(migrator_db, table):
    cols = {c for _, c, _, _ in _indexes(migrator_db, table).values()}
    assert 'user_uid, renovation_id' in cols                           # num_renovated_refuges / esborrat d'usuari
    assert 'renovation_id, user_uid' in cols                           # la PK


# ----------------------------------------------- funcions i triggers (§2.12.1, §2.14) -----------------------------------------------

FUNCTIONS = ['fn_renovation_anonymize', 'fn_renovation_requires_link', 'fn_renovation_member_guard']


@pytest.mark.parametrize('fn', FUNCTIONS)
def test_funcions_security_definer_amb_search_path_fix(migrator_db, fn):
    row = fetch_one(migrator_db, """
        SELECT p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner)
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'activity' AND p.proname = %s""", [fn])
    assert row is not None, f'falta activity.{fn}'
    secdef, config, owner = row
    assert secdef is True and owner == 'migrator'
    assert any(c.startswith('search_path=') and 'pg_catalog' in c for c in (config or [])), config


def _trigger(conn, table, name):
    row = fetch_one(conn, """
        SELECT pg_get_triggerdef(t.oid), t.tgconstraint <> 0, t.tgdeferrable, t.tginitdeferred
          FROM pg_trigger t WHERE t.tgrelid = %s::regclass AND t.tgname = %s AND NOT t.tgisinternal""", [table, name])
    assert row is not None, f'falta el trigger {name} a {table}'
    return row


def test_trigger_d_anonimitzacio_esborra_l_enllac(migrator_db):
    definition = _trigger(migrator_db, REN, 'renovations_anonymize')[0]
    assert 'AFTER UPDATE OF creator_uid' in definition and 'FOR EACH ROW' in definition
    assert 'fn_renovation_anonymize' in definition


def test_constraint_trigger_diferit_exigeix_enllac(migrator_db):
    definition, is_constraint, deferrable, init_deferred = _trigger(migrator_db, REN, 'renovations_requires_link')
    assert 'AFTER INSERT' in definition and 'fn_renovation_requires_link' in definition
    assert (is_constraint, deferrable, init_deferred) == (True, True, True)


@pytest.mark.parametrize('table,name', [(PAR, 'renovation_participants_guard'), (EXP, 'renovation_expelled_guard')])
def test_triggers_de_guarda_abans_de_l_insert(migrator_db, table, name):
    definition = _trigger(migrator_db, table, name)[0]
    assert 'BEFORE INSERT' in definition and 'fn_renovation_member_guard' in definition


# ----------------------------------------------- RLS i grants (§2.12–§2.14, §7.2) -----------------------------------------------

POLICIES = {
    REN: {'renov_select': 'SELECT', 'renov_insert': 'INSERT', 'renov_update': 'UPDATE', 'renov_delete': 'DELETE'},
    LNK: {'rlinks_select': 'SELECT', 'rlinks_insert': 'INSERT', 'rlinks_update': 'UPDATE'},     # sense DELETE
    PAR: {'rparts_select': 'SELECT', 'rparts_insert': 'INSERT', 'rparts_delete': 'DELETE'},
    EXP: {'rexp_select': 'SELECT', 'rexp_insert': 'INSERT'},                                    # expulsió definitiva
}
GRANTS = {REN: {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}, LNK: {'SELECT', 'INSERT', 'UPDATE'},
          PAR: {'SELECT', 'INSERT', 'DELETE'}, EXP: {'SELECT', 'INSERT'}}


@pytest.mark.parametrize('table', TABLES)
def test_politiques_rls_noms_i_ordres(migrator_db, table):
    schema, name = table.split('.')
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies WHERE schemaname = %s "
                                  "AND tablename = %s", [schema, name])
    assert {r[0]: r[1] for r in rows} == POLICIES[table]
    assert all('app' in r[2] for r in rows)


@pytest.mark.parametrize('table', TABLES)
def test_matriu_de_grants_d_app(app_db, table):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == GRANTS[table]
