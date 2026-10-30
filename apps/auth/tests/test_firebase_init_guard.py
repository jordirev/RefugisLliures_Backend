"""Guarda de l'emulador de Firebase Auth: prohibit a producció (RENDER/PRODUCTION)."""
from unittest.mock import patch

import firebase_admin
import pytest

from apps.auth import firebase_config

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('var', ['RENDER', 'PRODUCTION'])
def test_emulador_prohibit_en_produccio(monkeypatch, settings, var):
    for v in ('RENDER', 'PRODUCTION', 'CI', 'FIREBASE_SERVICE_ACCOUNT_KEY'):
        monkeypatch.delenv(v, raising=False)
    settings.FIREBASE_SERVICE_ACCOUNT_KEY = None
    monkeypatch.setattr(firebase_config, '_is_testing_environment', lambda: False)
    monkeypatch.setattr(firebase_admin, '_apps', {})
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    monkeypatch.setenv(var, 'true')
    with patch('firebase_admin.initialize_app') as init:
        with pytest.raises(ValueError):
            firebase_config.initialize_firebase()
    init.assert_not_called()
