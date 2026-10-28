"""Tests addicionals de la implementació del chunk 1: middleware del health, guarda de l'emulador, R2 sota demanda."""
from unittest.mock import patch

import firebase_admin
import pytest
from django.db.utils import OperationalError
from django.test import RequestFactory

from api import firebase_config

pytestmark = pytest.mark.unit


def test_middleware_health_converteix_error_de_bd_en_503():
    from api.middleware import HealthDatabaseErrorMiddleware
    mw = HealthDatabaseErrorMiddleware(lambda r: None)
    r = mw.process_exception(RequestFactory().get('/api/health/'), OperationalError('connection refused'))
    assert r.status_code == 503
    assert b'"database": false' in r.content and b'unhealthy' in r.content
    assert b'refused' not in r.content


def test_middleware_health_ignora_altres_rutes_i_errors():
    from api.middleware import HealthDatabaseErrorMiddleware
    mw = HealthDatabaseErrorMiddleware(lambda r: None)
    assert mw.process_exception(RequestFactory().get('/api/users/'), OperationalError('x')) is None
    assert mw.process_exception(RequestFactory().get('/api/health/'), ValueError('x')) is None


@pytest.mark.parametrize('var', ['RENDER', 'PRODUCTION'])
def test_emulador_prohibit_en_produccio(monkeypatch, var):
    for v in ('RENDER', 'PRODUCTION', 'CI', 'FIREBASE_SERVICE_ACCOUNT_KEY'):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(firebase_config, '_is_testing_environment', lambda: False)
    monkeypatch.setattr(firebase_admin, '_apps', {})
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    monkeypatch.setenv(var, 'true')
    with patch('firebase_admin.initialize_app') as init:
        with pytest.raises(ValueError):
            firebase_config.initialize_firebase()
    init.assert_not_called()
