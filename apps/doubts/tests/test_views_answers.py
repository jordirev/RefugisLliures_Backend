"""
Contracte HTTP de les respostes (chunk 6): `AnswerListAPIView` i `AnswerReplyAPIView` a `apps/doubts/views.py`
(rutes `answer_list`, `answer_reply`).

- `POST /api/doubts/{doubt_id}/answers/` cos `{message}` -> 201 `{id, creator_uid, message, created_at, parent_answer_id: null}`.
- `POST /api/doubts/{doubt_id}/answers/{answer_id}/` (rèplica) -> 201 amb `parent_answer_id = answer_id`.
- `DELETE /api/doubts/{doubt_id}/answers/{answer_id}/` -> 204; esborra TOT el subarbre de la resposta (canvi respecte
  d'avui: abans les filles quedaven penjant).
- 404 amb el text d'avui: `Doubt not found`, `Parent answer not found` (POST rèplica: pare inexistent, d'un altre dubte
  o id no UUID), `Answer not found` (DELETE). 400 de validació abans que cap 404. 403 `not_owner` (només el creador de
  la RESPOSTA o un admin; el creador del dubte no pot esborrar respostes alienes).
"""
import uuid
from datetime import datetime

import pytest

from apps.doubts.tests.helpers import (
    ANSWER_KEYS, NOT_OWNER, admin_claims, answer_ids, answer_rows, answer_url, answers_url, api_delete, api_get,
    api_post, build_tree, doubt_ids, doubt_url, is_uuid, list_url, make_answer, make_doubt, make_user, sql,
    user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


@pytest.fixture
def d(world):
    return make_doubt(world[0], 'u1')


# =================================== POST resposta directa ===================================

def test_post_resposta_201(client, world, d):
    resp = api_post(client, answers_url(d), user_claims('u2'), {'message': 'Sí, hi ha una font'})
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert set(body) == ANSWER_KEYS and is_uuid(body['id'])
    assert body['creator_uid'] == 'u2' and body['message'] == 'Sí, hi ha una font' and body['parent_answer_id'] is None
    rows = answer_rows(d)
    assert [(r[0], r[2], r[3]) for r in rows] == [(body['id'], 'u2', None)]
    assert datetime.fromisoformat(body['created_at']) == rows[0][5]


def test_el_creador_del_dubte_tambe_pot_respondre(client, world, d):
    assert api_post(client, answers_url(d), user_claims('u1'), {'message': 'ho aclareixo'}).status_code == 201


def test_post_incrementa_answers_count(client, world, d):
    api_post(client, answers_url(d), user_claims('u2'), {'message': 'a'})
    r = api_post(client, answers_url(d), user_claims('u3'), {'message': 'b'})
    assert r.status_code == 201
    [doubt] = api_get(client, list_url(world[0].pk), user_claims('u1')).json()
    assert doubt['answers_count'] == 2 and [a['message'] for a in doubt['answers']] == ['a', 'b']


@pytest.mark.parametrize('body', [{}, {'message': ''}, {'message': '  '}, {'message': 'x' * 2001}, {'message': None},
                                  {'message': 'a\x00b'}, []])
def test_post_dades_invalides_400(client, world, d, body):
    resp = api_post(client, answers_url(d), user_claims('u2'), body)
    assert resp.status_code == 400 and resp.json()['error'] == 'Dades invàlides' and 'details' in resp.json()
    assert answer_ids(d) == []


def test_post_missatge_de_2000_caracters_val(client, world, d):
    assert api_post(client, answers_url(d), user_claims('u2'), {'message': 'x' * 2000}).status_code == 201


def test_la_validacio_va_abans_del_404(client, world):
    r = api_post(client, answers_url(uuid.uuid4()), user_claims('u2'), {'message': ''})
    assert r.status_code == 400


@pytest.mark.parametrize('did', ['uuid', 'no-es-uuid', 'a%00b', '0' * 200])
def test_post_dubte_inexistent_404(client, world, did):
    did = uuid.uuid4() if did == 'uuid' else did
    r = api_post(client, answers_url(did), user_claims('u2'), {'message': 'x'})
    assert r.status_code == 404 and r.json() == {'error': 'Doubt not found'}


def test_post_ignora_creator_pare_i_id_del_cos(client, world, d):
    other = make_answer(d, 'u3')
    resp = api_post(client, answers_url(d), user_claims('u2'),
                    {'message': 'x', 'creator_uid': 'u3', 'parent_answer_id': other, 'id': str(uuid.uuid4())})
    body = resp.json()
    assert resp.status_code == 201 and body['creator_uid'] == 'u2' and body['parent_answer_id'] is None


def test_post_com_a_admin(client, world, d):
    r = api_post(client, answers_url(d), admin_claims('adm'), {'message': 'moderació'})
    assert r.status_code == 201 and r.json()['creator_uid'] == 'adm'


# =================================== POST rèplica ===================================

def test_replica_a_una_resposta_201(client, world, d):
    a = make_answer(d, 'u2')
    resp = api_post(client, answer_url(d, a), user_claims('u3'), {'message': 'gràcies'})
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert set(body) == ANSWER_KEYS and body['parent_answer_id'] == a and body['creator_uid'] == 'u3'
    assert [(r[0], r[3]) for r in answer_rows(d)][-1] == (body['id'], a)


def test_replica_a_una_replica_arbre_de_diversos_nivells(client, world, d):
    parent = None
    for i, uid in enumerate(['u2', 'u3', 'u1', 'u2', 'u3']):
        path = answers_url(d) if parent is None else answer_url(d, parent)
        resp = api_post(client, path, user_claims(uid), {'message': f'nivell {i}'})
        assert resp.status_code == 201 and resp.json()['parent_answer_id'] == parent
        parent = resp.json()['id']
    [doubt] = api_get(client, list_url(world[0].pk), user_claims('u1')).json()
    assert doubt['answers_count'] == 5


def test_replica_pare_inexistent_404_parent_answer_not_found(client, world, d):
    for aid in (uuid.uuid4(), 'no-es-uuid', 'a%00b'):
        r = api_post(client, answer_url(d, aid), user_claims('u2'), {'message': 'x'})
        assert r.status_code == 404 and r.json() == {'error': 'Parent answer not found'}, aid
    assert answer_ids(d) == []


def test_replica_a_una_resposta_d_un_altre_dubte_404_i_no_es_desa(client, world):
    """Avui ho comprova el controller; ara també la FK composta `answers_parent_same_doubt_fk`."""
    r1, _ = world
    d1, d2 = make_doubt(r1, 'u1'), make_doubt(r1, 'u1', minutes=1)
    foreign = make_answer(d2, 'u3')
    resp = api_post(client, answer_url(d1, foreign), user_claims('u2'), {'message': 'x'})
    assert resp.status_code == 404 and resp.json() == {'error': 'Parent answer not found'}
    assert answer_ids(d1) == [] and answer_ids(d2) == [foreign]


def test_replica_amb_dubte_inexistent_404_doubt_not_found(client, world, d):
    a = make_answer(d, 'u2')
    r = api_post(client, answer_url(uuid.uuid4(), a), user_claims('u2'), {'message': 'x'})
    assert r.status_code == 404 and r.json() == {'error': 'Doubt not found'}


def test_replica_validacio_abans_del_404(client, world, d):
    r = api_post(client, answer_url(d, uuid.uuid4()), user_claims('u2'), {})
    assert r.status_code == 400


# =================================== DELETE ===================================

def test_delete_propia_204_i_esborra_el_subarbre(client, world):
    make_user('u9')
    d, a = build_tree(world[0], 'u1')                  # a1 (u2) { a1r (u3) { a1rr (u1) }, a1s (u2) }, a2 (u3)
    resp = api_delete(client, answer_url(d, a['a1']), user_claims('u2'))
    assert resp.status_code == 204 and resp.content == b''
    assert answer_ids(d) == [a['a2']] and doubt_ids() == [d]


def test_delete_d_una_resposta_intermitja_nomes_esborra_els_seus_descendents(client, world):
    d, a = build_tree(world[0], 'u1')
    assert api_delete(client, answer_url(d, a['a1r']), user_claims('u3')).status_code == 204
    assert set(answer_ids(d)) == {a['a1'], a['a1s'], a['a2']}


def test_delete_d_una_fulla(client, world):
    d, a = build_tree(world[0], 'u1')
    assert api_delete(client, answer_url(d, a['a1rr']), user_claims('u1')).status_code == 204
    assert len(answer_ids(d)) == 4


def test_delete_actualitza_answers_count(client, world):
    d, a = build_tree(world[0], 'u1')
    api_delete(client, answer_url(d, a['a1']), user_claims('u2'))
    [doubt] = api_get(client, list_url(world[0].pk), user_claims('u1')).json()
    assert doubt['answers_count'] == 1 and [x['id'] for x in doubt['answers']] == [a['a2']]


def test_delete_d_una_resposta_d_un_altre_403_not_owner(client, world):
    d, a = build_tree(world[0], 'u1')
    resp = api_delete(client, answer_url(d, a['a1']), user_claims('u3'))
    assert resp.status_code == 403
    body = resp.json()
    assert body['error'] == NOT_OWNER and body['code'] == NOT_OWNER and isinstance(body['message'], str)
    assert len(answer_ids(d)) == 5


def test_el_creador_del_dubte_no_pot_esborrar_respostes_alienes(client, world):
    d, a = build_tree(world[0], 'u1')
    resp = api_delete(client, answer_url(d, a['a1']), user_claims('u1'))
    assert resp.status_code == 403 and resp.json()['error'] == NOT_OWNER
    assert len(answer_ids(d)) == 5


def test_delete_com_a_admin_204(client, world):
    d, a = build_tree(world[0], 'u1')
    assert api_delete(client, answer_url(d, a['a1']), admin_claims('adm')).status_code == 204
    assert answer_ids(d) == [a['a2']]


def test_delete_resposta_inexistent_404(client, world, d):
    for aid in (uuid.uuid4(), 'no-es-uuid', 'a%00b', '0' * 200):
        r = api_delete(client, answer_url(d, aid), user_claims('u1'))
        assert r.status_code == 404 and r.json() == {'error': 'Answer not found'}, aid


def test_delete_dubte_inexistent_404_doubt_not_found(client, world, d):
    a = make_answer(d, 'u2')
    for did in (uuid.uuid4(), 'no-es-uuid'):
        r = api_delete(client, answer_url(did, a), user_claims('u2'))
        assert r.status_code == 404 and r.json() == {'error': 'Doubt not found'}
    assert answer_ids(d) == [a]


def test_delete_resposta_d_un_altre_dubte_per_la_url_404_tambe_per_a_admin(client, world):
    """IDOR: l'`answer_id` ha de ser del `doubt_id` de la URL."""
    r1, _ = world
    d1, d2 = make_doubt(r1, 'u1'), make_doubt(r1, 'u1', minutes=1)
    a = make_answer(d2, 'u2')
    for claims in (user_claims('u2'), admin_claims('adm')):
        r = api_delete(client, answer_url(d1, a), claims)
        assert r.status_code == 404 and r.json() == {'error': 'Answer not found'}
    assert answer_ids(d2) == [a]


def test_delete_dues_vegades_la_segona_es_404(client, world, d):
    a = make_answer(d, 'u2')
    assert api_delete(client, answer_url(d, a), user_claims('u2')).status_code == 204
    assert api_delete(client, answer_url(d, a), user_claims('u2')).status_code == 404


def test_esborrar_el_dubte_esborra_l_arbre_sencer(client, world):
    make_user('u9')
    d, a = build_tree(world[0], 'u1')
    assert api_delete(client, doubt_url(d), user_claims('u1')).status_code == 204
    assert answer_ids() == [] and doubt_ids() == []


def test_get_i_put_a_la_resposta_no_estan_permesos(client, world, d):
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    a = make_answer(d, 'u2')
    for method in ('get', 'put', 'patch'):
        with patch(VERIFY, return_value=user_claims('u2')):
            r = getattr(client, method)(answer_url(d, a), data='{}', content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer t')
        assert r.status_code == 405
