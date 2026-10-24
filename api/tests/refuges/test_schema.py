"""
Esquema físic del chunk 2 (docs/design/postgres-schema.md §2.1, §2.2, §2.5-2.8, §4.1, §6, §7.2):
taules, constraints, índexs, FK reals amb `ON DELETE` del DDL, RLS activada, grants i propietari.

Es consulta el catàleg amb el propietari (`migrator`); el comportament de les restriccions i de les polítiques
es prova a `test_constraints.py` i `test_rls.py` amb el rol `app`.
"""
import pytest

from api.tests.conftest import fetch_all, fetch_one
from api.tests.refuges.helpers import AMENITY_FIELDS, account_models

pytestmark = [pytest.mark.db_infra, pytest.mark.integration]

REFUGE_TABLES = ['refuges.refuges', 'refuges.refuge_amenities', 'refuges.refuge_links', 'refuges.refuge_media']
ACCOUNT_TABLES = ['users.users', 'users.user_public_profiles']
ALL_TABLES = REFUGE_TABLES + ACCOUNT_TABLES


def _cols(conn, schema, table):
    rows = fetch_all(conn, """
        SELECT column_name, data_type, udt_name, is_nullable, column_default, character_maximum_length
          FROM information_schema.columns WHERE table_schema = %s AND table_name = %s""", [schema, table])
    return {r[0]: r for r in rows}


# ---------- Migracions ----------

@pytest.mark.parametrize('app', ['accounts', 'refuges'])
def test_migracions_0001_aplicades_pel_migrator(migrator_db, app):
    """`accounts.0001` (users + perfils) es crea al chunk 2 perquè `refuge_media.creator_uid` hi depèn (§6.2)."""
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = %s AND name LIKE '0001%%'",
                     [app])[0] == 1


def test_apps_declarades_com_a_domain(settings):
    assert 'apps.accounts' in settings.INSTALLED_APPS
    assert 'apps.refuges' in settings.INSTALLED_APPS


def test_la_migracio_de_refuges_depen_d_accounts():
    from django.db.migrations.loader import MigrationLoader
    loader = MigrationLoader(None, ignore_no_migrations=True)
    nodes = [k for k in loader.graph.node_map if k[0] == 'refuges' and k[1].startswith('0001')]
    assert nodes, 'cal una migració `refuges.0001_*`'
    parents = loader.graph.node_map[nodes[0]].parents
    assert any(app == 'accounts' for app, _ in parents)


def test_models_i_migracions_sincronitzats():
    """`makemigrations --check`: cap canvi de model pendent de migrar."""
    from django.core.management import call_command
    try:
        call_command('makemigrations', 'accounts', 'refuges', check=True, dry_run=True, verbosity=0)
    except SystemExit as exc:
        pytest.fail(f'models i migracions desincronitzats (exit {exc.code})')


# ---------- Taules, propietari, RLS ----------

@pytest.mark.parametrize('table', ALL_TABLES)
def test_taula_amb_rls_activada_sense_force_i_propietat_del_migrator(migrator_db, table):
    schema, name = table.split('.')
    row = fetch_one(migrator_db, """
        SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner)
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'""", [schema, name])
    assert row is not None, f'falta la taula {table}'
    assert row == (True, False, 'migrator')


def test_vista_refuge_map_existeix_i_es_del_migrator(migrator_db):
    row = fetch_one(migrator_db, """
        SELECT pg_get_userbyid(c.relowner), c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'refuges' AND c.relname = 'refuge_map'""")
    assert row == ('migrator', 'v')
    assert set(_cols(migrator_db, 'refuges', 'refuge_map')) == {'id', 'name', 'lat', 'lng', 'geohash', 'coord'}


@pytest.mark.parametrize('table,expected', [
    ('refuges.refuges', {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('refuges.refuge_amenities', {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('refuges.refuge_links', {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('refuges.refuge_media', {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('refuges.refuge_map', {'SELECT'}),
    ('users.users', {'SELECT', 'INSERT', 'UPDATE', 'DELETE'}),
    ('users.user_public_profiles', {'SELECT', 'INSERT', 'UPDATE'}),       # esborrat només per cascada
])
def test_matriu_de_grants_del_rol_app(app_db, table, expected):
    """§7.2: mínim privilegi. `app` mai té TRUNCATE, REFERENCES ni TRIGGER."""
    privs = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER')
    got = {p for p in privs if fetch_one(app_db, f"SELECT has_table_privilege('app', %s, '{p}')", [table])[0]}
    assert got == expected


# ---------- Columnes ----------

def test_columnes_de_refuges(migrator_db):
    c = _cols(migrator_db, 'refuges', 'refuges')
    assert set(c) == {'id', 'name', 'surname', 'type', 'coord', 'altitude', 'places', 'remarque', 'description',
                      'region', 'departement', 'modified_at', 'condition', 'num_contributed_conditions',
                      'condition_reset_at', 'created_at'}
    assert c['id'][2] == 'uuid' and c['id'][3] == 'NO'
    assert c['coord'][2] == 'geography' and c['coord'][3] == 'NO'
    assert c['condition'][2] == 'float8' and c['condition'][3] == 'YES'
    assert c['num_contributed_conditions'][2] == 'int4' and c['num_contributed_conditions'][3] == 'NO'
    assert c['num_contributed_conditions'][4] == '0'
    assert c['modified_at'][2] == 'date' and c['modified_at'][3] == 'YES'
    assert c['condition_reset_at'][2] == 'timestamptz'
    assert c['created_at'][2] == 'timestamptz' and c['created_at'][3] == 'NO'
    assert c['name'][5] == 255 and c['type'][5] == 64
    assert c['places'][3] == 'YES' and c['altitude'][3] == 'YES'
    assert c['remarque'][3] == 'NO' and c['description'][3] == 'NO'
    assert c['region'][3] == 'YES' and c['departement'][3] == 'YES' and c['surname'][3] == 'YES'
    assert 'non gardé' in c['type'][4]


def test_les_pk_uuid_no_tenen_default_de_bd(migrator_db):
    """§1.4: els uuid v7 els genera l'aplicació (`uuid7()`); la columna no té DEFAULT."""
    assert _cols(migrator_db, 'refuges', 'refuges')['id'][4] is None
    assert _cols(migrator_db, 'refuges', 'refuge_links')['id'][4] is None


def test_columnes_d_amenities(migrator_db):
    c = _cols(migrator_db, 'refuges', 'refuge_amenities')
    assert set(c) == {'refuge_id', *AMENITY_FIELDS}
    for f in AMENITY_FIELDS:
        assert (c[f][2], c[f][3], c[f][4]) == ('bool', 'NO', 'false'), f


def test_columnes_de_links(migrator_db):
    c = _cols(migrator_db, 'refuges', 'refuge_links')
    assert set(c) == {'id', 'refuge_id', 'position', 'url'}
    assert c['position'][2] == 'int2' and c['url'][2] == 'text'


def test_columnes_de_media_sense_experience_id_encara(migrator_db):
    """`experience_id` (i la FK cap a `activity.experiences`) arriba al chunk 7 amb `refuges.0002` (§6.2)."""
    c = _cols(migrator_db, 'refuges', 'refuge_media')
    assert set(c) == {'key', 'refuge_id', 'creator_uid', 'media_type', 'content_type', 'status', 'uploaded_at',
                      'taken_at', 'width', 'height', 'size_bytes', 'thumb_key', 'blurhash', 'rights_confirmed_at'}
    assert c['key'][2] == 'text' and c['creator_uid'][5] == 128 and c['media_type'][5] == 5
    assert c['status'][4].startswith("'visible'")
    assert c['rights_confirmed_at'][3] == 'NO' and c['size_bytes'][2] == 'int8'


def test_columnes_d_accounts(migrator_db):
    u = _cols(migrator_db, 'users', 'users')
    assert set(u) == {'uid', 'language', 'created_at', 'age_confirmed_at', 'age_threshold', 'moderation_strikes',
                      'is_blocked', 'blocked_reason', 'blocked_at'}
    assert u['uid'][5] == 128 and u['language'][4].startswith("'ca'")
    p = _cols(migrator_db, 'users', 'user_public_profiles')
    assert set(p) == {'uid', 'username', 'avatar_key', 'avatar_thumb_key', 'avatar_content_type', 'avatar_width',
                      'avatar_height', 'avatar_size_bytes', 'avatar_blurhash', 'avatar_uploaded_at', 'updated_at'}


# ---------- Constraints i índexs pel nom que fixa el disseny ----------

@pytest.mark.parametrize('name', [
    'refuges_condition_ck', 'refuges_condition_n_ck', 'refuges_name_ck', 'refuges_surname_ck', 'refuges_type_ck',
    'refuges_altitude_ck', 'refuges_places_ck', 'refuges_coord_ck'])
def test_constraints_de_refuges_amb_el_nom_del_disseny(migrator_db, name):
    row = fetch_one(migrator_db, "SELECT contype FROM pg_constraint WHERE conname = %s "
                                 "AND conrelid = 'refuges.refuges'::regclass", [name])
    assert row == ('c',)


@pytest.mark.parametrize('name,method,needle', [
    ('refuges_coord_gist', 'gist', 'coord'),
    ('refuges_name_trgm_gin', 'gin', 'norm_name'),
    ('refuges_surname_trgm_gin', 'gin', 'norm_name'),
    ('refuges_type_idx', 'btree', 'type'),
    ('refuges_places_idx', 'btree', 'places'),
    ('refuges_altitude_idx', 'btree', 'altitude'),
])
def test_index_de_refuges(migrator_db, name, method, needle):
    row = fetch_one(migrator_db, "SELECT indexdef FROM pg_indexes WHERE schemaname = 'refuges' AND indexname = %s",
                    [name])
    assert row is not None, f"falta l'índex {name}"
    assert f'USING {method}' in row[0] and needle in row[0]


def test_index_trigram_amb_gin_trgm_ops_i_parcial_del_surname(migrator_db):
    name = fetch_one(migrator_db, "SELECT indexdef FROM pg_indexes WHERE indexname = 'refuges_name_trgm_gin'")[0]
    sur = fetch_one(migrator_db, "SELECT indexdef FROM pg_indexes WHERE indexname = 'refuges_surname_trgm_gin'")[0]
    assert 'gin_trgm_ops' in name and 'core.norm_name' in name
    assert 'gin_trgm_ops' in sur and 'surname IS NOT NULL' in sur


def test_no_es_crea_index_sobre_la_condicio_arrodonida(migrator_db):
    """§2.5: amb ~1,5 mil files l'avaluació de `round_half_even(condition)` és negligible."""
    rows = fetch_all(migrator_db, "SELECT indexdef FROM pg_indexes WHERE schemaname = 'refuges' "
                                  "AND indexdef ILIKE '%%round_half_even%%'")
    assert rows == []


def test_indexs_parcials_de_places_i_altitud(migrator_db):
    for name, col in (('refuges_places_idx', 'places'), ('refuges_altitude_idx', 'altitude')):
        d = fetch_one(migrator_db, "SELECT indexdef FROM pg_indexes WHERE indexname = %s", [name])[0]
        assert f'{col} IS NOT NULL' in d


def test_index_de_media_per_refugi_i_per_creador(migrator_db):
    defs = [r[0] for r in fetch_all(migrator_db, "SELECT indexdef FROM pg_indexes "
                                                  "WHERE tablename = 'refuge_media' AND schemaname = 'refuges'")]
    assert any('(refuge_id, uploaded_at, key)' in d for d in defs), defs
    assert any('(creator_uid, uploaded_at)' in d for d in defs), defs
    thumb = [d for d in defs if 'thumb_key' in d]
    assert thumb and 'UNIQUE' in thumb[0] and 'thumb_key IS NOT NULL' in thumb[0]


# ---------- FK reals: ON DELETE del DDL, DEFERRABLE INITIALLY DEFERRED (§6.3) ----------

def _fk(conn, table, column):
    rows = fetch_all(conn, """
        SELECT c.confdeltype, c.condeferrable, c.condeferred, c.confrelid::regclass::text,
               (SELECT array_agg(a.attname::text) FROM unnest(c.conkey) k JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k)
          FROM pg_constraint c WHERE c.contype = 'f' AND c.conrelid = %s::regclass""", [table])
    return [r for r in rows if r[4] == [column]]


@pytest.mark.parametrize('table,column,target', [
    ('refuges.refuge_amenities', 'refuge_id', 'refuges.refuges'),
    ('refuges.refuge_links', 'refuge_id', 'refuges.refuges'),
    ('refuges.refuge_media', 'refuge_id', 'refuges.refuges'),
    ('refuges.refuge_media', 'creator_uid', 'users.users'),
    ('users.user_public_profiles', 'uid', 'users.users'),
])
def test_fk_real_amb_on_delete_cascade_diferible(migrator_db, table, column, target):
    fks = _fk(migrator_db, table, column)
    assert len(fks) == 1, f'falta la FK {table}.{column} (db_constraint=False + RunSQL, §6.3)'
    deltype, deferrable, deferred, ref, _ = fks[0]
    assert (deltype, deferrable, deferred, ref) == ('c', True, True, target)


def test_unique_de_links_refuge_position_diferible_i_refuge_url(migrator_db):
    rows = fetch_all(migrator_db, """
        SELECT c.condeferrable, c.condeferred,
               (SELECT array_agg(a.attname::text ORDER BY k.ord)
                  FROM unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum)
          FROM pg_constraint c WHERE c.contype = 'u' AND c.conrelid = 'refuges.refuge_links'::regclass""")
    by_cols = {tuple(r[2]): r for r in rows}
    assert ('refuge_id', 'position') in by_cols and ('refuge_id', 'url') in by_cols
    assert by_cols[('refuge_id', 'position')][:2] == (True, True), \
        'UNIQUE (refuge, position) DEFERRABLE INITIALLY DEFERRED'


def test_extensions_necessaries(migrator_db):
    ext = {r[0] for r in fetch_all(migrator_db, 'SELECT extname FROM pg_extension')}
    assert {'postgis', 'pg_trgm', 'unaccent', 'btree_gist'} <= ext


# ---------- Models Django: noms de taula amb cometes (§1.5) i vista no gestionada ----------

def test_db_table_dels_models_porta_el_schema_entre_cometes(RM):
    assert RM.Refuge._meta.db_table == 'refuges"."refuges'
    assert RM.RefugeAmenities._meta.db_table == 'refuges"."refuge_amenities'
    assert RM.RefugeLink._meta.db_table == 'refuges"."refuge_links'
    assert RM.RefugeMedia._meta.db_table == 'refuges"."refuge_media'
    assert RM.RefugeMapPoint._meta.db_table == 'refuges"."refuge_map'
    assert RM.RefugeMapPoint._meta.managed is False


def test_db_table_dels_models_d_accounts():
    am = account_models()
    assert am.UserAccount._meta.db_table == 'users"."users'
    assert am.UserPublicProfile._meta.db_table == 'users"."user_public_profiles'
    assert am.UserAccount._meta.pk.name == 'uid'
    assert am.UserPublicProfile._meta.pk.name == 'user'
    assert am.UserPublicProfile._meta.pk.column == 'uid'


def test_les_fk_dels_models_son_do_nothing_sense_constraint_de_django(RM):
    """§6.3: les cascades són del DDL; Django 5.1 les emularia des del rol `app` (subjecte a RLS)."""
    from django.db import models
    for model, field in ((RM.RefugeAmenities, 'refuge'), (RM.RefugeLink, 'refuge'), (RM.RefugeMedia, 'refuge'),
                         (RM.RefugeMedia, 'creator')):
        f = model._meta.get_field(field)
        assert f.remote_field.on_delete is models.DO_NOTHING, f'{model.__name__}.{field}'
        assert f.db_constraint is False, f'{model.__name__}.{field}'
