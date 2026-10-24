"""Mínim privilegi del rol `app` després de `core.0001` (§7.1-7.2): es prova de debò amb el rol de l'aplicació."""
import pytest
from django.db import DatabaseError, transaction

from api.tests.conftest import fetch_all, fetch_one

pytestmark = [pytest.mark.db_infra, pytest.mark.rls]

SCHEMAS = ('core', 'refuges', 'users', 'activity', 'proposals', 'moderation', 'audit', 'public')
FUNCS = ('uid()', 'is_admin()', 'is_system()', 'immutable_unaccent(text)', 'norm_name(text)',
         'round_half_even(double precision)')


def _ha_de_fallar(conn, sql):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            with conn.cursor() as cur:
                cur.execute(sql)


def _public_te_execute(acl):
    """`proacl` en text (`{a=X/b,...}`): una entrada sense rol davant (`=X/`) és PUBLIC."""
    return any(item.startswith('=') for item in acl.strip('{}').split(','))


def test_app_no_te_atributs_privilegiats(app_db):
    row = fetch_one(app_db, "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication "
                            "FROM pg_roles WHERE rolname = current_user")
    assert row == (False, False, False, False, False)


def test_app_no_es_propietari_de_cap_objecte(app_db):
    oid = "(SELECT oid FROM pg_roles WHERE rolname = 'app')"
    assert fetch_one(app_db, f"SELECT count(*) FROM pg_class WHERE relowner = {oid}")[0] == 0
    assert fetch_one(app_db, f"SELECT count(*) FROM pg_proc WHERE proowner = {oid}")[0] == 0
    assert fetch_one(app_db, f"SELECT count(*) FROM pg_namespace WHERE nspowner = {oid}")[0] == 0


@pytest.mark.parametrize('schema', SCHEMAS)
def test_app_no_pot_crear_objectes_als_schemas(app_db, schema):
    assert fetch_one(app_db, "SELECT has_schema_privilege('app', %s, 'CREATE')", [schema])[0] is False
    assert fetch_one(app_db, "SELECT has_schema_privilege('app', %s, 'USAGE')", [schema])[0] is True
    _ha_de_fallar(app_db, f'CREATE TABLE {schema}.intrus (a int)')


@pytest.mark.parametrize('ddl', ['CREATE SCHEMA intrus', 'CREATE ROLE intrus', 'SET ROLE migrator', 'SET ROLE postgres',
                                 'ALTER ROLE app BYPASSRLS', 'ALTER ROLE app SUPERUSER'])
def test_app_no_pot_escalar_privilegis(app_db, ddl):
    assert fetch_one(app_db, "SELECT has_database_privilege('app', current_database(), 'CREATE')")[0] is False
    _ha_de_fallar(app_db, ddl)


def test_app_no_pot_substituir_les_funcions_de_context(app_db):
    _ha_de_fallar(app_db, "CREATE OR REPLACE FUNCTION core.is_admin() RETURNS boolean LANGUAGE sql AS 'SELECT true'")


@pytest.mark.parametrize('sig', FUNCS)
def test_les_funcions_core_no_son_executables_per_public(app_db, sig):
    acl = fetch_one(app_db, "SELECT proacl::text FROM pg_proc WHERE oid = %s::regprocedure", [f'core.{sig}'])[0]
    assert acl is not None and not _public_te_execute(acl), f"PUBLIC no ha de tenir EXECUTE: {acl}"
    assert fetch_one(app_db, "SELECT has_function_privilege('app', %s, 'EXECUTE')", [f'core.{sig}'])[0] is True


def test_funcions_core_security_definer_amb_search_path_fixat(app_db):
    """Si mai n'hi ha, una funció SECURITY DEFINER ha de fixar `search_path` (evita segrest per objectes del cridant)."""
    rows = fetch_all(app_db, "SELECT p.oid::regprocedure::text, p.prosecdef, p.proconfig FROM pg_proc p "
                             "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'core'")
    assert rows
    for name, secdef, config in rows:
        if secdef:
            assert config and any(c.startswith('search_path=') for c in config), f'{name}: sense search_path'


def test_default_privileges_del_migrator_no_donen_execute_a_public(app_db):
    rows = fetch_all(app_db, "SELECT d.defaclacl::text FROM pg_default_acl d JOIN pg_roles r ON r.oid = d.defaclrole "
                             "WHERE r.rolname = 'migrator' AND d.defaclobjtype = 'f' AND d.defaclnamespace = 0")
    assert rows, "falta ALTER DEFAULT PRIVILEGES FOR ROLE migrator REVOKE EXECUTE ... FROM PUBLIC"
    assert not _public_te_execute(rows[0][0])
