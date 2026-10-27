"""
Permisos i seguretat dels endpoints d'experiències (chunk 7; CLAUDE.md gotcha 15, C1).

- Anònim -> 401 a tots; usuari sense fila a `users.users` (també admin) -> 403 `profile_required`.
- `GET`, `PATCH`, `DELETE` porten `IsAuthenticated, HasProfile` en aquest ordre; `POST` i `PATCH` (escriptura de
  contingut) hi afegeixen `IsNotBlocked` i `IsAgeConfirmed` (decisió del PO, 26/10; abans: POST només `IsNotBlocked`,
  PATCH/DELETE `IsNotBlocked` a nivell de classe). `GET` i `DELETE` del contingut propi no els exigeixen: un usuari
  bloquejat o sense edat confirmada pot llegir i esborrar el seu contingut (RGPD). **Canvi respecte d'avui:** el
  `DELETE` d'un bloquejat passa de 403 a 200.
- Les vistes viuen a `apps.experiences.views` i les rutes s'inclouen des d'`apps.experiences.urls`.
- C1: la propietat la comprova el service (403 `not_owner`) i la RLS; cap IDOR; ids hostils -> 404, mai 500.
"""
import uuid
from unittest.mock import patch

import pytest
from django.urls import get_resolver, resolve, reverse
from django.urls.resolvers import URLPattern, URLResolver
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked
from apps.experiences.tests.helpers import (
    EXPERIENCES, NOT_OWNER, VERIFY, admin_claims, api_delete, api_get, api_patch, api_post, at, exp_ids, exp_row,
    exp_url, list_url, make_experience, make_user, new_body, refuge_state, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SOME = str(uuid.uuid4())
ENDPOINTS = [
    ('get', f'{EXPERIENCES}?refuge_id={SOME}', None),
    ('post', EXPERIENCES, {'refuge_id': SOME, 'comment': 'x', 'condition': 1}),
    ('patch', exp_url(SOME), {'comment': 'x'}),
    ('delete', exp_url(SOME), None),
]


def call(client, method, path, claims, body=None):
    if method == 'get':
        return api_get(client, path, claims)
    if method == 'delete':
        return api_delete(client, path, claims)
    return (api_post if method == 'post' else api_patch)(client, path, claims, body)


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_anonim_401(client, method, path, body):
    assert call(client, method, path, None, body).status_code == 401


@pytest.mark.parametrize('claims_fn', [user_claims, admin_claims])
@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_sense_perfil_403_profile_required(client, method, path, body, claims_fn):
    r = call(client, method, path, claims_fn('ghost'), body)
    assert r.status_code == 403 and r.json().get('error') == 'profile_required', r.content


def test_sense_perfil_no_es_crea_res(client, world):
    api_post(client, EXPERIENCES, user_claims('ghost'), new_body(world[0]))
    assert exp_ids() == [] and refuge_state(world[0])[:2] == (None, 0)
    assert sql("SELECT count(*) FROM users.users WHERE uid = 'ghost'") == [(0,)]


# ---------- permission_classes ----------

def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def _views():
    out = {}
    for route, pattern in _walk(get_resolver().url_patterns):
        if route.startswith('api/experiences/'):
            out[route] = getattr(pattern.callback, 'cls', None) or getattr(pattern.callback, 'view_class', None)
    return out


def test_hi_ha_les_dues_rutes_i_viuen_a_apps_experiences():
    views = _views()
    assert len(views) == 2, views
    for route, cls in views.items():
        assert cls.__module__ == 'apps.experiences.views', (route, cls)


@pytest.mark.parametrize('name,args', [('experience_list', []), ('experience_detail', ['x'])])
def test_noms_de_ruta_conservats(name, args):
    path = reverse(name, args=args)
    assert path.startswith('/api/experiences/')
    assert resolve(path).func.cls.__module__ == 'apps.experiences.views'


def _perms(cls, method):
    view = cls()
    view.request = Request(getattr(APIRequestFactory(), method)('/x/'))
    return [type(p) for p in view.get_permissions()]


def test_cada_metode_exigeix_is_authenticated_i_despres_has_profile():
    checked = 0
    for route, cls in _views().items():
        for method in ('get', 'post', 'patch', 'delete'):
            if hasattr(cls, method):
                assert _perms(cls, method)[:2] == [IsAuthenticated, HasProfile], (route, method)
                checked += 1
    assert checked == 4


def test_post_i_patch_exigeixen_bloqueig_i_edat_i_get_i_delete_no():
    for route, cls in _views().items():
        for method in ('get', 'post', 'patch', 'delete'):
            if not hasattr(cls, method):
                continue
            expected = ([IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed] if method in ('post', 'patch')
                        else [IsAuthenticated, HasProfile])
            assert _perms(cls, method) == expected, (route, method)


def test_no_s_usa_is_experience_creator_que_no_protegeix_res():
    """Gotcha 1: `has_object_permission` no s'executa mai; la propietat és al service."""
    try:
        from api.permissions import IsExperienceCreator
    except ImportError:                                   # ja eliminada: encara millor
        return
    for route, cls in _views().items():
        for method in ('get', 'post', 'patch', 'delete'):
            if hasattr(cls, method):
                assert IsExperienceCreator not in _perms(cls, method)


# ---------- bloqueig i edat ----------

@pytest.fixture
def blocked():
    return make_user('blk', is_blocked=True, blocked_reason='csam_confirmed', blocked_at=at())


@pytest.fixture
def kid():
    return make_user('kid', age_confirmed_at=None, age_threshold=None)


def test_un_bloquejat_no_pot_fer_post_ni_patch(client, world, blocked):
    mine = make_experience(world[0], 'blk', comment='meu')
    r1 = api_post(client, EXPERIENCES, user_claims('blk'), new_body(world[0]))
    r2 = api_patch(client, exp_url(mine), user_claims('blk'), {'comment': 'editat'})
    for r in (r1, r2):
        assert r.status_code == 403 and r.json()['error'] == 'user_blocked', r.content
    assert exp_ids(creator_uid='blk') == [mine] and exp_row(mine)['comment'] == 'meu'


def test_un_bloquejat_pot_llegir_i_esborrar_el_seu(client, world, blocked):
    mine = make_experience(world[0], 'blk')
    assert api_get(client, list_url(world[0].pk), user_claims('blk')).status_code == 200
    assert api_delete(client, exp_url(mine), user_claims('blk')).status_code == 200
    assert exp_ids() == []


def test_un_sense_edat_confirmada_no_pot_fer_post_ni_patch(client, world, kid):
    mine = make_experience(world[0], 'kid', comment='meu')
    r1 = api_post(client, EXPERIENCES, user_claims('kid'), new_body(world[0]))
    r2 = api_patch(client, exp_url(mine), user_claims('kid'), {'comment': 'editat'})
    for r in (r1, r2):
        assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed', r.content
    assert exp_row(mine)['comment'] == 'meu'


def test_un_sense_edat_confirmada_pot_llegir_i_esborrar_el_seu(client, world, kid):
    mine = make_experience(world[0], 'kid')
    assert api_get(client, list_url(world[0].pk), user_claims('kid')).status_code == 200
    assert api_delete(client, exp_url(mine), user_claims('kid')).status_code == 200


def test_sense_perfil_el_post_dona_profile_required_abans_que_edat(client, world):
    r = api_post(client, EXPERIENCES, user_claims('ghost'), new_body(world[0]))
    assert r.status_code == 403 and r.json()['error'] == 'profile_required'


def test_bloqueig_i_edat_van_abans_de_la_validacio_del_cos(client, world, blocked):
    r = api_post(client, EXPERIENCES, user_claims('blk'), {})
    assert r.status_code == 403 and r.json()['error'] == 'user_blocked'


# ---------- C1: propietat ----------

@pytest.mark.parametrize('uid', ['u2', 'u3'])
def test_c1_ningu_mes_pot_editar_ni_esborrar(client, world, uid):
    e = make_experience(world[0], 'u1', comment='meu')
    r1 = api_patch(client, exp_url(e), user_claims(uid), {'comment': 'x'})
    r2 = api_delete(client, exp_url(e), user_claims(uid))
    assert r1.status_code == r2.status_code == 403
    assert r1.json()['error'] == r2.json()['error'] == NOT_OWNER
    assert exp_ids() == [e] and exp_row(e)['comment'] == 'meu'


def test_un_admin_per_token_i_no_pel_cos(client, world):
    """`is_admin` surt del token verificat (§7.3.7), mai del cos de la petició ni de la query."""
    e = make_experience(world[0], 'u1')
    with patch(VERIFY, return_value=user_claims('u2')):
        r = client.delete(exp_url(e) + '?is_admin=true&creator_uid=u2', data='{"is_admin": true}',
                          content_type='application/json', HTTP_AUTHORIZATION='Bearer t')
    assert r.status_code == 403 and exp_ids() == [e]
    r = api_delete(client, exp_url(e), {'uid': 'u2', 'role': 'user', 'admin': True})
    assert r.status_code == 403 and exp_ids() == [e]


# ---------- ids hostils ----------

HOSTILE = ['a%00b', "1'%20OR%20'1'='1", '..%2F..%2Fetc', 'x' * 500, '0', '-1', 'ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ',
           '00000000-0000-0000-0000-000000000000']


@pytest.mark.parametrize('bad', HOSTILE)
def test_ids_hostils_donen_404_i_mai_500(client, world, bad):
    e = make_experience(world[0], 'u1')
    for r in (api_patch(client, exp_url(bad), user_claims('u1'), {'comment': 'x'}),
              api_delete(client, exp_url(bad), user_claims('u1')),
              api_get(client, list_url(bad), user_claims('u1')),
              api_post(client, EXPERIENCES, user_claims('u1'), {**new_body(world[0]), 'refuge_id': bad})):
        assert r.status_code == 404, (bad, r.status_code, r.content)
    assert exp_ids() == [e]
    sql('SELECT 1 FROM activity.experiences LIMIT 1')


def test_el_comentari_es_desa_tal_qual_sense_executar_res(client, world):
    payload = "'); DROP TABLE activity.experiences; --<script>alert(1)</script>"
    r = api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0], payload))
    assert r.status_code == 201 and r.json()['experience']['comment'] == payload
    assert sql('SELECT comment FROM activity.experiences') == [(payload,)]


def test_les_respostes_d_error_no_filtren_dades_personals(client, world):
    e = make_experience(world[0], 'u1', comment='secret')
    text = api_delete(client, exp_url(e), user_claims('u2')).content.decode()
    assert 'secret' not in text and 'u1' not in text
