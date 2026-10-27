"""
Esquema físic de `experiences.0001` i `refuges.0002` (chunk 7; docs/design/postgres-schema.md §2.8, §2.9, §2.15, §6.2,
§6.3, §7.2): taula `activity.experiences`, CHECK, índexs, FK reals `ON DELETE CASCADE`, RLS, grants, *triggers* de
condició (`SECURITY DEFINER`) i, a `refuges`, la columna `refuge_media.experience_id` amb la seva FK i la política
`media_insert` reescrita.

Ordre de migracions (§6.2): `experiences.0001` -> `refuges.0002` (i `uploads.0001`).
"""
import re

import pytest

from apps.core.testing import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.integration, pytest.mark.real_permissions]

TABLE = 'activity.experiences'


def _columns(conn, schema, name):
    rows = fetch_all(conn, """
        SELECT column_name, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, name])
    return {r[0]: r for r in rows}


def _indexes(conn, schema, table):
    """`{nom: (unique, 'cols amb ordre', 'predicat')}` a partir de `pg_indexes`."""
    rows = fetch_all(conn, "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
                     [schema, table])
    out = {}
    for name, definition in rows:
        m = re.search(r'\((.*?)\)(?: WHERE (.*))?$', definition)
        out[name] = ('UNIQUE' in definition, m.group(1), m.group(2) or '')
    return out


def _fks(conn, table):
    return fetch_all(conn, """
        SELECT c.conname, c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])


def _constraints(conn, table, kind):
    return fetch_all(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                           "WHERE contype = %s AND conrelid = %s::regclass", [kind, table])


# ---------- migracions ----------

def test_migracions_aplicades_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'experiences' "
                                  "AND name LIKE '0001%%'")[0] == 1
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'refuges' "
                                  "AND name LIKE '0002%%'")[0] == 1


def test_ordre_de_migracions_refuges_0002_depen_d_experiences_0001():
    """§6.2: `refuges.0002` afegeix la FK cap a `activity.experiences`, que ha d'existir abans."""
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    node = [k for k in loader.graph.node_map if k[0] == 'refuges' and k[1].startswith('0002')]
    assert node, 'cal una migracio `refuges.0002_*`'
    plan = set(loader.graph.forwards_plan(node[0]))
    assert any(app == 'experiences' for app, _ in plan)
    exp = [k for k in loader.graph.node_map if k[0] == 'experiences' and k[1].startswith('0001')]
    assert exp, 'cal una migracio `experiences.0001_*`'
    # i experiences.0001 no pot dependre de refuges.0002 (graf aciclic)
    assert node[0] not in set(loader.graph.forwards_plan(exp[0]))


@pytest.mark.parametrize('app', ['experiences', 'refuges'])
def test_models_i_migracions_sincronitzats(migrator_db, app):
    from django.core.management import call_command
    try:
        call_command('makemigrations', app, check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions de {app} desincronitzats (exit {exc.code})')


@pytest.mark.parametrize('app,prefix', [('experiences', '0001'), ('refuges', '0002')])
def test_cada_runsql_es_reversible(app, prefix):
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunSQL
    loader = MigrationLoader(None, ignore_no_migrations=True)
    key = next(k for k in loader.graph.node_map if k[0] == app and k[1].startswith(prefix))
    run_sql = [op for op in loader.get_migration(*key).operations if isinstance(op, RunSQL)]
    assert run_sql, f'{app}.{prefix} crea FK, RLS, grants o triggers per RunSQL'
    assert all(op.reversible for op in run_sql)


def test_cap_index_like_de_django(migrator_db):
    rows = fetch_all(migrator_db, "SELECT indexname FROM pg_indexes WHERE schemaname = 'activity' "
                                  "AND tablename = 'experiences' AND indexname LIKE %s", ['%\\_like'])
    assert rows == []
    assert fetch_one(migrator_db, "SELECT count(*) FROM pg_tables WHERE schemaname = 'activity' "
                                  "AND tablename = 'experiences'") == (1,)


# ---------- taula ----------

def test_taula_amb_rls_sense_force_i_propietat_del_migrator(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'activity' AND c.relname = 'experiences' AND c.relkind = 'r'""")
    assert row == (True, False, 'migrator')


def test_columnes_d_experiences(migrator_db):
    c = _columns(migrator_db, 'activity', 'experiences')
    assert set(c) == {'id', 'refuge_id', 'creator_uid', 'comment', 'created_at', 'modified_at', 'condition',
                      'condition_counted_at'}
    assert (c['id'][1], c['id'][2]) == ('uuid', 'NO') and c['id'][3].lower().startswith('uuidv7()')
    assert (c['refuge_id'][1], c['refuge_id'][2]) == ('uuid', 'NO')
    assert (c['creator_uid'][1], c['creator_uid'][2], c['creator_uid'][4]) == ('varchar', 'NO', 128)
    assert (c['comment'][1], c['comment'][2]) == ('text', 'NO')
    assert (c['condition'][1], c['condition'][2]) == ('int2', 'NO')          # smallint obligatori (decisio del PO)
    assert c['condition'][3] is None                                          # sense default: l'API l'exigeix
    for col in ('created_at', 'modified_at', 'condition_counted_at'):
        assert (c[col][1], c[col][2]) == ('timestamptz', 'NO'), col
        assert c[col][3].lower().startswith('now()'), col


def test_pk_uuid_a_id(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'p' AND c.conrelid = %s::regclass""", [TABLE])
    assert row == (['id'],)


# ---------- CHECK ----------

def test_check_de_condicio_0_a_3_amb_el_nom_del_disseny(migrator_db):
    checks = dict(_constraints(migrator_db, TABLE, 'c'))
    assert 'experiences_condition_ck' in checks
    d = checks['experiences_condition_ck']
    assert 'condition' in d and '0' in d and '3' in d


def test_check_del_comentari_no_buit_i_com_a_molt_2000(migrator_db):
    checks = [d for _, d in _constraints(migrator_db, TABLE, 'c') if 'comment' in d]
    assert len(checks) == 1, checks
    assert 'btrim' in checks[0] and '2000' in checks[0] and 'char_length' in checks[0]


# ---------- FK ----------

@pytest.mark.parametrize('column,target', [('refuge_id', 'refuges.refuges'), ('creator_uid', 'users.users')])
def test_fk_real_cascade_diferible_amb_el_nom_del_disseny(migrator_db, column, target):
    fks = [f for f in _fks(migrator_db, TABLE) if f[5] == [column]]
    assert len(fks) == 1, f'falta la FK experiences.{column} (db_constraint=False + RunSQL, §6.3)'
    name, deltype, deferrable, deferred, ref, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, target)
    assert name == f'experiences_{column}_fk'


def test_nomes_hi_ha_les_dues_fk_del_disseny(migrator_db):
    assert len(_fks(migrator_db, TABLE)) == 2


# ---------- índexs ----------

def test_indexs_d_experiences(migrator_db):
    cols = {c for _, c, _ in _indexes(migrator_db, 'activity', 'experiences').values()}
    assert 'refuge_id, modified_at DESC, id DESC' in cols, cols      # llista d'un refugi + FK
    assert 'creator_uid, modified_at DESC' in cols, cols             # num_shared_experiences, esborrat d'usuari + FK


# ---------- RLS i grants ----------

def test_politiques_rls_noms_i_ordres(migrator_db):
    rows = fetch_all(migrator_db, "SELECT policyname, cmd, roles::text FROM pg_policies "
                                  "WHERE schemaname = 'activity' AND tablename = 'experiences'")
    assert {(r[0], r[1]) for r in rows} == {('exp_select', 'SELECT'), ('exp_insert', 'INSERT'),
                                            ('exp_update', 'UPDATE'), ('exp_delete', 'DELETE')}
    assert all('app' in r[2] for r in rows)


def test_matriu_de_grants_d_app_select_insert_update_delete(app_db):
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [TABLE])[0]}
    assert got == {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}


# ---------- triggers de condició (§2.9) ----------

def test_funcio_del_trigger_security_definer_i_sense_execute_public(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig::text
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'activity' AND p.proname = 'fn_experience_condition'""")
    assert row is not None, 'falta activity.fn_experience_condition()'
    assert row[0] is True and row[1] == 'migrator'
    assert 'search_path' in row[2] and 'pg_catalog' in row[2]          # SET search_path fix (SECURITY DEFINER)
    # REVOKE ALL ... FROM PUBLIC: l'ACL no és NULL (permisos per defecte) i cap entrada és de PUBLIC (grantee 0)
    row = fetch_one(migrator_db, """
        SELECT p.proacl IS NOT NULL,
               EXISTS (SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE')
          FROM pg_proc p WHERE p.oid = 'activity.fn_experience_condition()'::regprocedure""")
    assert row == (True, False)


def test_app_no_pot_cridar_la_funcio_del_trigger(app_db):
    assert fetch_one(app_db, "SELECT has_function_privilege('app', 'activity.fn_experience_condition()', "
                             "'EXECUTE')")[0] is False


def test_dos_triggers_before_insert_i_before_update_of_condition(migrator_db):
    rows = fetch_all(migrator_db, """
        SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger
         WHERE tgrelid = 'activity.experiences'::regclass AND NOT tgisinternal""")
    defs = dict(rows)
    assert {'experiences_condition_ins', 'experiences_condition_upd'} <= set(defs), defs
    ins, upd = defs['experiences_condition_ins'], defs['experiences_condition_upd']
    assert 'BEFORE INSERT' in ins and 'FOR EACH ROW' in ins and 'fn_experience_condition' in ins
    assert 'BEFORE UPDATE OF condition' in upd and 'FOR EACH ROW' in upd and 'fn_experience_condition' in upd
    assert 'IS DISTINCT FROM' in upd                                    # WHEN (OLD.condition IS DISTINCT FROM NEW.condition)


# ---------- refuges.0002: refuge_media.experience_id ----------

def test_columna_experience_id_a_refuge_media(migrator_db):
    c = _columns(migrator_db, 'refuges', 'refuge_media')
    assert set(c) == {'key', 'refuge_id', 'creator_uid', 'experience_id', 'media_type', 'content_type', 'status',
                      'uploaded_at', 'taken_at', 'width', 'height', 'size_bytes', 'thumb_key', 'blurhash',
                      'rights_confirmed_at'}
    assert (c['experience_id'][1], c['experience_id'][2]) == ('uuid', 'YES')


def test_fk_experience_id_cascade_diferible(migrator_db):
    fks = [f for f in _fks(migrator_db, 'refuges.refuge_media') if f[5] == ['experience_id']]
    assert len(fks) == 1, 'falta la FK refuge_media.experience_id -> activity.experiences (RunSQL)'
    _, deltype, deferrable, deferred, ref, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, TABLE)


def test_index_parcial_d_experience_id(migrator_db):
    idx = _indexes(migrator_db, 'refuges', 'refuge_media')
    partial = [(c, p) for _, c, p in idx.values() if c == 'experience_id']
    assert partial and all('experience_id IS NOT NULL' in p for _, p in partial), idx


def test_les_fk_i_indexs_anteriors_de_refuge_media_es_conserven(migrator_db):
    assert {f[5][0] for f in _fks(migrator_db, 'refuges.refuge_media')} == {'refuge_id', 'creator_uid',
                                                                           'experience_id'}
    cols = {c for _, c, _ in _indexes(migrator_db, 'refuges', 'refuge_media').values()}
    assert {'refuge_id, uploaded_at, key', 'creator_uid, uploaded_at'} <= cols


def test_media_insert_reescrita_amb_l_exists_d_experiences(migrator_db):
    rows = fetch_all(migrator_db, "SELECT policyname, with_check FROM pg_policies "
                                  "WHERE schemaname = 'refuges' AND tablename = 'refuge_media' "
                                  "AND policyname = 'media_insert'")
    assert len(rows) == 1
    check = rows[0][1]
    assert 'experience_id IS NULL' in check and 'EXISTS' in check and 'activity.experiences' in check
    assert 'creator_uid' in check and "'visible'" in check


def test_les_altres_politiques_de_media_no_canvien(migrator_db):
    names = {r[0] for r in fetch_all(migrator_db, "SELECT policyname FROM pg_policies "
                                                  "WHERE schemaname = 'refuges' AND tablename = 'refuge_media'")}
    assert names == {'media_select', 'media_insert', 'media_update', 'media_delete'}
