"""
RLS de `activity.doubts` i `activity.answers` amb el rol `app` (§2.16, §2.17, §7.5): anònim, propi, aliè, admin i sistema.

- `SELECT`: públic (`USING (true)`), també sense context.
- `INSERT`: només `creator_uid = {U}` o sistema (l'admin NO pot inserir en nom d'un altre).
- `DELETE`: el creador, l'admin o el sistema (C1 també a la BD). El creador del dubte NO pot esborrar les respostes dels altres.
- Cap `UPDATE` ni `TRUNCATE` (no hi ha grant).
- Les cascades (FK `ON DELETE CASCADE`) NO estan subjectes a la RLS.

Un `INSERT` denegat per la RLS llança error; un `SELECT`/`DELETE` denegat afecta 0 files.
"""
import pytest
from django.db import DatabaseError, connection, transaction

from apps.core.rls import rls_context
from apps.doubts.tests.helpers import answer_ids, build_tree, doubt_ids, make_answer, make_doubt, make_refuge, make_user

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.rls, pytest.mark.integration,
              pytest.mark.real_permissions]

ANON = {}
OWN = {'uid': 'u1'}
OTHER = {'uid': 'u2'}
ADMIN = {'uid': 'adm', 'is_admin': True}
SYSTEM = {'system': True}
ALL_CTX = {'anon': ANON, 'own': OWN, 'other': OTHER, 'admin': ADMIN, 'system': SYSTEM}
# Qui pot esborrar les files de `u1`
CAN_DELETE = {'anon': False, 'own': True, 'other': False, 'admin': True, 'system': True}
# Qui pot inserir files amb creator_uid = 'u1'
CAN_INSERT_AS_U1 = {'anon': False, 'own': True, 'other': False, 'admin': False, 'system': True}


@pytest.fixture
def world():
    for uid in ('u1', 'u2', 'u3', 'adm'):
        make_user(uid)
    return make_refuge()


def _run(ctx, statement, params=None):
    with rls_context(**ALL_CTX[ctx]):
        with connection.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else cur.rowcount


def _denied(fn):
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            fn()


# =================================== SELECT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_select_public_per_a_tothom_inclos_anonim(world, ctx):
    d = make_doubt(world, 'u1')
    make_answer(d, 'u2')
    assert _run(ctx, 'SELECT count(*) FROM activity.doubts')[0][0] == 1
    assert _run(ctx, 'SELECT count(*) FROM activity.answers')[0][0] == 1


def test_select_sense_cap_context_tambe_funciona(world):
    d = make_doubt(world, 'u1')
    make_answer(d, 'u2')
    with connection.cursor() as cur:
        cur.execute('SELECT (SELECT count(*) FROM activity.doubts), (SELECT count(*) FROM activity.answers)')
        assert cur.fetchone() == (1, 1)


# =================================== INSERT ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_de_dubte_amb_creator_u1(world, ctx):
    def go():
        _run(ctx, 'INSERT INTO activity.doubts (refuge_id, creator_uid, message) VALUES (%s, %s, %s)',
             [world.pk, 'u1', 'hola'])
    if CAN_INSERT_AS_U1[ctx]:
        go()
        assert len(doubt_ids()) == 1
    else:
        _denied(go)
        assert doubt_ids() == []


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_insert_de_resposta_amb_creator_u1(world, ctx):
    d = make_doubt(world, 'u2')

    def go():
        _run(ctx, 'INSERT INTO activity.answers (doubt_id, creator_uid, message) VALUES (%s, %s, %s)',
             [d, 'u1', 'hola'])
    if CAN_INSERT_AS_U1[ctx]:
        go()
        assert len(answer_ids(d)) == 1
    else:
        _denied(go)
        assert answer_ids(d) == []


def test_l_admin_si_pot_inserir_en_nom_propi(world):
    _run('admin', 'INSERT INTO activity.doubts (refuge_id, creator_uid, message) VALUES (%s, %s, %s)',
         [world.pk, 'adm', 'consulta de l\'admin'])
    assert len(doubt_ids()) == 1


def test_insert_amb_returning_i_default_de_la_bd_sota_rls(world):
    rows = _run('own', 'INSERT INTO activity.doubts (refuge_id, creator_uid, message) VALUES (%s, %s, %s) '
                       'RETURNING id, created_at', [world.pk, 'u1', 'x'])
    assert len(rows) == 1 and rows[0][0] is not None and rows[0][1] is not None


def test_insert_sense_context_es_denegat_fail_closed(world):
    make_doubt(world, 'u1')                                   # la taula ha d'existir: si no, el test passaria per error
    _denied(lambda: _exec('INSERT INTO activity.doubts (refuge_id, creator_uid, message) VALUES (%s, %s, %s)',
                          [world.pk, 'u1', 'x']))


def _exec(statement, params=None):
    with connection.cursor() as cur:
        cur.execute(statement, params)


# =================================== DELETE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_d_un_dubte_de_u1(world, ctx):
    d = make_doubt(world, 'u1')
    n = _run(ctx, 'DELETE FROM activity.doubts WHERE id = %s', [d])
    assert n == (1 if CAN_DELETE[ctx] else 0)
    assert doubt_ids() == ([] if CAN_DELETE[ctx] else [d])


@pytest.mark.parametrize('ctx', ALL_CTX)
def test_delete_d_una_resposta_de_u1(world, ctx):
    d = make_doubt(world, 'u2')
    a = make_answer(d, 'u1')
    n = _run(ctx, 'DELETE FROM activity.answers WHERE id = %s', [a])
    assert n == (1 if CAN_DELETE[ctx] else 0)
    assert answer_ids(d) == ([] if CAN_DELETE[ctx] else [a])


def test_el_creador_del_dubte_no_pot_esborrar_la_resposta_d_un_altre(world):
    d = make_doubt(world, 'u1')
    a = make_answer(d, 'u2')
    assert _run('own', 'DELETE FROM activity.answers WHERE id = %s', [a]) == 0
    assert answer_ids(d) == [a]


def test_el_creador_del_dubte_si_l_esborra_amb_les_respostes_alienes_per_cascada(world):
    """La cascada de la FK no passa per la RLS: `u1` no pot esborrar la resposta de `u2`, però sí el dubte que la conté."""
    d = make_doubt(world, 'u1')
    make_answer(d, 'u2')
    assert _run('own', 'DELETE FROM activity.doubts WHERE id = %s', [d]) == 1
    assert answer_ids() == []


def test_esborrar_la_propia_resposta_cascadeja_les_respostes_alienes_filles(world):
    d, a = build_tree(world, 'u1')                  # a1 (u2) -> a1r (u3) -> a1rr (u1); a1 -> a1s (u2)
    assert _run('other', 'DELETE FROM activity.answers WHERE id = %s', [a['a1']]) == 1
    assert answer_ids(d) == [a['a2']]


def test_delete_en_massa_nomes_afecta_les_files_permeses(world):
    make_doubt(world, 'u1', minutes=0)
    make_doubt(world, 'u2', minutes=1)
    make_doubt(world, 'u1', minutes=2)
    assert _run('own', 'DELETE FROM activity.doubts') == 2
    assert len(doubt_ids()) == 1
    assert _run('admin', 'DELETE FROM activity.doubts') == 1


# =================================== UPDATE / TRUNCATE ===================================

@pytest.mark.parametrize('ctx', ALL_CTX)
def test_no_hi_ha_update_per_a_ningu(world, ctx):
    d = make_doubt(world, 'u1')
    a = make_answer(d, 'u2')
    _denied(lambda: _run(ctx, "UPDATE activity.doubts SET message = 'editat' WHERE id = %s", [d]))
    _denied(lambda: _run(ctx, "UPDATE activity.answers SET message = 'editat' WHERE id = %s", [a]))


@pytest.mark.parametrize('table', ['activity.doubts', 'activity.answers'])
def test_no_hi_ha_truncate(world, table):
    make_doubt(world, 'u1')                                   # la taula ha d'existir: si no, el test passaria per error
    _denied(lambda: _run('system', f'TRUNCATE {table}'))


# =================================== cascades amb el rol app ===================================

def test_esborrar_l_usuari_amb_el_rol_app_cascadeja_sense_que_la_rls_ho_talli(world):
    """§7.5.2: `DELETE FROM users.users` esborra els dubtes i les respostes d'`u1` i les respostes alienes que penjaven."""
    d1, a = build_tree(world, 'u1')                 # dubte d'u1 amb respostes de u2 i u3
    d2 = make_doubt(world, 'u2', minutes=10)
    b1 = make_answer(d2, 'u1', minutes=11)                          # resposta d'u1 en un dubte d'altri
    b1r = make_answer(d2, 'u2', parent=b1, minutes=12)              # filla d'u2 sota la d'u1
    b2 = make_answer(d2, 'u3', minutes=13)                          # no relacionada
    assert _run('own', 'DELETE FROM users.users WHERE uid = %s', ['u1']) == 1
    assert doubt_ids() == [d2]
    assert answer_ids() == [b2]
    assert b1r not in answer_ids()
