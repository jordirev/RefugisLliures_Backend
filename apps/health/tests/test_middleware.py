"""Middleware del health check: un error de BD a `/api/health/` es converteix en 503."""
from unittest.mock import patch

import pytest
from django.db.utils import OperationalError
from django.test import RequestFactory

pytestmark = pytest.mark.unit


def test_middleware_health_converteix_error_de_bd_en_503():
    from apps.health.middleware import HealthDatabaseErrorMiddleware
    mw = HealthDatabaseErrorMiddleware(lambda r: None)
    r = mw.process_exception(RequestFactory().get('/api/health/'), OperationalError('connection refused'))
    assert r.status_code == 503
    assert b'"database": false' in r.content and b'unhealthy' in r.content
    assert b'refused' not in r.content


def test_middleware_health_ignora_altres_rutes_i_errors():
    from apps.health.middleware import HealthDatabaseErrorMiddleware
    mw = HealthDatabaseErrorMiddleware(lambda r: None)
    assert mw.process_exception(RequestFactory().get('/api/users/'), OperationalError('x')) is None
    assert mw.process_exception(RequestFactory().get('/api/health/'), ValueError('x')) is None
