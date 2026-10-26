"""
Permisos i seguretat dels endpoints de dubtes (chunk 6; CLAUDE.md gotcha 15, C1).

- Anònim -> 401 a tots; usuari sense fila a `users.users` (també admin) -> 403 `profile_required`.
- Les quatre vistes porten `IsAuthenticated, HasProfile` en aquest ordre (a cada mètode; els POST, a més, bloqueig i edat).
- Els tres POST exigeixen a més `IsNotBlocked` i `IsAgeConfirmed` (decisió del PO, 26/10); GET i DELETE no: un usuari
  bloquejat o sense edat confirmada pot llegir i esborrar el seu contingut (RGPD).
- Les vistes viuen a `apps.doubts.views` i les rutes s'inclouen des d'`apps.doubts.urls`.
- C1: la propietat la comprova el service (403 `not_owner`) i la RLS; cap IDOR; ids hostils -> 404, mai 500.
"""
import uuid

import pytest
from django.urls import get_resolver, resolve, reverse
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.permissions import HasProfile
from apps.doubts.tests.helpers import (
    DOUBTS, NOT_OWNER, admin_claims, answer_ids, answer_url, answers_url, api_delete, api_get, api_post, doubt_ids,
    doubt_url, make_answer, make_doubt, make_refuge, make_user, sql, user_claims, at)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SOME = str(uuid.uuid4())
ENDPOINTS = [
    ('get', f'{DOUBTS}?refuge_id={SOME}', None),
    ('post', DOUBTS, {'refuge_id': SOME, 'message': 'x'}),
    ('delete', doubt_url(SOME), None),
    ('post', answers_url(SOME), {'message': 'x'}),
    ('post', answer_url(SOME, SOME), {'message': 'x'}),
    ('delete', answer_url(SOME, SOME), None),
]


def call(client, method, path, claims, body=None):
    if method == 'get':
        return api_get(client, path, claims)
    if method == 'delete':
        return api_delete(client, path, claims)
    return api_post(client, path, claims, body)


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_anonim_401(client, method, path, body):
    assert call(client, method, path, None, body).status_code == 401


@pytest.mark.parametrize('claims_fn', [user_claims, admin_claims])
@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_sense_perfil_403_profile_required(client, method, path, body, claims_fn):
    r = call(client, method, path, claims_fn('ghost'), body)
    assert r.status_code == 403 and r.json().get('error') == 'profile_required', r.content


def test_sense_perfil_no_es_crea_res(client, world):
    api_post(client, DOUBTS, user_claims('ghost'), {'refuge_id': str(world[0].pk), 'message': 'x'})
    assert doubt_ids() == []
    assert sql("SELECT count(*) FROM users.users WHERE uid = 'ghost'") == [(0,)]


# ---------- permission_classes ----------

def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def _doubt_views():
    out = {}
    for route, pattern in _walk(get_resolver().url_patterns):
        if route.startswith('api/doubts/'):
            cls = getattr(pattern.callback, 'cls', None) or getattr(pattern.callback, 'view_class', None)
            out[route] = cls
    return out


def test_hi_ha_les_quatre_rutes_i_viuen_a_apps_doubts():
    views = _doubt_views()
    assert len(views) == 4, views
    for route, cls in views.items():
        assert cls.__module__ == 'apps.doubts.views', (route, cls)


@pytest.mark.parametrize('name,args', [('doubt_list', []), ('doubt_detail', ['x']), ('answer_list', ['x']),
                                       ('answer_reply', ['x', 'y'])])
def test_noms_de_ruta_conservats(name, args):
    path = reverse(name, args=args)
    assert path.startswith('/api/doubts/')
    assert resolve(path).func.cls.__module__ == 'apps.doubts.views'


def test_cada_metode_exigeix_is_authenticated_i_despres_has_profile():
    factory = APIRequestFactory()
    checked = 0
    for route, cls in _doubt_views().items():
        for method in ('get', 'post', 'delete'):
            if not hasattr(cls, method):
                continue
            view = cls()
            view.request = Request(getattr(factory, method)('/x/'))
            names = [type(p) for p in view.get_permissions()]
            assert names[:2] == [IsAuthenticated, HasProfile], (route, method, names)
            checked += 1
    assert checked == 6


# ---------- bloqueig i edat: només a l'escriptura de contingut (POST; decisió del PO, 26/10) ----------

def test_els_tres_post_exigeixen_bloqueig_i_edat_i_la_resta_no():
    from api.permissions import IsAgeConfirmed, IsNotBlocked
    factory = APIRequestFactory()
    for route, cls in _doubt_views().items():
        for method in ('get', 'post', 'delete'):
            if not hasattr(cls, method):
                continue
            view = cls()
            view.request = Request(getattr(factory, method)('/x/'))
            names = [type(p) for p in view.get_permissions()]
            expected = ([IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed] if method == 'post'
                        else [IsAuthenticated, HasProfile])
            assert names == expected, (route, method, names)


def _post_endpoints(world, d):
    return [(DOUBTS, {'refuge_id': str(world[0].pk), 'message': 'x'}),
            (answers_url(d), {'message': 'x'}),
            (answer_url(d, make_answer(d, 'u1')), {'message': 'x'})]


def test_un_usuari_bloquejat_no_pot_fer_post_pero_si_llegir_i_esborrar_el_seu(client, world):
    make_user('blk', is_blocked=True, blocked_reason='csam_confirmed', blocked_at=at())
    d = make_doubt(world[0], 'u1')
    own_doubt = make_doubt(world[0], 'blk', minutes=1)
    own_answer = make_answer(d, 'blk', minutes=2)
    for path, body in _post_endpoints(world, d):
        r = api_post(client, path, user_claims('blk'), body)
        assert r.status_code == 403 and r.json()['error'] == 'user_blocked', (path, r.content)
    assert len(doubt_ids()) == 2 and len(answer_ids(d)) == 2
    assert api_get(client, f'{DOUBTS}?refuge_id={world[0].pk}', user_claims('blk')).status_code == 200
    assert api_delete(client, answer_url(d, own_answer), user_claims('blk')).status_code == 204
    assert api_delete(client, doubt_url(own_doubt), user_claims('blk')).status_code == 204


def test_un_usuari_sense_edat_confirmada_no_pot_fer_post_pero_si_llegir_i_esborrar_el_seu(client, world):
    make_user('kid', age_confirmed_at=None, age_threshold=None)
    d = make_doubt(world[0], 'u1')
    own_doubt = make_doubt(world[0], 'kid', minutes=1)
    own_answer = make_answer(d, 'kid', minutes=2)
    for path, body in _post_endpoints(world, d):
        r = api_post(client, path, user_claims('kid'), body)
        assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed', (path, r.content)
    assert len(doubt_ids()) == 2 and len(answer_ids(d)) == 2
    assert api_get(client, f'{DOUBTS}?refuge_id={world[0].pk}', user_claims('kid')).status_code == 200
    assert api_delete(client, answer_url(d, own_answer), user_claims('kid')).status_code == 204
    assert api_delete(client, doubt_url(own_doubt), user_claims('kid')).status_code == 204


def test_sense_perfil_el_post_dona_profile_required_abans_que_edat(client, world):
    r = api_post(client, DOUBTS, user_claims('ghost'), {'refuge_id': str(world[0].pk), 'message': 'x'})
    assert r.status_code == 403 and r.json()['error'] == 'profile_required'


# ---------- C1: propietat ----------

@pytest.mark.parametrize('uid', ['u2', 'u3'])
def test_c1_ningu_mes_pot_esborrar_el_dubte_ni_la_resposta(client, world, uid):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u1')
    r1 = api_delete(client, answer_url(d, a), user_claims(uid))
    r2 = api_delete(client, doubt_url(d), user_claims(uid))
    assert r1.status_code == r2.status_code == 403
    assert r1.json()['error'] == r2.json()['error'] == NOT_OWNER
    assert doubt_ids() == [d] and answer_ids(d) == [a]


def test_c1_l_admin_si_pot(client, world):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u1')
    assert api_delete(client, answer_url(d, a), admin_claims('adm')).status_code == 204
    assert api_delete(client, doubt_url(d), admin_claims('adm')).status_code == 204


def test_un_admin_amb_claim_pero_sense_rol_a_la_bd_segueix_sent_admin_nomes_pel_token(client, world):
    """`is_admin` surt del token verificat (§7.3.7), mai del cos de la petició."""
    d = make_doubt(world[0], 'u1')
    r = api_delete(client, doubt_url(d), {'uid': 'u2', 'role': 'user', 'admin': True})
    assert r.status_code == 403 and doubt_ids() == [d]


def test_el_cos_no_pot_concedir_privilegis(client, world):
    d = make_doubt(world[0], 'u1')
    from unittest.mock import patch
    from apps.doubts.tests.helpers import VERIFY
    with patch(VERIFY, return_value=user_claims('u2')):
        r = client.delete(doubt_url(d) + '?is_admin=true&creator_uid=u2', data='{"is_admin": true}',
                          content_type='application/json', HTTP_AUTHORIZATION='Bearer t')
    assert r.status_code == 403 and doubt_ids() == [d]


# ---------- ids hostils ----------

HOSTILE = ['a%00b', "1'%20OR%20'1'='1", '..%2F..%2Fetc', '%E0%A4%A', 'x' * 500, '0', '-1',
           '00000000-0000-0000-0000-000000000000', 'ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ']


@pytest.mark.parametrize('bad', HOSTILE)
def test_ids_hostils_donen_404_i_mai_500(client, world, bad):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u1')
    for r in (api_delete(client, doubt_url(bad), user_claims('u1')),
              api_post(client, answers_url(bad), user_claims('u1'), {'message': 'x'}),
              api_post(client, answer_url(bad, bad), user_claims('u1'), {'message': 'x'}),
              api_post(client, answer_url(d, bad), user_claims('u1'), {'message': 'x'}),
              api_delete(client, answer_url(d, bad), user_claims('u1')),
              api_delete(client, answer_url(bad, a), user_claims('u1')),
              api_get(client, f'{DOUBTS}?refuge_id={bad}', user_claims('u1')),
              api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': bad, 'message': 'x'})):
        assert r.status_code in (404, 400), (bad, r.status_code, r.content)
    assert doubt_ids() == [d] and answer_ids(d) == [a]
    sql('SELECT 1 FROM activity.doubts LIMIT 1')                      # la taula segueix al seu lloc


def test_el_missatge_es_desa_tal_qual_sense_executar_res(client, world):
    payload = "'); DROP TABLE activity.doubts; --<script>alert(1)</script>"
    r = api_post(client, DOUBTS, user_claims('u1'), {'refuge_id': str(world[0].pk), 'message': payload})
    assert r.status_code == 201 and r.json()['message'] == payload
    assert sql('SELECT message FROM activity.doubts') == [(payload,)]


def test_les_respostes_d_error_no_filtren_dades_personals(client, world):
    d = make_doubt(world[0], 'u1', message='secret')
    r = api_delete(client, doubt_url(d), user_claims('u2'))
    text = r.content.decode()
    assert 'secret' not in text and 'u1' not in text
