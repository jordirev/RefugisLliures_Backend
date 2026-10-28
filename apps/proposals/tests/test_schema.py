"""
Esquema físic de `proposals.0001` (chunk 8; docs/design/postgres-schema.md §2.18, §2.5-2.7, §6.3, §7.2).

Taula `proposals.refuge_proposals` (PK UUID v7 de la BD, `jsonb`, 3 FK `SET NULL`, `CHECK`s, 5 índexs, RLS i grants
`SELECT, INSERT, UPDATE`) i l'escriptura del catàleg (`refuges`, `refuge_amenities`, `refuge_links`) que el chunk 2
va deixar només de lectura: grants `INSERT, UPDATE, DELETE` i polítiques `{ADM} OR {SYS}`.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLE = 'proposals.refuge_proposals'
CATALOG = {'refuges.refuges': 'refuges', 'refuges.refuge_amenities': 'amen', 'refuges.refuge_links': 'links'}
PRIVS = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')


def _columns(conn):
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = 'proposals' AND table_name = 'refuge_proposals'""")
    return {r[0]: r for r in rows}


def _indexes(conn):
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'proposals' "
                           "AND tablename = 'refuge_proposals'")
    out = {}
    for name, definition in rows:
        cols = re.search(r'\((.*?)\)(?: WHERE (.*))?$', definition)
        out[name] = (cols.group(1), cols.group(2) or '')
    return out


def _checks(conn):
    return dict(fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE contype = 'c' AND conrelid = %s::regclass", [TABLE]))


# ---------- migració ----------

def test_migracio_0001_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'proposals' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts_i_refuges():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'proposals' and k[1].startswith('0001')]
    assert node, 'cal una migracio `proposals.0001_*`'
    plan = set(loader.graph.forwards_plan(node[0]))
    assert any(app == 'accounts' for app, _ in plan) and any(app == 'refuges' for app, _ in plan)


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'proposals', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_la_migracio_es_reversible():
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'proposals' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql, 'la 0001 crea CHECK, FK, RLS i grants per RunSQL'
    assert all(op.reversible for op in run_sql)


def test_cap_index_like_de_django(migrator_db):
    assert fetch_all(migrator_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'proposals' "
                                  "AND indexname LIKE %s", ['%\\_like']) == []


def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'proposals' AND c.relname = 'refuge_proposals' AND c.relkind = 'r'""")
    assert row == (True, False, 'migrator')


# ---------- columnes ----------

def test_columnes(migrator_db):
    c = _columns(migrator_db)
    assert set(c) == {'id', 'refuge_id', 'action', 'status', 'payload', 'refuge_snapshot', 'comment', 'creator_uid',
                      'created_at', 'reviewer_uid', 'reviewed_at', 'rejection_reason'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'YES')
    assert (c['action'][1], c['action'][2], c['action'][4]) == ('varchar', 'NO', 6)
    assert (c['status'][1], c['status'][2], c['status'][4]) == ('varchar', 'NO', 8)
    assert "'pending'" in c['status'][3]
    assert (c['payload'][1], c['payload'][2]) == ('jsonb', 'YES')
    assert (c['refuge_snapshot'][1], c['refuge_snapshot'][2]) == ('jsonb', 'YES')
    assert (c['comment'][1], c['comment'][2]) == ('text', 'YES')
    for col in ('creator_uid', 'reviewer_uid'):
        assert (c[col][1], c[col][2], c[col][4]) == ('varchar', 'YES', 128)
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO') and c['created_at'][3].lower().startswith('now()')
    assert (c['reviewed_at'][1], c['reviewed_at'][2]) == ('timestamptz', 'YES')
    assert (c['rejection_reason'][1], c['rejection_reason'][2]) == ('text', 'YES')


def test_pk_uuid_a_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [TABLE])
    assert row == (['id'],)


# ---------- CHECK ----------

@pytest.mark.parametrize('name', ['refuge_proposals_action_ck', 'refuge_proposals_status_ck',
                                  'refuge_proposals_shape_ck', 'refuge_proposals_refuge_ref_ck',
                                  'refuge_proposals_review_ck', 'refuge_proposals_payload_keys_ck',
                                  'refuge_proposals_payload_coord_ck', 'refuge_proposals_size_ck'])
def test_check_del_disseny_existeix(migrator_db, name):
    assert name in _checks(migrator_db)


def test_checks_de_longitud_de_comment_i_rejection_reason(migrator_db):
    defs = list(_checks(migrator_db).values())
    assert any('comment' in d and '4000' in d and 'char_length' in d for d in defs)
    assert any('rejection_reason' in d and '2000' in d and 'char_length' in d for d in defs)


def test_llista_de_claus_del_payload_sense_remarque(migrator_db):
    d = _checks(migrator_db)['refuge_proposals_payload_keys_ck']
    for key in ALLOWED:
        assert f"'{key}'" in d
    assert 'remarque' not in d


ALLOWED = ['name', 'coord', 'altitude', 'places', 'info_comp', 'description', 'links', 'type', 'region',
           'departement', 'condition']


# ---------- FK ----------

@pytest.mark.parametrize('column,target', [('refuge_id', 'refuges.refuges'), ('creator_uid', 'users.users'),
                                           ('reviewer_uid', 'users.users')])
def test_fk_real_set_null_amb_el_nom_del_disseny(migrator_db, column, target):
    rows = fetch_all(migrator_db, """
        SELECT c.conname, c.confdeltype, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [TABLE])
    fk = [r for r in rows if r[3] == [column]]
    assert len(fk) == 1, f'falta la FK {column} (db_constraint=False + RunSQL, §6.3)'
    assert (fk[0][1], fk[0][2]) == ('n', target)                      # ON DELETE SET NULL
    assert fk[0][0] == f'refuge_proposals_{column}_fk'
    assert len(rows) == 3


# ---------- índexs ----------

def test_indexs_del_disseny(migrator_db):
    idx = _indexes(migrator_db)
    by_cols = {}
    for cols, where in idx.values():
        by_cols.setdefault(cols, []).append(where)
    assert any('pending' in w for w in by_cols.get('created_at DESC, id DESC', [])), idx          # cua de l'admin
    assert 'status, created_at DESC, id DESC' in by_cols, idx
    assert 'creator_uid, created_at DESC, id DESC' in by_cols, idx
    assert 'refuge_id, status' in by_cols, idx
    assert any('reviewer_uid IS NOT NULL' in w for w in by_cols.get('reviewer_uid', [])), idx


# ---------- RLS i grants ----------

def test_politiques_rls_de_la_taula(migrator_db):
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = 'proposals' AND tablename = 'refuge_proposals'")
    assert {(r[0], r[1]) for r in rows} == {('proposals_select', 'SELECT'), ('proposals_insert', 'INSERT'),
                                            ('proposals_update', 'UPDATE')}     # sense DELETE: l'historial no s'esborra
    assert all('app' in r[2] for r in rows)


def test_grants_d_app_select_insert_update(app_db):
    got = {p for p in PRIVS if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [TABLE])[0]}
    assert got == {'SELECT', 'INSERT', 'UPDATE'}


# ---------- catàleg: escriptura que obre el chunk 8 ----------

@pytest.mark.parametrize('table', CATALOG)
def test_grants_del_cataleg_ara_inclouen_escriptura(app_db, table):
    got = {p for p in PRIVS if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}


def test_refuge_types_continua_nomes_de_lectura(app_db):
    got = {p for p in PRIVS if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')",
                                         ['refuges.refuge_types'])[0]}
    assert got == {'SELECT'}


@pytest.mark.parametrize('table,prefix', CATALOG.items())
def test_politiques_del_cataleg(migrator_db, table, prefix):
    schema, name = table.split('.')
    rows = fetch_all(migrator_db, "SELECT policyname, cmd FROM pg_policies WHERE schemaname = %s AND tablename = %s",
                     [schema, name])
    assert set(rows) == {(f'{prefix}_select', 'SELECT'), (f'{prefix}_insert', 'INSERT'),
                         (f'{prefix}_update', 'UPDATE'), (f'{prefix}_delete', 'DELETE')}


@pytest.mark.parametrize('table,prefix', CATALOG.items())
def test_les_politiques_d_escriptura_del_cataleg_exigeixen_admin_o_sistema(migrator_db, table, prefix):
    schema, name = table.split('.')
    for policy in ('insert', 'update', 'delete'):
        row = fetch_one(migrator_db, "SELECT coalesce(qual, '') || ' ' || coalesce(with_check, '') FROM pg_policies "
                                     "WHERE schemaname = %s AND tablename = %s AND policyname = %s",
                        [schema, name, f'{prefix}_{policy}'])
        assert 'is_admin' in row[0] and 'is_system' in row[0], (policy, row)
        assert 'uid()' not in row[0], 'cap camí per a un usuari corrent'
