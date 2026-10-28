"""
Permisos i seguretat dels endpoints de propostes (chunk 8; CLAUDE.md gotcha 15, C1/C2).

- Anònim -> 401 a tots; sense fila a `users.users` (també admin) -> 403 `profile_required`, abans de res més.
- `POST /refuges-proposals/` (escriptura de contingut): `IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed`
  (decisió del PO, 26/10) -> 403 `user_blocked` / `age_not_confirmed`.
- `GET /refuges-proposals/`, `approve`, `reject`: `IsAuthenticated, HasProfile, IsFirebaseAdmin` -> 403 per a un usuari normal.
- `GET /my-refuges-proposals/`: `IsAuthenticated, HasProfile` (un bloquejat o sense edat confirmada llegeix el seu historial).
- Les vistes viuen a `apps.proposals.views` i les rutes s'inclouen des d'`apps.proposals.urls` (mateixos paths).
"""
import uuid

import pytest
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

from apps.proposals.tests.helpers import (
    MINE, PROPOSALS, admin_claims, api_get, api_post, approve_url, count_proposals, create_body, make_proposal,
    make_user, proposal_row, refuge_ids, reject_url, sql, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SOME = str(uuid.uuid4())
ENDPOINTS = [
    ('post', PROPOSALS, create_body()),
    ('get', PROPOSALS, None),
    ('get', MINE, None),
    ('post', approve_url(SOME), None),
    ('post', reject_url(SOME), {}),
]
ADMIN_ONLY = [e for e in ENDPOINTS if e[1] != MINE and not (e[0] == 'post' and e[1] == PROPOSALS)]


def call(client, method, path, claims, body=None):
    return api_get(client, path, claims) if method == 'get' else api_post(client, path, claims, body)


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_anonim_401(client, method, path, body):
    assert call(client, method, path, None, body).status_code == 401


@pytest.mark.parametrize('claims_fn', [user_claims, admin_claims])
@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_sense_perfil_403_profile_required(client, method, path, body, claims_fn):
    r = call(client, method, path, claims_fn('ghost'), body)
    assert r.status_code == 403 and r.json().get('error') == 'profile_required', r.content


def test_sense_perfil_no_es_crea_res(client, world):
    call(client, 'post', PROPOSALS, user_claims('ghost'), create_body())
    assert count_proposals() == 0 and sql("SELECT count(*) FROM users.users WHERE uid = 'ghost'") == [(0,)]


# ---------- només admin ----------

@pytest.mark.parametrize('method,path,body', ADMIN_ONLY)
def test_un_usuari_normal_403(client, world, method, path, body):
    assert call(client, method, path, user_claims('u1'), body).status_code == 403


def test_un_usuari_normal_no_pot_aprovar_ni_rebutjar_ni_la_seva_proposta(client, world):
    pid = make_proposal(creator='u1')
    n = len(refuge_ids())
    assert api_post(client, approve_url(pid), user_claims('u1')).status_code == 403
    assert api_post(client, reject_url(pid), user_claims('u1'), {'reason': 'x'}).status_code == 403
    assert proposal_row(pid)['status'] == 'pending' and len(refuge_ids()) == n


def test_el_403_va_abans_del_404_i_del_400(client, world):
    assert api_post(client, approve_url(SOME), user_claims('u1')).status_code == 403
    assert api_post(client, reject_url(SOME), user_claims('u1'), {'reason': 'x' * 3000}).status_code == 403


def test_un_usuari_normal_no_veu_la_llista_d_admin(client, world):
    make_proposal(creator='u1')
    r = api_get(client, PROPOSALS, user_claims('u1'))
    assert r.status_code == 403 and 'creator_uid' not in r.content.decode()


def test_el_claim_d_admin_ve_del_token_mai_del_cos(client, world):
    pid = make_proposal(creator='u1')
    r = api_post(client, reject_url(pid), user_claims('u1'), {'reason': 'x', 'role': 'admin', 'is_admin': True})
    assert r.status_code == 403 and proposal_row(pid)['status'] == 'pending'


# ---------- bloqueig i edat (només POST de creació) ----------

def test_post_usuari_bloquejat_403_user_blocked(client, world):
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u2'")
    r = api_post(client, PROPOSALS, user_claims('u2'), create_body())
    assert r.status_code == 403 and r.json()['error'] == 'user_blocked'
    assert count_proposals() == 0


def test_post_sense_edat_confirmada_403_age_not_confirmed(client, world):
    make_user('minor', age_confirmed_at=None, age_threshold=None)
    r = api_post(client, PROPOSALS, user_claims('minor'), create_body())
    assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed'
    assert count_proposals() == 0


def test_get_my_no_exigeix_ni_bloqueig_ni_edat(client, world):
    make_user('minor', age_confirmed_at=None, age_threshold=None)
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u2'")
    make_proposal(creator='u2')
    make_proposal(creator='minor', minutes=1)
    assert len(api_get(client, MINE, user_claims('u2')).json()) == 1
    assert len(api_get(client, MINE, user_claims('minor')).json()) == 1


# ---------- ubicació de les vistes ----------

def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def test_les_cinc_rutes_viuen_a_apps_proposals_i_son_les_d_avui():
    routes = {}
    for route, pattern in _walk(get_resolver().url_patterns):
        if route.startswith('api/refuges-proposals/') or route.startswith('api/my-refuges-proposals/'):
            cls = getattr(pattern.callback, 'cls', None) or getattr(pattern.callback, 'view_class', None)
            routes[route] = cls
    assert set(routes) == {'api/refuges-proposals/', 'api/my-refuges-proposals/',
                           'api/refuges-proposals/<str:id>/approve/', 'api/refuges-proposals/<str:id>/reject/'} or \
        set(routes) == {'api/refuges-proposals/', 'api/my-refuges-proposals/',
                        'api/refuges-proposals/<str:proposal_id>/approve/',
                        'api/refuges-proposals/<str:proposal_id>/reject/'}, routes
    for route, cls in routes.items():
        assert cls.__module__ == 'apps.proposals.views', (route, cls)


def test_la_vista_legacy_ja_no_existeix():
    with pytest.raises(ImportError):
        from api.views import refuge_proposal_views  # noqa: F401
