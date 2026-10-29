"""
Permisos i seguretat de les vistes de visites (chunk 4; CLAUDE.md gotcha 15; GOTCHAS #2).

- `permission_classes` com avui, amb `HasProfile` darrere d'`IsAuthenticated`:
  `RefugeVisitsAPIView` i `RefugeVisitDetailAPIView` = `[IsAuthenticated, HasProfile]`;
  `UserVisitsAPIView` = `[IsAuthenticated, HasProfile, IsSameUser]`. Noms de ruta: `refuge_visits`,
  `refuge_visit_detail`, `user_visits` (les vistes son a `apps.visits.views`; les rutes a `apps/visits/urls.py`).
- Les rutes de `/api/refuges/` son excloses del middleware per prefix: l'anonim ha de rebre 401 per `permission_classes`.
- Sense perfil -> 403 `profile_required`; `/users/{uid}/visits/` d'un altre -> 403 (tambe per a un admin).
- Un UID/id/data amb byte NUL no ha de provocar un 500 (psycopg el rebutja).
"""
import uuid

import pytest
from django.urls import resolve, reverse
from rest_framework.permissions import IsAuthenticated

from apps.auth.permissions import HasProfile, IsSameUser
from apps.visits.tests.helpers import (
    PROFILE_REQUIRED, admin_claims, api_delete, api_get, api_patch, api_post, day, make_refuge, make_user, make_visit,
    participant_rows, refuge_visits_url, sql, user_claims, user_visits_url, visit_rows, visit_url)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

RID = str(uuid.uuid4())
DATE = day(3).isoformat()
ENDPOINTS = [
    ('get', refuge_visits_url(RID), None),
    ('post', visit_url(RID, DATE), {'num_visitors': 1}),
    ('patch', visit_url(RID, DATE), {'num_visitors': 1}),
    ('delete', visit_url(RID, DATE), None),
    ('get', user_visits_url('ghost'), None),
]
CALL = {'get': api_get, 'post': api_post, 'patch': api_patch, 'delete': api_delete}


def call(client, method, path, claims, payload):
    if method in ('post', 'patch'):
        return CALL[method](client, path, claims, payload)
    return CALL[method](client, path, claims)


@pytest.mark.parametrize('name,kwargs,expected', [
    ('refuge_visits', {'refuge_id': RID}, [IsAuthenticated, HasProfile]),
    ('refuge_visit_detail', {'refuge_id': RID, 'visit_date': DATE}, [IsAuthenticated, HasProfile]),
    ('user_visits', {'uid': 'u1'}, [IsAuthenticated, HasProfile, IsSameUser]),
])
def test_permission_classes_i_modul_de_la_vista(name, kwargs, expected):
    cls = resolve(reverse(name, kwargs=kwargs)).func.cls
    assert cls.__module__ == 'apps.visits.views'
    assert list(cls.permission_classes) == expected


def test_les_urls_conserven_els_paths_d_abans():
    assert reverse('refuge_visits', kwargs={'refuge_id': RID}) == f'/api/refuges/{RID}/visits/'
    assert reverse('refuge_visit_detail', kwargs={'refuge_id': RID, 'visit_date': DATE}) == \
        f'/api/refuges/{RID}/visits/{DATE}/'
    assert reverse('user_visits', kwargs={'uid': 'u1'}) == '/api/users/u1/visits/'


@pytest.mark.parametrize('method,path,payload', ENDPOINTS)
def test_anonim_401(client, method, path, payload):
    resp = call(client, method, path, None, payload)
    assert resp.status_code == 401


@pytest.mark.parametrize('method,path,payload', ENDPOINTS)
def test_sense_perfil_403_profile_required(client, method, path, payload):
    resp = call(client, method, path, user_claims('ghost'), payload)
    assert resp.status_code == 403 and resp.json()['error'] == PROFILE_REQUIRED


@pytest.mark.parametrize('method,path,payload', ENDPOINTS)
def test_sense_perfil_com_a_admin_tambe_403(client, method, path, payload):
    resp = call(client, method, path, admin_claims('ghost'), payload)
    assert resp.status_code == 403 and resp.json()['error'] == PROFILE_REQUIRED


def test_sense_perfil_no_s_escriu_res(client):
    r = make_refuge()
    api_post(client, visit_url(r.pk, DATE), user_claims('ghost'), {'num_visitors': 1})
    assert visit_rows() == []


@pytest.mark.parametrize('claims', [user_claims('u2'), admin_claims('adm')])
def test_visites_d_un_altre_usuari_403_tambe_per_a_admin(client, claims):
    make_user('u1')
    make_user('u2')
    make_user('adm')
    r = make_refuge()
    make_visit(r, day(1), {'u1': 3})
    resp = api_get(client, user_visits_url('u1'), claims)
    assert resp.status_code == 403
    assert 'refuge_id' not in resp.content.decode()


BLOCK = ("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() "
         "WHERE uid = 'u1'")


def _scene(blocked=False, adult=True):
    fields = {} if adult else {'age_confirmed_at': None, 'age_threshold': None}
    make_user('u1', **fields)
    if blocked:
        sql(BLOCK)
    r = make_refuge()
    vid = make_visit(r, day(3), {'u1': 2})
    return r, vid


@pytest.mark.parametrize('blocked,adult,error', [(True, True, 'user_blocked'), (False, False, 'age_not_confirmed'),
                                                 (True, False, 'user_blocked')])
@pytest.mark.parametrize('method', ['post', 'patch'])
def test_bloquejat_o_sense_edat_no_pot_escriure_post_ni_patch(client, method, blocked, adult, error):
    r, vid = _scene(blocked, adult)
    path = visit_url(r.pk, day(4) if method == 'post' else day(3))
    resp = call(client, method, path, user_claims('u1'), {'num_visitors': 5})
    assert resp.status_code == 403 and resp.json()['error'] == error
    assert participant_rows(vid) == {'u1': 2} and len(visit_rows(r)) == 1


@pytest.mark.parametrize('blocked,adult', [(True, True), (False, False)])
def test_bloquejat_o_sense_edat_si_pot_llegir_i_esborrar(client, blocked, adult):
    r, vid = _scene(blocked, adult)
    u = user_claims('u1')
    assert api_get(client, refuge_visits_url(r.pk), u).status_code == 200
    assert api_get(client, user_visits_url('u1'), u).status_code == 200
    assert api_delete(client, visit_url(r.pk, day(3)), u).status_code == 200
    assert participant_rows(vid) == {}


def test_adult_i_no_bloquejat_pot_escriure(client):
    r, _ = _scene()
    assert api_post(client, visit_url(r.pk, day(4)), user_claims('u1'), {'num_visitors': 1}).status_code == 201
    assert api_patch(client, visit_url(r.pk, day(3)), user_claims('u1'), {'num_visitors': 1}).status_code == 200


@pytest.mark.parametrize('method', ['post', 'patch'])
def test_sense_perfil_profile_required_abans_que_edat(client, method):
    r = make_refuge()
    resp = call(client, method, visit_url(r.pk, DATE), user_claims('ghost'), {'num_visitors': 1})
    assert resp.status_code == 403 and resp.json()['error'] == PROFILE_REQUIRED


def test_el_uid_de_l_escriptura_surt_del_token_mai_de_la_url_ni_del_cos(client):
    make_user('u1')
    make_user('u2')
    r = make_refuge()
    vid = make_visit(r, day(3), {'u2': 5})
    api_patch(client, visit_url(r.pk, DATE), user_claims('u1'), {'num_visitors': 1, 'uid': 'u2'})
    api_delete(client, visit_url(r.pk, DATE), user_claims('u1'))
    assert participant_rows(vid) == {'u2': 5}                          # cap acció sobre la fila d'un altre


@pytest.mark.parametrize('path', ['/api/users/u%00x/visits/', '/api/refuges/%00/visits/',
                                  f'/api/refuges/{RID}/visits/2030-01-01%00/'])
def test_bytes_nul_a_la_url_no_provoquen_500(client, path):
    make_user('u1')
    for method in ('get', 'post', 'patch', 'delete'):
        resp = call(client, method, path, user_claims('u1'), {'num_visitors': 1})
        assert resp.status_code < 500, (method, path, resp.status_code)


def test_nul_a_l_uid_de_la_url_es_403_o_404(client):
    make_user('u1')
    resp = api_get(client, '/api/users/u1%00/visits/', user_claims('u1'))
    assert resp.status_code in (403, 404)


def test_cap_ruta_de_visites_queda_sense_has_profile():
    from django.urls import get_resolver
    from django.urls.resolvers import URLPattern, URLResolver

    def walk(patterns, prefix=''):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern):
                yield prefix + str(p.pattern), p
    routes = [(r, p) for r, p in walk(get_resolver().url_patterns) if r.startswith('api/') and 'visits/' in r]
    assert len(routes) == 3, [r for r, _ in routes]
    for route, pattern in routes:
        assert HasProfile in pattern.callback.cls.permission_classes, route
