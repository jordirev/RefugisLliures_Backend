"""Suport del Firebase Auth Emulator a `api/firebase_config.py` (e2e sense credencials reals)."""
from unittest.mock import patch, MagicMock

import firebase_admin
import pytest
from firebase_admin import credentials

from api import firebase_config

pytestmark = pytest.mark.unit

_ENV_NETEJA = ('RENDER', 'PRODUCTION', 'CI', 'FIREBASE_SERVICE_ACCOUNT_KEY', 'FIREBASE_AUTH_EMULATOR_HOST',
               'GCLOUD_PROJECT', 'GOOGLE_CLOUD_PROJECT')


@pytest.fixture
def entorn_net(monkeypatch):
    for v in _ENV_NETEJA:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(firebase_config, '_is_testing_environment', lambda: False)
    monkeypatch.setattr(firebase_admin, '_apps', {})
    return monkeypatch


def _init_args(mock_init):
    mock_init.assert_called_once()
    args, kwargs = mock_init.call_args
    cred = kwargs.get('credential', args[0] if args else None)
    options = kwargs.get('options', args[1] if len(args) > 1 else None)
    return cred, options


@pytest.mark.parametrize('ci', [None, 'true'])
def test_amb_emulador_no_cal_service_account(entorn_net, ci):
    entorn_net.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    if ci:
        entorn_net.setenv('CI', ci)   # GitHub Actions: abans exigia FIREBASE_SERVICE_ACCOUNT_KEY
    with patch('firebase_admin.initialize_app') as mock_init, \
            patch.object(credentials, 'Certificate', side_effect=AssertionError('no hauria de carregar cap service account')):
        firebase_config.initialize_firebase()
    cred, options = _init_args(mock_init)
    assert not isinstance(cred, credentials.Certificate)
    assert options and options.get('projectId'), "l'emulador necessita un projectId (p. ex. 'demo-...')"


def test_amb_emulador_respecta_gcloud_project(entorn_net):
    entorn_net.setenv('FIREBASE_AUTH_EMULATOR_HOST', '127.0.0.1:9099')
    entorn_net.setenv('GCLOUD_PROJECT', 'demo-refugis-e2e')
    with patch('firebase_admin.initialize_app') as mock_init:
        firebase_config.initialize_firebase()
    _, options = _init_args(mock_init)
    assert options['projectId'] == 'demo-refugis-e2e'


def test_amb_emulador_no_llegeix_fitxers_de_credencials(entorn_net):
    entorn_net.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    with patch('firebase_admin.initialize_app'), \
            patch('builtins.open', side_effect=AssertionError('no s\'ha de llegir cap fitxer')), \
            patch('os.path.exists', return_value=False):
        firebase_config.initialize_firebase()


def test_amb_emulador_no_reinicialitza_si_ja_hi_ha_app(entorn_net):
    entorn_net.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    entorn_net.setattr(firebase_admin, '_apps', {'[DEFAULT]': MagicMock()})
    with patch('firebase_admin.initialize_app') as mock_init:
        firebase_config.initialize_firebase()
    mock_init.assert_not_called()


def test_sense_emulador_en_ci_continua_exigint_service_account(entorn_net):
    entorn_net.setenv('CI', 'true')
    with patch('firebase_admin.initialize_app') as mock_init:
        with pytest.raises(ValueError):
            firebase_config.initialize_firebase()
    mock_init.assert_not_called()


def test_emulador_buit_es_tracta_com_no_definit(entorn_net):
    entorn_net.setenv('FIREBASE_AUTH_EMULATOR_HOST', '')
    entorn_net.setenv('CI', 'true')
    with patch('firebase_admin.initialize_app') as mock_init:
        with pytest.raises(ValueError):
            firebase_config.initialize_firebase()
    mock_init.assert_not_called()
