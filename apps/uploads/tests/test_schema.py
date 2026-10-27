"""
Esquema físic de `uploads.0001` (chunk 7; docs/design/postgres-schema.md §2.19, §3, §6.3, §7.2): taula
`moderation.upload_intents`, `CHECK` (target, estat, motiu de fallada, forma, estat coherent, caducitat), `UNIQUE
quarantine_key`, índexs, FK reals `ON DELETE CASCADE` (usuari, refugi, experiència), RLS i grants `SELECT, INSERT,
UPDATE, DELETE`.

Ordre de migracions (§6.2): `experiences.0001` -> `uploads.0001`. El schema `moderation` el crea `core`.
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLE = 'moderation.upload_intents'


def _columns(conn):
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = 'moderation' AND table_name = 'upload_intents'""")
    return {r[0]: r for r in rows}


def _indexes(conn):
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'moderation' "
                           "AND tablename = 'upload_intents'")
    out = {}
    for name, definition in rows:
        m = re.search(r'\((.*?)\)(?: WHERE (.*))?$', definition)
        out[name] = ('UNIQUE' in definition, m.group(1), m.group(2) or '')
    return out


def _constraints(conn, kind):
    return dict(fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE contype = %s AND conrelid = %s::regclass", [kind, TABLE]))


def _fks(conn):
    return fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [TABLE])


# ---------- migració ----------

def test_migracio_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'uploads' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_experiences():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'uploads' and k[1].startswith('0001')]
    assert node, 'cal una migracio `uploads.0001_*`'
    apps = {app for app, _ in loader.graph.forwards_plan(node[0])}
    assert {'experiences', 'accounts', 'refuges'} <= apps


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'uploads', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_cada_runsql_es_reversible():
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'uploads' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql and all(op.reversible for op in run_sql)


# ---------- taula i columnes ----------

def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'moderation' AND c.relname = 'upload_intents' AND c.relkind = 'r'""")
    assert row == (True, False, 'migrator')


def test_columnes(migrator_db):
    c = _columns(migrator_db)
    assert set(c) == {'id', 'user_uid', 'target', 'content_type', 'size', 'quarantine_key', 'refuge_id',
                      'experience_id', 'status', 'rights_confirmed_at', 'created_at', 'expire_at', 'result_key',
                      'failure_reason'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['user_uid'][1], c['user_uid'][2], c['user_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['target'][1], c['target'][2], c['target'][4]) == ('varchar', 'NO', 10)
    assert (c['content_type'][1], c['content_type'][2], c['content_type'][4]) == ('varchar', 'NO', 100)
    assert (c['size'][1], c['size'][2]) == ('int8', 'NO')
    assert (c['quarantine_key'][1], c['quarantine_key'][2]) == ('text', 'NO')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'YES')
    assert (c['experience_id'][1], c['experience_id'][2]) == ('uuid', 'YES')
    assert (c['status'][1], c['status'][2], c['status'][4]) == ('varchar', 'NO', 9)
    assert c['status'][3].startswith("'pending'")
    assert (c['rights_confirmed_at'][1], c['rights_confirmed_at'][2]) == ('timestamptz', 'NO')
    assert c['rights_confirmed_at'][3] is None                       # l'app l'envia (instant en què es declaren els drets)
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO') and c['created_at'][3].startswith('now()')
    assert (c['expire_at'][1], c['expire_at'][2]) == ('timestamptz', 'NO')
    assert "interval '1 day'" in c['expire_at'][3].lower().replace('"', "'") or '1 day' in c['expire_at'][3]
    assert (c['result_key'][1], c['result_key'][2]) == ('text', 'YES')
    assert (c['failure_reason'][1], c['failure_reason'][2], c['failure_reason'][4]) == ('varchar', 'YES', 24)


def test_pk_uuid_a_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [TABLE])
    assert row == (['id'],)


# ---------- CHECK i UNIQUE ----------

@pytest.mark.parametrize('name,needles', [
    ('upload_intents_target_ck', ['target', 'refuge', 'experience', 'avatar']),
    ('upload_intents_status_ck', ['status', 'pending', 'confirmed', 'failed']),
    ('upload_intents_failure_reason_ck', ['missing_object', 'too_large', 'invalid_type', 'processing_error',
                                          'moderation_blocked']),
    ('upload_intents_shape_ck', ['target', 'avatar', 'refuge_id', 'experience_id']),
    ('upload_intents_state_ck', ['status', 'result_key', 'failure_reason']),
    ('upload_intents_expire_ck', ['expire_at', 'created_at']),
])
def test_check_amb_el_nom_del_disseny(migrator_db, name, needles):
    checks = _constraints(migrator_db, 'c')
    assert name in checks, sorted(checks)
    assert all(n in checks[name] for n in needles), checks[name]


def test_check_de_la_mida_positiva(migrator_db):
    checks = [d for d in _constraints(migrator_db, 'c').values() if 'size' in d and '> 0' in d.replace('(', '').replace(')', '')]
    assert checks, _constraints(migrator_db, 'c')


def test_unique_quarantine_key(migrator_db):
    uniques = _constraints(migrator_db, 'u')
    idx = _indexes(migrator_db)
    assert any('quarantine_key' in d for d in uniques.values()) or \
        any(u and c == 'quarantine_key' for u, c, _ in idx.values())


# ---------- FK ----------

@pytest.mark.parametrize('column,target', [('user_uid', 'users.users'), ('refuge_id', 'refuges.refuges'),
                                           ('experience_id', 'activity.experiences')])
def test_fk_real_cascade_diferible_amb_el_nom_del_disseny(migrator_db, column, target):
    fks = [f for f in _fks(migrator_db) if f[5] == [column]]
    assert len(fks) == 1, f'falta la FK upload_intents.{column} (db_constraint=False + RunSQL, §6.3)'
    name, deltype, deferrable, deferred, ref, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, target)
    assert name == f'upload_intents_{column}_fk'


def test_nomes_hi_ha_les_tres_fk_del_disseny(migrator_db):
    assert len(_fks(migrator_db)) == 3


# ---------- índexs ----------

def test_indexs(migrator_db):
    idx = _indexes(migrator_db)
    cols = {c: p for _, c, p in idx.values()}
    assert 'expire_at' in cols, idx                                  # purga: DELETE … WHERE expire_at < now()
    assert 'user_uid, created_at DESC' in cols, idx                  # intents de l'usuari + FK
    assert 'refuge_id' in cols and 'refuge_id IS NOT NULL' in cols['refuge_id'], idx
    assert 'experience_id' in cols and 'experience_id IS NOT NULL' in cols['experience_id'], idx


def test_cap_index_like_de_django(migrator_db):
    rows = fetch_all(migrator_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'moderation' "
                                  "AND tablename = 'upload_intents' AND indexname LIKE %s", ['%\\_like'])
    assert rows == []
    assert fetch_one(migrator_db, "SELECT count(*) FROM pg_tables WHERE schemaname = 'moderation' "
                                  "AND tablename = 'upload_intents'") == (1,)


# ---------- RLS i grants ----------

def test_politiques_rls_noms_i_ordres(migrator_db):
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = 'moderation' AND tablename = 'upload_intents'")
    assert {(r[0], r[1]) for r in rows} == {('intents_select', 'SELECT'), ('intents_insert', 'INSERT'),
                                            ('intents_update', 'UPDATE'), ('intents_delete', 'DELETE')}
    assert all('app' in r[2] for r in rows)


def test_matriu_de_grants_d_app(app_db):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [TABLE])[0]}
    assert got == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}
