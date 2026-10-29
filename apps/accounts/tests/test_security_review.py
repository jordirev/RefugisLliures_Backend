"""
Revisió de seguretat del chunk 3: forats trobats i garanties transversals.

- Meta-test: cap ruta de l'API pot quedar sense `HasProfile` per descuit (llista blanca explícita).
- Un UID de la URL amb un byte NUL no ha de provocar un 500 (psycopg el rebutja): 404.
- Cap endpoint propietari (`/users/{uid}/...`) deixa tocar dades alienes, tampoc a un admin.
"""
import uuid

import pytest
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

from apps.auth.permissions import HasProfile, IsFirebaseAdmin
from apps.accounts.tests.helpers import (
    FAV, VIS, USERS, admin_claims, api_delete, api_get, api_patch, api_post, make_refuge, make_user, sql, url,
    user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

# Rutes que NO exigeixen HasProfile, amb el motiu (qualsevol altra ruta l'ha de tenir).
PUBLIC_OR_EXEMPT = {
    'users_collection': 'POST /users/ crea el perfil',
    'health_check': 'ping públic',
}
# Endpoints només d'admin d'infraestructura (cache): no toquen dades d'usuari i han de funcionar sense Postgres.
ADMIN_ONLY_EXEMPT = {'cache'}


def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p


def _view_class(pattern):
    cb = pattern.callback
    return getattr(cb, 'cls', None) or getattr(cb, 'view_class', None)


def test_totes_les_rutes_de_l_api_exigeixen_has_profile_llevat_de_les_excepcions():
    sense = []
    for route, pattern in _walk(get_resolver().url_patterns):
        if not route.startswith('api/'):
            continue
        cls = _view_class(pattern)
        if cls is None or pattern.name in PUBLIC_OR_EXEMPT:
            continue
        classes = list(getattr(cls, 'permission_classes', []))
        if HasProfile in classes:
            continue
        if IsFirebaseAdmin in classes and any(k in route for k in ADMIN_ONLY_EXEMPT):
            continue
        sense.append((route, [c.__name__ for c in classes]))
    # Les vistes públiques de lectura (AllowAny) són l'única altra excepció admesa
    sense = [(r, c) for r, c in sense if c != ['AllowAny']]
    assert not sense, f'Rutes sense HasProfile: {sense}'


@pytest.mark.parametrize('claims_fn', [user_claims, admin_claims])
def test_uid_amb_nul_en_obtenir_un_perfil_alie_es_404(client, claims_fn):
    make_user('u1')
    r = api_get(client, USERS + 'a%00b/', claims_fn('u1'))
    assert r.status_code == 404, r.content


@pytest.mark.parametrize('claims_fn', [user_claims, admin_claims])
@pytest.mark.parametrize('method,suffix,body', [
    ('patch', '', {'username': 'hack'}),
    ('delete', '', None),
    ('delete', 'avatar/', None),
    ('patch', 'age-confirmation/', {'birth_date': '1990-01-01'}),
    ('get', f'{FAV}/', None),
    ('post', f'{FAV}/', {'refuge_id': 'x'}),
    ('get', f'{VIS}/', None),
    ('post', f'{VIS}/', {'refuge_id': 'x'}),
    ('delete', f'{FAV}/{uuid.uuid4()}/', None),
    ('delete', f'{VIS}/{uuid.uuid4()}/', None),
])
def test_cap_endpoint_propietari_deixa_tocar_un_altre_usuari(client, claims_fn, method, suffix, body):
    make_user('u1', username='original')
    make_user('u2', username='victima')
    refuge = make_refuge()
    path = f'{USERS}u2/{suffix}'
    if method == 'post':
        body = {'refuge_id': str(refuge.pk)}
    fn = {'get': lambda: api_get(client, path, claims_fn('u1')),
          'delete': lambda: api_delete(client, path, claims_fn('u1')),
          'patch': lambda: api_patch(client, path, claims_fn('u1'), body),
          'post': lambda: api_post(client, path, claims_fn('u1'), body)}[method]
    r = fn()
    assert r.status_code == 403, (r.status_code, r.content)
    assert sql("SELECT username FROM users.user_public_profiles WHERE uid = 'u2'") == [('victima',)]
    assert sql("SELECT count(*) FROM users.user_favourite_refuges WHERE user_uid = 'u2'") == [(0,)]
    assert sql("SELECT count(*) FROM users.user_visited_refuges WHERE user_uid = 'u2'") == [(0,)]
