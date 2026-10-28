"""
RLS de `audit.audit_logs` amb el rol `app` (§2.24, §7.5): anònim, propi, aliè, admin i sistema.

- `SELECT`: l'actor (`actor_uid = {U}`), l'admin o el sistema. (L'`INSERT … RETURNING` de Django també passa per aquesta
  política.)
- `INSERT`: `actor_uid = {U}` o sistema: no es pot falsificar un actor ni escriure com a «sistema» (`actor_uid` NULL) sense
  `{SYS}`.
- `UPDATE`: ningú, ni el sistema (registre immutable: sense privilegi). `DELETE`: només el sistema (purga).
Un `INSERT` denegat per la RLS llança error; un `SELECT`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.moderation.tests.helpers import audit_rows, sql

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ALL_CTX = {'anon': {}, 'own': {'uid': 'u1'}, 'other': {'uid': 'u2'}, 'admin': {'uid': 'adm', 'is_admin': True},
           'system': {'system': True}}


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


def seed(actor='u1', action='media.report', **extra):
    cols = ['actor_uid', 'action'] + list(extra)
    sql(f'INSERT INTO audit.audit_logs ({", ".join(cols)}) VALUES ({", ".join(["%s"] * len(cols))})',
        [actor, action, *extra.values()])


def _no_privilege(fn):
    """Denegat per falta de privilegi (`insufficient_privilege`, 42501), no per qualsevol altre error."""
    with pytest.raises(DatabaseError) as err:
        with transaction.atomic():
            fn()
    assert getattr(err.value.__cause__, 'sqlstate', None) == '42501', err.value


@pytest.mark.parametrize('ctx,sees', [('anon', False), ('own', True), ('other', False), ('admin', True),
                                      ('system', True)])
def test_select(world, ctx, sees):
    seed('u1')
    assert (len(_run(ctx, 'SELECT id FROM audit.audit_logs')) == 1) is sees


def test_les_files_del_sistema_nomes_les_veu_l_admin_o_el_sistema(world):
    seed(None, 'moderation.auto_hide')
    assert _run('own', 'SELECT id FROM audit.audit_logs') == []
    assert len(_run('admin', 'SELECT id FROM audit.audit_logs')) == 1
    assert len(_run('system', 'SELECT id FROM audit.audit_logs')) == 1


INSERT_AS = "INSERT INTO audit.audit_logs (actor_uid, action) VALUES (%s, 'media.report')"


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', True), ('other', False), ('admin', False),
                                    ('system', True)])
def test_insert_com_a_u1(world, ctx, ok):
    if ok:
        _run(ctx, INSERT_AS, ['u1'])
    else:
        _denied(lambda: _run(ctx, INSERT_AS, ['u1']))
    assert len(audit_rows()) == (1 if ok else 0)


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', False),
                                    ('system', True)])
def test_insert_com_a_sistema_actor_null_nomes_amb_system(world, ctx, ok):
    stmt = "INSERT INTO audit.audit_logs (actor_uid, action) VALUES (NULL, 'moderation.auto_hide')"
    if ok:
        _run(ctx, stmt)
    else:
        _denied(lambda: _run(ctx, stmt))
    assert len(audit_rows()) == (1 if ok else 0)


def test_un_usuari_pot_escriure_amb_subject_uid_d_un_altre(world):
    """`subject_uid` és l'afectat: no es comprova; només l'actor ha de ser el propi."""
    _run('own', "INSERT INTO audit.audit_logs (actor_uid, subject_uid, action) VALUES ('u1', 'u2', 'user.age_confirmed')")
    assert audit_rows()[0]['subject_uid'] == 'u2'


@pytest.mark.parametrize('ctx', list(ALL_CTX))
def test_cap_update_ni_el_sistema(world, ctx):
    seed('u1')
    _no_privilege(lambda: _run(ctx, "UPDATE audit.audit_logs SET action = 'media.delete'"))
    _no_privilege(lambda: _run(ctx, 'UPDATE audit.audit_logs SET legal_hold = true'))
    assert audit_rows()[0]['action'] == 'media.report'


@pytest.mark.parametrize('ctx,ok', [('anon', False), ('own', False), ('other', False), ('admin', False),
                                    ('system', True)])
def test_delete_nomes_sistema(world, ctx, ok):
    seed('u1')
    assert _run(ctx, 'DELETE FROM audit.audit_logs') == (1 if ok else 0)
    assert len(audit_rows()) == (0 if ok else 1)


def test_sense_context_tot_invisible_i_no_escrivible(world):
    seed('u1')
    with connection.cursor() as cur:
        cur.execute('SELECT id FROM audit.audit_logs')
        assert cur.fetchall() == []
