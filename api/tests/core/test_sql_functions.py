"""Funcions SQL de `core` (docs/design/postgres-schema.md §2.0) provades amb el rol `app`."""
import pytest
from django.db import transaction, connections
from django.db.utils import ProgrammingError

from api.tests.conftest import fetch_one, fetch_all

pytestmark = [pytest.mark.db_infra]

CORE_FUNCS = ['uid()', 'is_admin()', 'is_system()', 'immutable_unaccent(text)', 'norm_name(text)',
              'round_half_even(double precision)']


def test_les_proves_corren_com_a_rol_app(app_db):
    assert fetch_one(app_db, 'SELECT current_user, session_user') == ('app', 'app')


# ---------- norm_name / immutable_unaccent ----------

@pytest.mark.parametrize('entrada,esperat', [
    ('Refugi d’Àrreu', 'refugi d’arreu'),
    ('ÉLÈVE', 'eleve'),
    ('Çà Ñandú Öl', 'ca nandu ol'),
    ('Cabane de l’Ôrri', 'cabane de l’orri'),
    ('already lower', 'already lower'),
    ('', ''),
])
def test_norm_name(app_db, entrada, esperat):
    assert fetch_one(app_db, 'SELECT core.norm_name(%s)', [entrada])[0] == esperat


def test_norm_name_null_retorna_null(app_db):
    assert fetch_one(app_db, 'SELECT core.norm_name(NULL::text)')[0] is None


def test_immutable_unaccent(app_db):
    assert fetch_one(app_db, 'SELECT core.immutable_unaccent(%s)', ['Àéî ôü ñ'])[0] == 'Aei ou n'
    assert fetch_one(app_db, 'SELECT core.immutable_unaccent(NULL::text)')[0] is None


@pytest.mark.parametrize('func,volatilitat', [
    ('immutable_unaccent', 'i'), ('norm_name', 'i'), ('round_half_even', 'i'),
    ('uid', 's'), ('is_admin', 's'), ('is_system', 's'),
])
def test_volatilitat_de_les_funcions(app_db, func, volatilitat):
    rows = fetch_all(app_db, """
        SELECT p.provolatile, p.proparallel FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'core' AND p.proname = %s""", [func])
    assert len(rows) == 1, f"core.{func} no existeix o està duplicada"
    assert rows[0][0] == volatilitat
    assert rows[0][1] == 's', "PARALLEL SAFE"


def test_norm_name_es_pot_usar_a_un_index_d_expressio(app_db):
    """Si no fos IMMUTABLE, Postgres rebutjaria l'índex (cas real: GIN trgm del nom del refugi)."""
    with pytest.raises(Exception) as exc:
        with transaction.atomic():
            with app_db.cursor() as cur:
                cur.execute('CREATE TEMP TABLE zz_idx (name text) ON COMMIT DROP')
                cur.execute('CREATE INDEX zz_idx_norm ON zz_idx (core.norm_name(name))')
                cur.execute("CREATE INDEX zz_idx_trgm ON zz_idx USING gin (core.norm_name(name) gin_trgm_ops)")
                raise RuntimeError('rollback voluntari')
    assert isinstance(exc.value, RuntimeError), f"CREATE INDEX hauria d'anar bé: {exc.value!r}"


# ---------- round_half_even ----------

@pytest.mark.parametrize('x,esperat', [
    (0.5, 0), (1.5, 2), (2.5, 2), (3.5, 4), (2.6, 3), (2.1, 2), (0.0, 0), (3.0, 3), (0.4999, 0),
    (1.4999, 1), (1.5001, 2), (-0.5, 0), (-1.5, -2), (-2.5, -2), (-2.6, -3),
])
def test_round_half_even_coincideix_amb_round_de_python(app_db, x, esperat):
    got = fetch_one(app_db, 'SELECT core.round_half_even(%s::double precision)', [x])[0]
    assert got == esperat
    assert got == round(x), "ha de coincidir amb el round() de Python 3 que fa el serializer"


def test_round_half_even_null(app_db):
    assert fetch_one(app_db, 'SELECT core.round_half_even(NULL::double precision)')[0] is None


def test_round_half_even_retorna_integer(app_db):
    assert fetch_one(app_db, 'SELECT pg_typeof(core.round_half_even(1.5::double precision))::text')[0] == 'integer'


# ---------- funcions de context sense context (fail-closed) ----------

def test_funcions_de_context_sense_context(app_db):
    assert fetch_one(app_db, 'SELECT core.uid(), core.is_admin(), core.is_system()') == (None, False, False)


def test_uid_buit_es_null(app_db):
    with transaction.atomic():
        with app_db.cursor() as cur:
            cur.execute("SELECT set_config('app.uid', '', true)")
            cur.execute('SELECT core.uid()')
            assert cur.fetchone()[0] is None


@pytest.mark.parametrize('valor,esperat', [('true', True), ('false', False), ('', False), ('TRUE', False), ('1', False)])
def test_is_admin_nomes_accepta_true_exacte(app_db, valor, esperat):
    with transaction.atomic():
        with app_db.cursor() as cur:
            cur.execute("SELECT set_config('app.is_admin', %s, true), set_config('app.is_system', %s, true)",
                        [valor, valor])
            cur.execute('SELECT core.is_admin(), core.is_system()')
            assert cur.fetchone() == (esperat, esperat)


# ---------- propietat i privilegis ----------

@pytest.mark.parametrize('sig', CORE_FUNCS)
def test_app_pot_executar_les_funcions_core(app_db, sig):
    assert fetch_one(app_db, "SELECT has_function_privilege('app', %s, 'EXECUTE')", [f'core.{sig}'])[0] is True


@pytest.mark.parametrize('sig', CORE_FUNCS)
def test_funcions_core_son_del_migrator_i_no_de_public(app_db, sig):
    owner = fetch_one(app_db, "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid = %s::regprocedure",
                      [f'core.{sig}'])[0]
    assert owner == 'migrator'
    grantees = [r[0] for r in fetch_all(app_db, """
        SELECT a.grantee FROM pg_proc p, LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
        WHERE p.oid = %s::regprocedure AND a.privilege_type = 'EXECUTE'""", [f'core.{sig}'])]
    assert 0 not in grantees, f"PUBLIC (grantee 0) té EXECUTE a core.{sig}"


def test_funcio_nova_del_migrator_no_es_executable_per_public_ni_app(migrator_db):
    """`ALTER DEFAULT PRIVILEGES FOR ROLE migrator REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` (§7.1)."""
    class Rollback(Exception):
        pass
    try:
        with transaction.atomic(using='migrator'):
            with migrator_db.cursor() as cur:
                cur.execute("CREATE FUNCTION core.zz_probe() RETURNS int LANGUAGE sql AS 'SELECT 1'")
                cur.execute("SELECT has_function_privilege('app', 'core.zz_probe()', 'EXECUTE')")
                assert cur.fetchone()[0] is False
                cur.execute("""SELECT count(*) FROM pg_proc p,
                               LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
                               WHERE p.oid = 'core.zz_probe()'::regprocedure AND a.grantee = 0""")
                assert cur.fetchone()[0] == 0
            raise Rollback
    except Rollback:
        pass


# ---------- schemas ----------

SCHEMES = ['core', 'refuges', 'users', 'activity', 'proposals', 'moderation', 'audit']


@pytest.mark.parametrize('schema', SCHEMES)
def test_schema_existeix_i_es_del_migrator(app_db, schema):
    row = fetch_one(app_db, "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = %s", [schema])
    assert row is not None, f"schema {schema} no existeix (core.0001 no aplicada?)"
    assert row[0] == 'migrator'


@pytest.mark.parametrize('schema', SCHEMES)
def test_app_te_usage_pero_no_create_als_schemas(app_db, schema):
    usage, create = fetch_one(app_db, "SELECT has_schema_privilege('app', %s, 'USAGE'), "
                                      "has_schema_privilege('app', %s, 'CREATE')", [schema, schema])
    assert usage is True
    assert create is False


@pytest.mark.parametrize('schema', SCHEMES)
def test_app_no_pot_crear_taules_als_schemas_de_domini(app_db, schema):
    with pytest.raises(ProgrammingError) as exc:
        with transaction.atomic():
            with app_db.cursor() as cur:
                cur.execute(f'CREATE TABLE {schema}.zz_no_hauria_d_existir (id int)')
    assert getattr(exc.value.__cause__, 'sqlstate', None) == '42501'


def test_app_no_pot_crear_schemas_ni_extensions(app_db):
    with pytest.raises(Exception) as e1:
        with transaction.atomic():
            with app_db.cursor() as cur:
                cur.execute('CREATE SCHEMA zz_app_schema')
    assert getattr(e1.value.__cause__, 'sqlstate', None) == '42501'
    with pytest.raises(Exception):
        with transaction.atomic():
            with app_db.cursor() as cur:
                cur.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')


# ---------- rols ----------

def test_app_no_es_superusuari_ni_bypassrls(app_db):
    row = fetch_one(app_db, "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin "
                            "FROM pg_roles WHERE rolname = 'app'")
    assert row == (False, False, False, False, False, True)


def test_migrator_no_es_superusuari_ni_bypassrls(migrator_db):
    row = fetch_one(migrator_db, "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
                                 "FROM pg_roles WHERE rolname = 'migrator'")
    assert row == (False, False, False, False)
    assert fetch_one(migrator_db, 'SELECT current_user')[0] == 'migrator'


def test_timeouts_del_rol_app(app_db):
    assert fetch_one(app_db, 'SHOW statement_timeout')[0] == '20s'
    assert fetch_one(app_db, 'SHOW lock_timeout')[0] == '5s'
    assert fetch_one(app_db, 'SHOW idle_in_transaction_session_timeout')[0] == '30s'


def test_extensions_instal_lades_pel_superusuari(app_db):
    names = {r[0] for r in fetch_all(app_db, 'SELECT extname FROM pg_extension')}
    assert {'postgis', 'pg_trgm', 'unaccent', 'btree_gist'} <= names


def test_app_no_es_propietari_de_cap_objecte_de_domini(app_db):
    rows = fetch_all(app_db, """
        SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s) AND c.relowner = (SELECT oid FROM pg_roles WHERE rolname = 'app')""", [SCHEMES])
    assert rows == []
    assert fetch_one(app_db, "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                             "WHERE n.nspname = ANY(%s) AND p.proowner = (SELECT oid FROM pg_roles WHERE rolname='app')",
                     [SCHEMES])[0] == 0


# ---------- migracions ----------

def test_migracions_aplicades_pel_migrator(migrator_db):
    assert fetch_one(migrator_db, "SELECT tableowner FROM pg_tables WHERE tablename = 'django_migrations'")[0] == 'migrator'
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'core'")[0] >= 1
    assert fetch_one(migrator_db, "SELECT count(*) FROM django_migrations WHERE app = 'core' AND name LIKE '0001%%'")[0] == 1
