"""
Esquema físic de `moderation.0001` (chunk 9; docs/design/postgres-schema.md §2.20–§2.22, §3, §6.3, §7.2): taules
`moderation.media_reports`, `moderation.moderation_notices` i `moderation.moderation_hash_blocklist` amb columnes,
`CHECK` i `UNIQUE` amb els noms del disseny, FK reals amb el seu `ON DELETE`, índexs, RLS, grants, la funció
`fn_hash_match` i els *triggers* `refuges_detach_legal_hold` / `users_detach_legal_hold`.

Ordre de migracions (§6.2): `uploads.0001` (i `accounts`, `refuges`) -> `moderation.0001`. `media_deletion_queue` NO
s'implementa en aquest chunk (D40).
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

REPORTS = 'moderation.media_reports'
NOTICES = 'moderation.moderation_notices'
BLOCKLIST = 'moderation.moderation_hash_blocklist'


def _columns(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _indexes(conn, table):
    schema, name = table.split('.')
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
                     [schema, name])
    out = {}
    for iname, definition in rows:
        m = re.search(r'\((.*?)\)(?: NULLS NOT DISTINCT)?(?: WHERE (.*))?$', definition)
        out[iname] = ('UNIQUE' in definition, m.group(1), (m.group(2) or '').replace('(', '').replace(')', ''),
                      'NULLS NOT DISTINCT' in definition)
    return out


def _constraints(conn, table, kind):
    return dict(fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE contype = %s AND conrelid = %s::regclass", [kind, table]))


def _fks(conn, table):
    return {r[5][0]: r for r in fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])}


# ---------- migracions ----------

def test_migracio_aplicada_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'moderation' "
                                  "AND name LIKE '0001%%'")[0] == 1


def test_la_migracio_depen_d_accounts_refuges_uploads_i_audit():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'moderation' and k[1].startswith('0001')]
    assert node, 'cal una migracio `moderation.0001_*`'
    apps = {app for app, _ in loader.graph.forwards_plan(node[0])}
    assert {'accounts', 'refuges', 'uploads', 'audit'} <= apps          # el trigger d'usuari toca `audit.audit_logs`


def test_models_i_migracions_sincronitzats(migrator_db):
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'moderation', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


def test_cada_runsql_es_reversible():
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == 'moderation' and k[1].startswith('0001'))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql and all(op.reversible for op in run_sql)


@pytest.mark.parametrize('table', [REPORTS, NOTICES, BLOCKLIST])
def test_taules_amb_rls_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row == (True, False, 'migrator')


def test_media_deletion_queue_no_s_implementa_en_aquest_chunk(migrator_db):
    """D40 (1): els chunks 7 i 8 esborren a R2 de manera síncrona; la cua queda a TECH_DEBT."""
    assert fetch_one(migrator_db, "SELECT to_regclass('moderation.media_deletion_queue')") == (None,)


# ---------- media_reports ----------

def test_columnes_de_media_reports(migrator_db):
    c = _columns(migrator_db, REPORTS)
    assert set(c) == {'id', 'refuge_id', 'media_key', 'reporter_uid', 'reason', 'details', 'media_creator_uid',
                      'status', 'priority', 'created_at', 'resolved_at', 'resolved_by', 'action', 'statement',
                      'source', 'legal_hold', 'anonymized_at'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'YES')
    assert (c['media_key'][1], c['media_key'][2], c['media_key'][4]) == ('varchar', 'NO', 500)
    assert (c['reporter_uid'][1], c['reporter_uid'][2], c['reporter_uid'][4]) == ('varchar', 'YES', 128)
    assert (c['reason'][1], c['reason'][2], c['reason'][4]) == ('varchar', 'NO', 32)
    assert (c['details'][1], c['details'][2]) == ('text', 'YES')
    assert (c['media_creator_uid'][1], c['media_creator_uid'][2], c['media_creator_uid'][4]) == ('varchar', 'YES', 128)
    assert (c['status'][1], c['status'][2], c['status'][4]) == ('varchar', 'NO', 8) and "'pending'" in c['status'][3]
    assert (c['priority'][1], c['priority'][2], c['priority'][4]) == ('varchar', 'NO', 6)
    assert "'normal'" in c['priority'][3]
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO') and c['created_at'][3].startswith('now()')
    assert (c['resolved_at'][1], c['resolved_at'][2]) == ('timestamptz', 'YES')
    assert (c['resolved_by'][1], c['resolved_by'][2], c['resolved_by'][4]) == ('varchar', 'YES', 128)
    assert (c['action'][1], c['action'][2], c['action'][4]) == ('varchar', 'YES', 20)
    assert (c['statement'][1], c['statement'][2]) == ('text', 'YES')
    assert (c['source'][1], c['source'][2], c['source'][4]) == ('varchar', 'NO', 9) and "'user'" in c['source'][3]
    assert (c['legal_hold'][1], c['legal_hold'][2]) == ('bool', 'NO') and c['legal_hold'][3] == 'false'
    assert (c['anonymized_at'][1], c['anonymized_at'][2]) == ('timestamptz', 'YES')


def test_pk_uuid_a_id(migrator_db):
    for table in (REPORTS, NOTICES, BLOCKLIST):
        row = fetch_one(migrator_db, """
            SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                      JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
              FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [table])
        assert row == (['id'],), table


@pytest.mark.parametrize('name,needles', [
    ('media_reports_other_details_ck', ['reason', 'other', 'details', 'btrim']),
    ('media_reports_source_ck', ['source', 'user', 'automatic', 'reporter_uid', 'anonymized_at']),
    ('media_reports_hold_ck', ['anonymized_at', 'legal_hold']),
    ('media_reports_resolution_ck', ['status', 'pending', 'resolved', 'resolved_at', 'action', 'statement']),
    ('media_reports_not_own_ck', ['reporter_uid', 'media_creator_uid']),
])
def test_check_amb_el_nom_del_disseny(migrator_db, name, needles):
    checks = _constraints(migrator_db, REPORTS, 'c')
    assert name in checks, sorted(checks)
    assert all(n in checks[name] for n in needles), checks[name]


def test_check_dels_valors_de_les_enumeracions(migrator_db):
    defs = ' '.join(_constraints(migrator_db, REPORTS, 'c').values())
    for value in ('child_sexual_abuse', 'child_endangerment', 'sexual_nonconsensual', 'violence_gore',
                  'terrorism_extremism', 'hate_speech', 'harassment_bullying', 'animal_cruelty', 'self_harm',
                  'illegal_goods', 'my_image', 'privacy_personal_data', 'intellectual_property', 'fraud_scam_spam',
                  'misleading_irrelevant', 'other', 'pending', 'resolved', 'high', 'normal', 'dismiss', 'remove',
                  'remove_and_strike', 'user', 'automatic'):
        assert f"'{value}'" in defs, value
    assert any('details' in d and '1000' in d for d in _constraints(migrator_db, REPORTS, 'c').values())


def test_unicitats_de_media_reports(migrator_db):
    idx = _indexes(migrator_db, REPORTS)
    by_name = idx
    assert 'media_reports_unique_reporter_uq' in by_name, sorted(by_name)
    unique, cols, where, _ = by_name['media_reports_unique_reporter_uq']
    assert unique and cols == 'refuge_id, media_key, reporter_uid' and 'reporter_uid IS NOT NULL' in where
    assert 'media_reports_unique_auto_uq' in by_name, sorted(by_name)
    unique, cols, where, nulls_not_distinct = by_name['media_reports_unique_auto_uq']
    assert unique and cols == 'refuge_id, media_key' and "source" in where and "automatic" in where
    assert nulls_not_distinct


def test_indexs_de_media_reports(migrator_db):
    cols = {c: w for _, c, w, _ in _indexes(migrator_db, REPORTS).values()}
    assert 'status, priority, created_at, id' in cols, cols              # llista d'admin
    assert 'reporter_uid' in cols                                         # FK/cascada
    assert 'media_creator_uid' in cols and 'media_creator_uid IS NOT NULL' in cols['media_creator_uid']
    assert 'resolved_by' in cols and 'resolved_by IS NOT NULL' in cols['resolved_by']


def test_fk_de_media_reports(migrator_db):
    fks = _fks(migrator_db, REPORTS)
    expected = {'refuge_id': ('c', 'refuges.refuges'), 'reporter_uid': ('c', 'users.users'),
                'media_creator_uid': ('n', 'users.users'), 'resolved_by': ('n', 'users.users')}
    assert set(fks) == set(expected), fks
    for column, (deltype, target) in expected.items():
        name, got_del, _, _, ref, _ = fks[column]
        assert (got_del, ref) == (deltype, target), column
        assert name == f'media_reports_{column}_fk'


# ---------- moderation_notices ----------

def test_columnes_de_moderation_notices(migrator_db):
    c = _columns(migrator_db, NOTICES)
    assert set(c) == {'id', 'user_uid', 'type', 'statement', 'created_at', 'refuge_id', 'media_key', 'reason',
                      'action', 'report_id', 'automated', 'strikes'}
    assert (c['user_uid'][1], c['user_uid'][2], c['user_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['type'][1], c['type'][2], c['type'][4]) == ('varchar', 'NO', 20)
    assert (c['statement'][1], c['statement'][2]) == ('text', 'NO')
    assert (c['created_at'][1], c['created_at'][2]) == ('timestamptz', 'NO') and c['created_at'][3].startswith('now()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'YES')
    assert (c['media_key'][1], c['media_key'][2], c['media_key'][4]) == ('varchar', 'YES', 500)
    assert (c['reason'][1], c['reason'][2], c['reason'][4]) == ('varchar', 'YES', 32)
    assert (c['action'][1], c['action'][2], c['action'][4]) == ('varchar', 'YES', 20)
    assert (c['report_id'][1], c['report_id'][2]) == ('uuid', 'YES')
    assert (c['automated'][1], c['automated'][2]) == ('bool', 'NO') and c['automated'][3] == 'false'
    assert (c['strikes'][1], c['strikes'][2]) == ('int2', 'YES')


def test_check_dels_avisos(migrator_db):
    defs = ' '.join(_constraints(migrator_db, NOTICES, 'c').values())
    for value in ('content_hidden', 'content_restored', 'content_removed', 'strike', 'account_blocked',
                  'upload_blocked', 'dismiss', 'remove', 'remove_and_strike', 'auto_hide'):
        assert f"'{value}'" in defs, value
    assert any('strikes' in d and '>= 0' in d.replace('(', '').replace(')', '')
               for d in _constraints(migrator_db, NOTICES, 'c').values())


def test_fk_dels_avisos(migrator_db):
    fks = _fks(migrator_db, NOTICES)
    expected = {'user_uid': ('c', 'users.users'), 'refuge_id': ('n', 'refuges.refuges'),
                'report_id': ('n', 'moderation.media_reports')}
    assert set(fks) == set(expected), fks
    for column, (deltype, target) in expected.items():
        name, got_del, _, _, ref, _ = fks[column]
        assert (got_del, ref) == (deltype, target), column
        assert name == f'moderation_notices_{column}_fk'


def test_indexs_dels_avisos(migrator_db):
    cols = {c: w for _, c, w, _ in _indexes(migrator_db, NOTICES).values()}
    assert 'user_uid, created_at DESC, id DESC' in cols, cols
    assert 'report_id' in cols and 'report_id IS NOT NULL' in cols['report_id']
    assert 'refuge_id' in cols and 'refuge_id IS NOT NULL' in cols['refuge_id']


# ---------- llista de hashes ----------

def test_columnes_de_la_llista_de_hashes(migrator_db):
    c = _columns(migrator_db, BLOCKLIST)
    assert set(c) == {'id', 'sha256', 'phash', 'category', 'source', 'added_at'}
    assert (c['sha256'][1], c['sha256'][2], c['sha256'][4]) == ('bpchar', 'YES', 64)
    assert (c['phash'][1], c['phash'][2]) == ('int8', 'YES')
    assert (c['category'][1], c['category'][2], c['category'][4]) == ('varchar', 'NO', 16)
    assert "'csam'" in c['category'][3]
    assert (c['source'][1], c['source'][2], c['source'][4]) == ('varchar', 'NO', 100)
    assert (c['added_at'][1], c['added_at'][2]) == ('timestamptz', 'NO') and c['added_at'][3].startswith('now()')


def test_check_i_unique_de_la_llista_de_hashes(migrator_db):
    checks = _constraints(migrator_db, BLOCKLIST, 'c')
    assert any('sha256' in d and '[0-9a-f]{64}' in d for d in checks.values()), checks
    assert any('category' in d and 'csam' in d and 'other' in d for d in checks.values()), checks
    assert any('sha256 IS NOT NULL' in d.replace('(', '').replace(')', '') and 'phash IS NOT NULL' in d
               for d in checks.values()), checks
    idx = _indexes(migrator_db, BLOCKLIST)
    assert any(u and c == 'sha256' and 'sha256 IS NOT NULL' in w for u, c, w, _ in idx.values()), idx


def test_la_llista_de_hashes_no_te_cap_politica_ni_cap_privilegi_per_a_app(migrator_db, app_db):
    assert fetch_all(migrator_db, "SELECT policyname FROM pg_policies WHERE schemaname = 'moderation' "
                                  "AND tablename = 'moderation_hash_blocklist'") == []
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [BLOCKLIST])[0]}
    assert got == set()


def test_fn_hash_match_security_definer_amb_search_path_i_execute_nomes_per_a_app(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT p.prosecdef, p.provolatile, pg_get_userbyid(p.proowner), p.proconfig,
               has_function_privilege('app', p.oid, 'EXECUTE'), has_function_privilege('public', p.oid, 'EXECUTE'),
               pg_get_function_arguments(p.oid)
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'moderation' AND p.proname = 'fn_hash_match'""")
    assert row is not None, 'falta moderation.fn_hash_match'
    secdef, volatility, owner, config, app_exec, public_exec, args = row
    assert secdef and volatility == 's' and owner == 'migrator'
    assert any(c.startswith('search_path=') and 'pg_catalog' in c for c in config), config
    assert app_exec and not public_exec
    assert args == 'p_sha256 text, p_phash bigint, p_max_distance integer DEFAULT 6'


# ---------- politiques i grants ----------

def test_politiques_rls_noms_i_ordres(migrator_db):
    rows = fetch_all(migrator_db, "SELECT tablename, policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = 'moderation' AND tablename IN ('media_reports', "
                                  "'moderation_notices')")
    assert {(r[0], r[1], r[2]) for r in rows} == {
        ('media_reports', 'reports_select', 'SELECT'), ('media_reports', 'reports_insert', 'INSERT'),
        ('media_reports', 'reports_update', 'UPDATE'), ('media_reports', 'reports_delete', 'DELETE'),
        ('moderation_notices', 'notices_select', 'SELECT'), ('moderation_notices', 'notices_insert', 'INSERT'),
        ('moderation_notices', 'notices_delete', 'DELETE')}
    assert all('app' in r[3] for r in rows)


@pytest.mark.parametrize('table,expected', [
    (REPORTS, {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    (NOTICES, {'SELECT', 'INSERT', 'DELETE'}),
])
def test_matriu_de_grants_d_app(app_db, table, expected):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == expected


# ---------- triggers de conservacio legal_hold (§2.1, §2.20) ----------

def test_trigger_de_refugi_que_desvincula_les_denuncies_legal_hold(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT t.tgname, t.tgenabled, (t.tgtype & 2) = 2 AS before_, (t.tgtype & 1) = 1 AS per_row,
               (t.tgtype & 8) = 8 AS on_delete, p.proname, n.nspname, p.prosecdef
          FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE t.tgrelid = 'refuges.refuges'::regclass AND t.tgname = 'refuges_detach_legal_hold'""")
    assert row is not None, 'falta el trigger refuges_detach_legal_hold sobre refuges.refuges'
    assert row[1:] == ('O', True, True, True, 'fn_refuges_detach_legal_hold', 'refuges', True)


def test_trigger_d_usuari_que_desvincula_denuncies_i_auditoria_legal_hold(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT t.tgname, t.tgenabled, (t.tgtype & 2) = 2, (t.tgtype & 1) = 1, (t.tgtype & 8) = 8, p.proname,
               n.nspname, p.prosecdef
          FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE t.tgrelid = 'users.users'::regclass AND t.tgname = 'users_detach_legal_hold'""")
    assert row is not None, 'falta el trigger users_detach_legal_hold sobre users.users'
    assert row[1:] == ('O', True, True, True, 'fn_users_detach_legal_hold', 'users', True)
