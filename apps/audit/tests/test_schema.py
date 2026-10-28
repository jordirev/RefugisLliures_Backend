"""
Esquema físic de `audit.0001` (chunk 9; docs/design/postgres-schema.md §2.24, §3, §6.3, §7.2): taula `audit.audit_logs`
amb columnes, `CHECK` (format de l'acció, metadata objecte < 16 KiB, `expire_at > created_at`), FK reals `ON DELETE
CASCADE` (`actor_uid`, `subject_uid`), índexs, RLS i grants **sense `UPDATE`** (registre immutable).

Ordre de migracions (§6.2): `accounts.0001` -> `audit.0001` -> `moderation.0001` (el *trigger* d'usuari de
`moderation.0001` desvincula les files `legal_hold` d'aquesta taula).
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLE = 'audit.audit_logs'


def _columns(conn):
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = 'audit' AND table_name = 'audit_logs'""")
    return {r[0]: r for r in rows}


def _indexes(conn):
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'audit' "
                           "AND tablename = 'audit_logs'")
    out = {}
    for name, definition in rows:
        m = re.search(r'\((.*?)\)(?: WHERE (.*))?$', definition)
        out[name] = ('UNIQUE' in definition, m.group(1), (m.group(2) or '').replace('(', '').replace(')', ''))
    return out


def _constraints(conn, kind):
    return dict(fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE contype = %s AND conrelid = %s::regclass", [kind, TABLE]))


def test_migracio_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'audit' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'audit' and k[1].startswith('0001')]
    assert node, 'cal una migracio `audit.0001_*`'
    assert 'accounts' in {app for app, _ in loader.graph.forwards_plan(node[0])}


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'audit', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_cada_runsql_es_reversible():
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'audit' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql and all(op.reversible for op in run_sql)


def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'audit' AND c.relname = 'audit_logs' AND c.relkind = 'r'""")
    assert row == (True, False, 'migrator')


def test_columnes(migrator_db):
    c = _columns(migrator_db)
    assert set(c) == {'id', 'actor_uid', 'subject_uid', 'action', 'target_type', 'target_id', 'metadata', 'created_at',
                      'expire_at', 'legal_hold'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['actor_uid'][1], c['actor_uid'][2], c['actor_uid'][4]) == ('varchar', 'YES', 128)
    assert (c['subject_uid'][1], c['subject_uid'][2], c['subject_uid'][4]) == ('varchar', 'YES', 128)
    assert (c['action'][1], c['action'][2], c['action'][4]) == ('varchar', 'NO', 48)
    assert (c['target_type'][1], c['target_type'][2], c['target_type'][4]) == ('varchar', 'YES', 32)
    assert (c['target_id'][1], c['target_id'][2], c['target_id'][4]) == ('varchar', 'YES', 500)
    assert (c['metadata'][1], c['metadata'][2]) == ('jsonb', 'NO') and "'{}'" in c['metadata'][3]
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO') and c['created_at'][3].startswith('now()')
    assert (c['expire_at'][1], c['expire_at'][2]) == ('timestamptz', 'NO')
    assert '365 days' in c['expire_at'][3]
    assert (c['legal_hold'][1], c['legal_hold'][2]) == ('bool', 'NO') and c['legal_hold'][3] == 'false'


def test_pk_uuid_a_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [TABLE])
    assert row == (['id'],)


def test_check_amb_el_disseny(migrator_db):
    checks = _constraints(migrator_db, 'c')
    defs = ' '.join(checks.values())
    assert '[a-z_]+' in defs and 'action' in defs                                  # format, no llista tancada
    assert any('jsonb_typeof' in d and 'object' in d and '16384' in d for d in checks.values()), checks
    assert any('expire_at' in d and 'created_at' in d and '>' in d for d in checks.values()), checks


def test_fk_reals_cascade(migrator_db):
    rows = {r[5][0]: r for r in fetch_all(migrator_db, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [TABLE])}
    assert set(rows) == {'actor_uid', 'subject_uid'}
    for column, row in rows.items():
        assert (row[1], row[4]) == ('c', 'users.users'), column
        assert row[0] == f'audit_logs_{column}_fk'


def test_indexs(migrator_db):
    idx = {c: w for _, c, w in _indexes(migrator_db).values()}
    assert 'expire_at' in idx and 'legal_hold' in idx['expire_at'], idx            # purga: WHERE NOT legal_hold
    assert 'actor_uid, created_at DESC' in idx, idx
    assert 'subject_uid' in idx and 'subject_uid IS NOT NULL' in idx['subject_uid']


def test_politiques_rls(migrator_db):
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = 'audit' AND tablename = 'audit_logs'")
    assert {(r[0], r[1]) for r in rows} == {('audit_select', 'SELECT'), ('audit_insert', 'INSERT'),
                                            ('audit_delete', 'DELETE')}
    assert all('app' in r[2] for r in rows)


def test_matriu_de_grants_d_app_sense_update(app_db):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [TABLE])[0]}
    assert got == {'SELECT', 'INSERT', 'DELETE'}
