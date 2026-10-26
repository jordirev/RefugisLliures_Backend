"""
Contracte HTTP de `GET/POST /api/doubts/` i `DELETE /api/doubts/{doubt_id}/` (chunk 6), vistes a `apps/doubts/views.py`
(`DoubtListAPIView`, `DoubtDetailAPIView`; mateixos noms de ruta que ara: `doubt_list`, `doubt_detail`).

- `GET /api/doubts/?refuge_id=X` -> 200 `[Doubt]` (dubtes `created_at DESC`; cada un amb `answers_count` i `answers`
  planes `created_at ASC`); sense `refuge_id` 400; refugi inexistent o id no UUID 404 `{error: 'Refuge not found'}`.
  No hi ha paginació (llista completa, com ara).
- `POST /api/doubts/` cos `{refuge_id, message}` (el refugi va al COS) -> 201 amb el dubte (`answers_count` 0);
  validació 400 `{error: 'Dades invàlides', details}`; refugi inexistent o id no UUID 404 `{error: 'Refuge not found'}`.
  El creador és sempre l'usuari del token.
- `DELETE /api/doubts/{id}/` -> 204 sense cos; 404 `{error: 'Doubt not found'}` (també id no UUID); 403 `not_owner`
  (`{error, code, message}` amb `error == code == 'not_owner'`) si no és el creador ni admin (C1).
- Ordre de comprovacions: permisos -> validació del cos (400) -> existència (404) -> propietat (403).
"""
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.doubts.tests.helpers import (
    ANSWER_KEYS, DOUBT_BASE_KEYS, DOUBTS, NOT_OWNER, admin_claims, answer_ids, answers_of, answers_url, api_delete,
    api_get, api_post, doubt_ids, doubt_rows, doubt_url, is_uuid, list_url, make_answer, make_doubt, make_refuge,
    make_user, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]


# =================================== GET ===================================

def test_llista_buida_d_un_refugi_sense_dubtes(client, world):
    r = api_get(client, list_url(world[0].pk), user_claims('u1'))
    assert r.status_code == 200 and r.json() == []


def test_forma_i_ordre_de_la_llista(client, world):
    r1, r2 = world
    old = make_doubt(r1, 'u1', message='antic', minutes=0)
    new = make_doubt(r1, 'u2', message='nou', minutes=10)
    make_doubt(r2, 'u3', message='altre refugi', minutes=5)
    a2 = make_answer(old, 'u3', 'segona', minutes=2)
    a1 = make_answer(old, 'u2', 'primera', minutes=1)
    a3 = make_answer(old, 'u1', 'resposta a la primera', parent=a1, minutes=3)
    resp = api_get(client, list_url(r1.pk), user_claims('u3'))
    assert resp.status_code == 200
    body = resp.json()
    assert [d['id'] for d in body] == [new, old]                                  # created_at DESC
    n, o = body
    assert set(n) == DOUBT_BASE_KEYS | {'answers'} and set(o) == DOUBT_BASE_KEYS | {'answers'}
    assert (n['answers_count'], answers_of(n)) == (0, [])
    assert o['answers_count'] == 3
    assert [a['id'] for a in o['answers']] == [a1, a2, a3]                        # created_at ASC, llista plana
    assert all(set(a) == ANSWER_KEYS for a in o['answers'])
    assert [a['parent_answer_id'] for a in o['answers']] == [None, None, a1]
    assert o['refuge_id'] == str(r1.pk) and o['creator_uid'] == 'u1' and o['message'] == 'antic'
    assert o['created_at'] == '2025-01-01T11:00:00+01:00'


def test_la_llista_es_visible_per_a_qualsevol_usuari_amb_perfil_i_admin(client, world):
    make_doubt(world[0], 'u1')
    for claims in (user_claims('u2'), user_claims('u1'), admin_claims('adm')):
        r = api_get(client, list_url(world[0].pk), claims)
        assert r.status_code == 200 and len(r.json()) == 1


def test_get_sense_refuge_id_400(client, world):
    for path in (DOUBTS, DOUBTS + '?refuge_id='):
        r = api_get(client, path, user_claims('u1'))
        assert r.status_code == 400 and 'refuge_id' in r.json()['error']


@pytest.mark.parametrize('rid', ['no-es-uuid', 'a%00b', '0' * 200, "1'%20OR%20'1'='1"])
def test_get_refugi_amb_id_no_uuid_404(client, world, rid):
    r = api_get(client, list_url(rid), user_claims('u1'))
    assert r.status_code == 404 and r.json() == {'error': 'Refuge not found'}


def test_get_refugi_inexistent_404(client, world):
    r = api_get(client, list_url(uuid.uuid4()), user_claims('u1'))
    assert r.status_code == 404 and r.json() == {'error': 'Refuge not found'}


def test_get_nomes_retorna_els_dubtes_del_refugi_demanat(client, world):
    r1, r2 = world
    a = make_doubt(r1, 'u1')
    b = make_doubt(r2, 'u1')
    assert [d['id'] for d in api_get(client, list_url(r1.pk), user_claims('u2')).json()] == [a]
    assert [d['id'] for d in api_get(client, list_url(r2.pk), user_claims('u2')).json()] == [b]


def test_answers_count_inclou_totes_les_respostes_de_l_arbre(client, world):
    from apps.doubts.tests.helpers import build_tree
    make_user('u9')
    d, _ = build_tree(world[0], 'u1')
    [doubt] = api_get(client, list_url(world[0].pk), user_claims('u1')).json()
    assert doubt['answers_count'] == 5 and len(doubt['answers']) == 5


# =================================== POST ===================================

def test_post_crea_el_dubte_201(client, world):
    r1, _ = world
    resp = api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': str(r1.pk), 'message': 'Hi ha llenya?'})
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert set(body) == DOUBT_BASE_KEYS | {'answers'} and answers_of(body) == []
    assert is_uuid(body['id']) and body['refuge_id'] == str(r1.pk)
    assert body['creator_uid'] == 'u1' and body['message'] == 'Hi ha llenya?' and body['answers_count'] == 0
    rows = doubt_rows(r1)
    assert [(r[0], r[2], r[3]) for r in rows] == [(body['id'], 'u1', 'Hi ha llenya?')]


def test_post_created_at_es_el_de_la_bd_amb_desplacament_de_madrid(client, world):
    resp = api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': str(world[0].pk), 'message': 'x'})
    created = datetime.fromisoformat(resp.json()['created_at'])
    assert created == doubt_rows()[0][4]                                          # un sol rellotge (GOTCHAS #62)
    assert created.utcoffset() == created.astimezone(ZoneInfo('Europe/Madrid')).utcoffset()
    assert created.utcoffset().total_seconds() in (3600, 7200)


def test_post_retalla_el_missatge_i_accepta_2000_caracters_i_emojis(client, world):
    rid = str(world[0].pk)
    assert api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': rid, 'message': '  hola  '}).json()['message'] == 'hola'
    assert api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': rid, 'message': 'x' * 2000}).status_code == 201
    assert api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': rid, 'message': '\U0001F600' * 2000}).status_code == 201
    assert api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': rid, 'message': 'x' * 2001}).status_code == 400
    assert len(doubt_ids()) == 3


@pytest.mark.parametrize('body', [
    {}, {'message': 'x'}, {'refuge_id': 'r'}, {'refuge_id': 'r', 'message': ''}, {'refuge_id': 'r', 'message': '   '},
    {'refuge_id': '', 'message': 'x'}, {'refuge_id': 'r' * 101, 'message': 'x'}, {'refuge_id': 'r', 'message': None},
    {'refuge_id': 'r', 'message': 'a\x00b'}, [], 'text',
])
def test_post_dades_invalides_400(client, world, body):
    resp = api_post(client, DOUBTS, user_claims('u1'), body)
    assert resp.status_code == 400, resp.content
    assert resp.json()['error'] == 'Dades invàlides' and 'details' in resp.json()
    assert doubt_ids() == []


def test_post_cos_no_json_400(client, world):
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    with patch(VERIFY, return_value=user_claims('u1')):
        resp = client.post(DOUBTS, data='{no json', content_type='application/json', HTTP_AUTHORIZATION='Bearer t')
    assert resp.status_code == 400 and doubt_ids() == []


@pytest.mark.parametrize('rid', ['no-es-uuid', 'a\x00b', str(uuid.uuid4()), '123'])
def test_post_refugi_inexistent_o_no_uuid_404(client, world, rid):
    resp = api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': rid, 'message': 'x'})
    assert resp.status_code == 404 and resp.json() == {'error': 'Refuge not found'}, resp.content
    assert doubt_ids() == []


def test_post_el_refuge_id_a_la_query_no_serveix(client, world):
    resp = api_post(client, list_url(world[0].pk), user_claims('u1'), {'message': 'x'})
    assert resp.status_code == 400 and doubt_ids() == []


def test_post_ignora_creator_i_resta_de_camps_del_cos(client, world):
    resp = api_post(client, DOUBTS, user_claims('u1'),
                    {'refuge_id': str(world[0].pk), 'message': 'x', 'creator_uid': 'u2', 'id': str(uuid.uuid4()),
                     'created_at': '2000-01-01T00:00:00Z', 'answers_count': 50})
    assert resp.status_code == 201
    body = resp.json()
    assert body['creator_uid'] == 'u1' and body['answers_count'] == 0 and not body['created_at'].startswith('2000')
    assert doubt_rows()[0][0] == body['id'] and doubt_rows()[0][2] == 'u1'


def test_post_com_a_admin_el_creador_es_l_admin(client, world):
    resp = api_post(client, DOUBTS, admin_claims('adm'), {'refuge_id': str(world[0].pk), 'message': 'x'})
    assert resp.status_code == 201 and resp.json()['creator_uid'] == 'adm'


def test_post_el_dubte_creat_surt_a_la_llista_amb_el_mateix_contingut(client, world):
    created = api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': str(world[0].pk), 'message': 'x'}).json()
    [listed] = api_get(client, list_url(world[0].pk), user_claims('u2')).json()
    assert {k: v for k, v in listed.items() if k != 'answers'} == {k: v for k, v in created.items() if k != 'answers'}


def test_post_rep_dos_dubtes_iguals_com_a_dos_dubtes(client, world):
    for _ in range(2):
        assert api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': str(world[0].pk), 'message': 'igual'}
                        ).status_code == 201
    assert len(doubt_ids()) == 2


# =================================== DELETE ===================================

def test_delete_propi_204_sense_cos_i_esborra_les_respostes(client, world):
    d = make_doubt(world[0], 'u1')
    other = make_doubt(world[0], 'u2', minutes=1)
    make_answer(d, 'u2')
    keep = make_answer(other, 'u1')
    resp = api_delete(client, doubt_url(d), user_claims('u1'))
    assert resp.status_code == 204 and resp.content == b''
    assert doubt_ids() == [other] and answer_ids() == [keep]


def test_delete_d_un_altre_403_not_owner_i_no_esborra_res(client, world):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u2')
    resp = api_delete(client, doubt_url(d), user_claims('u2'))                    # u2 ha respost, però no n'és el creador
    assert resp.status_code == 403
    body = resp.json()
    assert body['error'] == NOT_OWNER and body['code'] == NOT_OWNER and isinstance(body['message'], str)
    assert doubt_ids() == [d] and answer_ids() == [a]


def test_delete_com_a_admin_pot_esborrar_el_d_un_altre(client, world):
    d = make_doubt(world[0], 'u1')
    make_answer(d, 'u2')
    assert api_delete(client, doubt_url(d), admin_claims('adm')).status_code == 204
    assert doubt_ids() == [] and answer_ids() == []


def test_delete_inexistent_404(client, world):
    for did in (uuid.uuid4(), 'no-es-uuid', '0' * 200, 'a%00b'):
        r = api_delete(client, doubt_url(did), user_claims('u1'))
        assert r.status_code == 404 and r.json() == {'error': 'Doubt not found'}, did


def test_delete_inexistent_es_404_i_no_403_encara_que_no_siguis_el_creador(client, world):
    assert api_delete(client, doubt_url(uuid.uuid4()), admin_claims('adm')).status_code == 404


def test_delete_dues_vegades_la_segona_es_404(client, world):
    d = make_doubt(world[0], 'u1')
    assert api_delete(client, doubt_url(d), user_claims('u1')).status_code == 204
    assert api_delete(client, doubt_url(d), user_claims('u1')).status_code == 404


def test_delete_un_dubte_no_toca_els_d_altres_refugis(client, world):
    r1, r2 = world
    d = make_doubt(r1, 'u1')
    keep = make_doubt(r2, 'u1', minutes=1)
    api_delete(client, doubt_url(d), user_claims('u1'))
    assert doubt_ids() == [keep]


# =================================== mètodes no permesos ===================================

@pytest.mark.parametrize('method,path', [
    ('put', DOUBTS), ('patch', DOUBTS), ('delete', DOUBTS),
])
def test_metodes_no_permesos_a_la_col_leccio(client, world, method, path):
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    with patch(VERIFY, return_value=user_claims('u1')):
        r = getattr(client, method)(path, data='{}', content_type='application/json', HTTP_AUTHORIZATION='Bearer t')
    assert r.status_code == 405


@pytest.mark.parametrize('method', ['get', 'put', 'patch', 'post'])
def test_metodes_no_permesos_al_detall_del_dubte(client, world, method):
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    d = make_doubt(world[0], 'u1')
    with patch(VERIFY, return_value=user_claims('u1')):
        r = client.generic(method.upper(), doubt_url(d), data='{}', content_type='application/json',
                                    HTTP_AUTHORIZATION='Bearer t')
    assert r.status_code == 405


@pytest.mark.parametrize('method', ['get', 'put', 'patch', 'delete'])
def test_metodes_no_permesos_a_les_respostes_d_un_dubte(client, world, method):
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    d = make_doubt(world[0], 'u1')
    with patch(VERIFY, return_value=user_claims('u1')):
        r = client.generic(method.upper(), answers_url(d), data='{}', content_type='application/json',
                                    HTTP_AUTHORIZATION='Bearer t')
    assert r.status_code == 405
