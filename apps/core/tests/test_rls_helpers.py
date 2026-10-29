"""Helper de polítiques RLS (macros {U}/{ADM}/{SYS}) — SQL pur, sense BD."""
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.rls]


def test_expand_macros_expandeix_els_tres():
    from apps.core.rls import expand_macros
    assert expand_macros('uid = {U} OR {ADM} OR {SYS}') == \
        'uid = (SELECT core.uid()) OR (SELECT core.is_admin()) OR (SELECT core.is_system())'


def test_expand_macros_repetits_i_sense_macros():
    from apps.core.rls import expand_macros
    assert expand_macros('{U} = {U}') == '(SELECT core.uid()) = (SELECT core.uid())'
    assert expand_macros('true') == 'true'


def test_expand_macros_desconeguda_falla():
    from apps.core.rls import expand_macros
    with pytest.raises(ValueError):
        expand_macros('uid = {X}')


def test_create_policy_sql_select():
    from apps.core.rls import create_policy_sql
    sql = create_policy_sql('users_select', 'users.users', 'SELECT', using='uid = {U} OR {ADM} OR {SYS}')
    assert sql.startswith('CREATE POLICY users_select ON users.users FOR SELECT TO app')
    assert 'USING (uid = (SELECT core.uid()) OR (SELECT core.is_admin()) OR (SELECT core.is_system()))' in sql
    assert 'WITH CHECK' not in sql
    assert '{' not in sql


def test_create_policy_sql_insert_i_update():
    from apps.core.rls import create_policy_sql
    ins = create_policy_sql('t_ins', 'users.t', 'INSERT', with_check='{ADM} OR {SYS}')
    assert 'FOR INSERT TO app' in ins and 'WITH CHECK ((SELECT core.is_admin()) OR (SELECT core.is_system()))' in ins
    upd = create_policy_sql('t_upd', 'users.t', 'UPDATE', using='{U} IS NOT NULL', with_check='{SYS}')
    assert 'USING ((SELECT core.uid()) IS NOT NULL)' in upd and 'WITH CHECK ((SELECT core.is_system()))' in upd


def test_create_policy_sql_validacions():
    from apps.core.rls import create_policy_sql
    with pytest.raises(ValueError):
        create_policy_sql('p', 'users.t', 'TRUNCATE', using='true')
    with pytest.raises(ValueError):
        create_policy_sql('p', 'users.t', 'INSERT', using='true')          # INSERT no admet USING
    with pytest.raises(ValueError):
        create_policy_sql('p', 'users.t', 'SELECT', with_check='true')     # SELECT no admet WITH CHECK
    with pytest.raises(ValueError):
        create_policy_sql('p', 'users.t', 'SELECT')                        # cal alguna expressió


@pytest.mark.parametrize('nom', ['x; DROP TABLE a', 'a b', '', "n'x"])
def test_create_policy_sql_rebutja_identificadors_perillosos(nom):
    from apps.core.rls import create_policy_sql
    with pytest.raises(ValueError):
        create_policy_sql(nom, 'users.t', 'SELECT', using='true')
    with pytest.raises(ValueError):
        create_policy_sql('ok', nom, 'SELECT', using='true')


def test_drop_policy_sql():
    from apps.core.rls import drop_policy_sql
    assert drop_policy_sql('users_select', 'users.users') == 'DROP POLICY IF EXISTS users_select ON users.users'


def test_rls_context_reexportat_des_de_domain_core():
    import apps.core as core
    from apps.core import rls
    assert core.rls_context is rls.rls_context
    assert core.system_context is rls.system_context
