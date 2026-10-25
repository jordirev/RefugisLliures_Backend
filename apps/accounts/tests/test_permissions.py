"""
Permisos del chunk 3 (§7.3.6, §12 #1): 403 `profile_required` a tot endpoint autenticat llevat de `POST /users/`;
`IsNotBlocked`/`IsAgeConfirmed` llegeixen l'usuari de PostgreSQL (una sola lectura per peticio); lectures publiques
sense canvis; `scripts/manage_admins.py add` crea la fila de l'admin.
"""
import importlib.util
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import connection
from rest_framework import exceptions

from apps.accounts.tests.helpers import (
    PROFILE_REQUIRED, QueryCounter, USERS, admin_claims, api_delete, api_get, api_patch, api_post, at, make_media,
    make_refuge, make_user, sql, url, user_claims, user_row, years_ago, FAV, VIS)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SOME_ID = str(uuid.uuid4())

# (metode, ruta, cos): tots autenticats, amb un usuari SENSE fila a `users.users` -> 403 profile_required
AUTHENTICATED = [
    ('get', '/api/users/ghost/', None),
    ('get', '/api/users/other/', None),
    ('patch', '/api/users/ghost/', {'username': 'abc'}),
    ('delete', '/api/users/ghost/', None),
    ('delete', '/api/users/ghost/avatar/', None),
    ('patch', '/api/users/ghost/age-confirmation/', {'birth_date': '1990-01-01'}),
    ('get', '/api/users/ghost/favorite-refuges/', None),
    ('post', '/api/users/ghost/favorite-refuges/', {'refuge_id': SOME_ID}),
    ('delete', f'/api/users/ghost/favorite-refuges/{SOME_ID}/', None),
    ('get', '/api/users/ghost/visited-refuges/', None),
    ('post', '/api/users/ghost/visited-refuges/', {'refuge_id': SOME_ID}),
    ('delete', f'/api/users/ghost/visited-refuges/{SOME_ID}/', None),
    # dominis que continuen a Firestore o a altres apps: la mateixa classe de permis
    ('get', '/api/users/ghost/visits/', None),
    ('get', '/api/users/ghost/moderation-notices/', None),
    ('get', f'/api/refuges/{SOME_ID}/media/', None),
    ('delete', f'/api/refuges/{SOME_ID}/media/k%2Fx.webp/', None),
    ('post', '/api/media/upload-intents/', {}),
    ('post', '/api/media/reports/', {}),
    ('get', '/api/renovations/', None),
    ('get', '/api/experiences/?refuge_id=x', None),
    ('get', '/api/doubts/?refuge_id=x', None),
    ('get', '/api/my-refuges-proposals/', None),
]


def call(client, method, path, claims, body=None):
    fn = {'get': api_get, 'delete': api_delete}.get(method)
    if fn:
        return fn(client, path, claims)
    return {'post': api_post, 'patch': api_patch}[method](client, path, claims, body)


@pytest.mark.parametrize('method,path,body', AUTHENTICATED)
def test_sense_perfil_403_profile_required(client, method, path, body):
    r = call(client, method, path, user_claims('ghost'), body)
    assert r.status_code == 403, (r.status_code, r.content)
    assert r.json()['error'] == PROFILE_REQUIRED


@pytest.mark.parametrize('method,path,body', AUTHENTICATED[:12])
def test_sense_perfil_com_a_admin_tambe_403(client, method, path, body):
    r = call(client, method, path, admin_claims('ghost'), body)
    assert r.status_code == 403 and r.json()['error'] == PROFILE_REQUIRED


@pytest.mark.parametrize('path', ['/api/admin/media-reports/'])
def test_endpoints_d_admin_sense_perfil_403_profile_required(client, path):
    r = api_get(client, path, admin_claims('ghost'))
    assert r.status_code == 403 and r.json()['error'] == PROFILE_REQUIRED


def test_profile_required_no_toca_les_dades_ni_crea_el_perfil(client):
    r = call(client, 'post', '/api/users/ghost/favorite-refuges/', user_claims('ghost'), {'refuge_id': SOME_ID})
    assert r.status_code == 403 and r.json()['error'] == PROFILE_REQUIRED
    assert user_row('ghost') is None


def test_amb_perfil_el_mateix_endpoint_ja_no_es_profile_required(client):
    make_user('u1')
    r = api_get(client, '/api/users/u1/', user_claims('u1'))
    assert r.status_code == 200


def test_anonim_continua_sent_401_i_no_profile_required(client):
    for method, path, body in AUTHENTICATED[:8]:
        r = call(client, method, path, None, body)
        assert r.status_code == 401, path


def test_post_users_es_l_unica_excepcio(client):
    r = api_post(client, USERS, user_claims('ghost'), {'username': 'Nou'})
    assert r.status_code == 201


def test_les_lectures_publiques_no_canvien_sense_perfil(client):
    r = make_refuge(name='Public')
    tok = user_claims('ghost')
    assert api_get(client, '/api/refuges/', tok).status_code == 200
    assert api_get(client, f'/api/refuges/{r.pk}/', tok).status_code == 200
    assert api_get(client, '/api/refuges/').status_code == 200
    # El health check consulta Firestore (bloquejat als tests: 503): només cal que no demani perfil (403) ni login.
    assert api_get(client, '/api/health/', tok).status_code in (200, 503)
    assert api_get(client, '/api/health/').status_code in (200, 503)


def test_el_perfil_d_un_altre_no_compta(client):
    make_user('u2')
    r = api_get(client, '/api/users/u2/', user_claims('ghost'))
    assert r.status_code == 403 and r.json()['error'] == PROFILE_REQUIRED


# =================================== IsNotBlocked / IsAgeConfirmed des de PostgreSQL ===================================

UPLOAD = '/api/media/upload-intents/'


def test_usuari_bloquejat_403_user_blocked(client):
    make_user('u1', age_confirmed_at=at(0), age_threshold=16)
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u1'")
    r = api_post(client, UPLOAD, user_claims('u1'), {})
    assert r.status_code == 403
    assert r.json()['error'] == 'user_blocked' and r.json()['code'] == 'user_blocked'


def test_usuari_sense_edat_confirmada_403_age_not_confirmed(client):
    make_user('u1')
    r = api_post(client, UPLOAD, user_claims('u1'), {})
    assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed'


def test_bloquejat_te_prioritat_sobre_edat_no_confirmada(client):
    make_user('u1')
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'csam_confirmed', blocked_at = now() "
        "WHERE uid = 'u1'")
    assert api_post(client, UPLOAD, user_claims('u1'), {}).json()['error'] == 'user_blocked'


def test_usuari_adult_i_no_bloquejat_passa_els_permisos(client):
    make_user('u1', age_confirmed_at=at(0), age_threshold=16)
    r = api_post(client, UPLOAD, user_claims('u1'), {})           # cos buit: arriba al serializer -> 400
    assert r.status_code == 400


def test_els_permisos_llegeixen_de_postgres_no_de_firestore(client):
    """El conftest arrel bloqueja Firestore: si el permis hi anes, fallaria amb RuntimeError."""
    make_user('u1', age_confirmed_at=at(0), age_threshold=16)
    with patch('api.services.firestore_service.FirestoreService.get_db', side_effect=AssertionError('Firestore!')):
        assert api_post(client, UPLOAD, user_claims('u1'), {}).status_code == 400


def test_els_permisos_no_depenen_de_cache(client):
    make_user('u1', age_confirmed_at=at(0), age_threshold=16)
    assert api_post(client, UPLOAD, user_claims('u1'), {}).status_code == 400
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'u1'")
    assert api_post(client, UPLOAD, user_claims('u1'), {}).status_code == 403          # efecte immediat


def test_una_sola_lectura_de_users_per_peticio_amb_els_tres_permisos(client):
    """§7.3.6: HasProfile + IsNotBlocked + IsAgeConfirmed comparteixen l'objecte (cache a `request`, no a Redis)."""
    make_user('u1')                                                   # sense edat: arriba fins a IsAgeConfirmed
    with QueryCounter() as q:
        r = api_post(client, UPLOAD, user_claims('u1'), {})
    assert r.status_code == 403 and r.json()['error'] == 'age_not_confirmed'
    reads = [s for s in q.queries if s.lstrip().upper().startswith('SELECT') and '"users"."users"' in s]
    assert len(reads) == 1, q.queries


@pytest.fixture
def perm():
    from api import permissions
    return permissions


class _Req:
    def __init__(self, uid):
        self.user_uid = uid
        self.user = type('U', (), {'is_authenticated': True, 'uid': uid})()


def test_is_not_blocked_unitari(perm):
    from apps.core.rls import rls_context
    make_user('ok')
    make_user('bad')
    sql("UPDATE users.users SET is_blocked = true, blocked_reason = 'strikes', blocked_at = now() WHERE uid = 'bad'")
    with rls_context(uid='ok'):
        assert perm.IsNotBlocked().has_permission(_Req('ok'), None) is True
    with rls_context(uid='bad'):
        with pytest.raises(exceptions.PermissionDenied) as exc:
            perm.IsNotBlocked().has_permission(_Req('bad'), None)
    assert exc.value.detail['error'] == 'user_blocked'


def test_is_age_confirmed_unitari(perm):
    from apps.core.rls import rls_context
    make_user('adult', age_confirmed_at=at(0), age_threshold=16)
    make_user('nope')
    with rls_context(uid='adult'):
        assert perm.IsAgeConfirmed().has_permission(_Req('adult'), None) is True
    with rls_context(uid='nope'):
        with pytest.raises(exceptions.PermissionDenied) as exc:
            perm.IsAgeConfirmed().has_permission(_Req('nope'), None)
    assert exc.value.detail['error'] == 'age_not_confirmed'


def test_is_age_confirmed_sense_fila_es_denega(perm):
    from apps.core.rls import rls_context
    with rls_context(uid='fantasma'):
        with pytest.raises(exceptions.PermissionDenied):
            perm.IsAgeConfirmed().has_permission(_Req('fantasma'), None)


# =================================== scripts/manage_admins.py add ===================================

@pytest.fixture
def manage_admins():
    """Carrega l'script sense inicialitzar Firebase (`firebase_admin._apps` no buit) i amb `auth` mockejat."""
    import firebase_admin
    path = Path(__file__).resolve().parents[3] / 'scripts' / 'manage_admins.py'
    spec = importlib.util.spec_from_file_location('manage_admins_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(firebase_admin._apps, {'[DEFAULT]': object()}):
        spec.loader.exec_module(module)
    user = type('FbUser', (), {'email': 'a@example.org', 'custom_claims': {}})()
    with patch.object(module.auth, 'get_user', return_value=user), \
            patch.object(module.auth, 'set_custom_user_claims') as set_claims:
        module.set_claims = set_claims
        yield module
    sys.modules.pop('manage_admins_under_test', None)


def test_manage_admins_add_crea_la_fila_i_el_perfil_de_l_admin(manage_admins):
    assert user_row('adm1') is None
    assert manage_admins.add_admin('adm1') is True
    manage_admins.set_claims.assert_called_once()
    assert user_row('adm1') is not None
    assert sql("SELECT username FROM users.user_public_profiles WHERE uid = 'adm1'") == [('',)]


def test_manage_admins_add_es_idempotent_i_no_trepitja_un_perfil_existent(manage_admins):
    make_user('adm1', username='Admin', language_id='ca')
    assert manage_admins.add_admin('adm1') is True
    assert sql("SELECT username FROM users.user_public_profiles WHERE uid = 'adm1'") == [('Admin',)]
    assert user_row('adm1')['language'] == 'ca'


def test_l_admin_creat_amb_l_script_pot_fer_servir_l_api(client, manage_admins):
    manage_admins.add_admin('adm1')
    assert api_get(client, '/api/users/adm1/', admin_claims('adm1')).status_code == 200
