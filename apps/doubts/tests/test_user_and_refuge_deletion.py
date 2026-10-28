"""
Cascades de dubtes i respostes (chunk 6, §8.4-8.5) a través de l'API d'altres dominis:

- `DELETE /api/users/{uid}/` ja no té els passos de Firestore «dubtes» ni «respostes» (l'esborrat ja no toca Firestore, D42): la FK `ON DELETE CASCADE` esborra els dubtes de l'usuari (amb les respostes d'altres), les seves
  respostes i el subarbre de respostes que penja de les seves, també en dubtes d'altres.
- Esborrar un refugi (propietari/admin del catàleg, chunk 8) esborra els seus dubtes i respostes.
"""

import pytest

from apps.doubts.tests.helpers import (
    admin_claims, answer_ids, api_delete, api_get, as_owner, doubt_ids, list_url, make_answer, make_doubt,
    make_refuge, make_user, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


def _falla_el_delete_d_usuari():
    """Fa fallar el `DELETE` de `users.users` (D42: tot el procediment és una sola transacció i es desfà)."""
    from django.db import DatabaseError, connection

    def boom(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('DELETE') and 'users"."users' in sql_:
            raise DatabaseError('fallada simulada')
        return execute(sql_, params, many, context)
    return connection.execute_wrapper(boom)


def test_delete_user_cascadeja_dubtes_respostes_i_subarbres_alienes(client, world):
    r1, r2 = world
    # Dubte d'u1 amb respostes d'altres (i una filla d'u3 sota una d'u2)
    d1 = make_doubt(r1, 'u1', minutes=0)
    x1 = make_answer(d1, 'u2', minutes=1)
    x1r = make_answer(d1, 'u3', parent=x1, minutes=2)
    own_in_own = make_answer(d1, 'u1', minutes=3)
    # Dubte d'u2: arbre amb respostes d'u1 pel mig
    d2 = make_doubt(r2, 'u2', minutes=10)
    b1 = make_answer(d2, 'u1', minutes=11)                           # d'u1
    b1r = make_answer(d2, 'u2', parent=b1, minutes=12)               # filla d'u2 sota la d'u1 -> també desapareix
    b1rr = make_answer(d2, 'u3', parent=b1r, minutes=13)             # néta d'u3 -> també desapareix
    b2 = make_answer(d2, 'u3', minutes=14)                           # no relacionada: es conserva
    b2r = make_answer(d2, 'u2', parent=b2, minutes=15)               # es conserva
    # Dubte d'u3 intacte
    d3 = make_doubt(r1, 'u3', minutes=20)
    c1 = make_answer(d3, 'u2', minutes=21)
    resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 204, resp.content
    assert set(doubt_ids()) == {d2, d3}
    assert set(answer_ids()) == {b2, b2r, c1}
    gone = {x1, x1r, own_in_own, b1, b1r, b1rr}
    assert not gone & set(answer_ids())


def test_despres_de_l_esborrat_els_comptadors_de_l_api_es_recalculen(client, world):
    r2 = world[1]
    d2 = make_doubt(r2, 'u2')
    b1 = make_answer(d2, 'u1', minutes=1)
    make_answer(d2, 'u2', parent=b1, minutes=2)
    make_answer(d2, 'u3', minutes=3)
    [before] = api_get(client, list_url(r2.pk), user_claims('u2')).json()
    assert before['answers_count'] == 3
    assert api_delete(client, '/api/users/u1/', user_claims('u1')).status_code == 204
    [after] = api_get(client, list_url(r2.pk), user_claims('u2')).json()
    assert after['answers_count'] == 1 and len(after['answers']) == 1


def test_un_admin_no_pot_esborrar_l_usuari_d_un_altre_pero_els_dubtes_es_conserven(client, world):
    d = make_doubt(world[0], 'u1')
    assert api_delete(client, '/api/users/u1/', admin_claims('adm')).status_code == 403
    assert doubt_ids() == [d]


def test_si_falla_l_esborrat_de_l_usuari_els_dubtes_es_conserven(client, world):
    """D42: si falla el `DELETE` (mateixa transacció) es desfà tot, també la cascada de dubtes i respostes."""
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u2')
    with _falla_el_delete_d_usuari():
        resp = api_delete(client, '/api/users/u1/', user_claims('u1'))
    assert resp.status_code == 500
    assert doubt_ids() == [d] and answer_ids() == [a]


def test_esborrar_un_refugi_esborra_els_seus_dubtes_i_respostes(RM, world):
    r1, r2 = world
    d1 = make_doubt(r1, 'u1')
    make_answer(d1, 'u2')
    d2 = make_doubt(r2, 'u1', minutes=1)
    keep = make_answer(d2, 'u2')
    with as_owner():
        RM.Refuge.objects.filter(pk=r1.pk).delete()
    assert doubt_ids() == [d2] and answer_ids() == [keep]
