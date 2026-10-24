"""Les respostes i els logs d'autenticació no filtren detalls interns ni identificadors personals."""
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from api.middleware.firebase_auth_middleware import FirebaseAuthenticationMiddleware

pytestmark = pytest.mark.unit

VERIFY = 'api.middleware.firebase_auth_middleware.auth.verify_id_token'


def _request(token='tok'):
    return RequestFactory().get('/api/users/', HTTP_AUTHORIZATION=f'Bearer {token}')


def _middleware():
    return FirebaseAuthenticationMiddleware(lambda req: HttpResponse())


def test_error_inesperat_no_retorna_el_detall_al_client():
    secret = 'Failed to connect to 10.1.2.3:5432 as app password=hunter2'
    with patch(VERIFY, side_effect=RuntimeError(secret)):
        r = _middleware().process_request(_request())
    assert r.status_code == 401
    assert secret not in r.content.decode()
    assert 'hunter2' not in r.content.decode()


def _logged(mock_logger):
    return ' '.join(str(c) for c in mock_logger.method_calls)


def test_error_inesperat_no_registra_el_missatge_original():
    with patch('api.middleware.firebase_auth_middleware.logger') as log,             patch(VERIFY, side_effect=RuntimeError('detall-intern-secret')):
        _middleware().process_request(_request())
    assert 'detall-intern-secret' not in _logged(log)
    assert 'RuntimeError' in _logged(log)


def test_token_valid_no_registra_l_uid():
    with patch('api.middleware.firebase_auth_middleware.logger') as log,             patch(VERIFY, return_value={'uid': 'uid-molt-personal', 'role': 'user'}):
        r = _middleware().process_request(_request())
    assert r is None
    assert 'uid-molt-personal' not in _logged(log)
