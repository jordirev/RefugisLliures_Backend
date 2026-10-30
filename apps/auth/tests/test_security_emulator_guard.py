"""Guard de seguretat del Firebase Auth Emulator: accepta tokens sense signatura, mai fora d'un entorn local."""
from unittest.mock import patch

import firebase_admin
import pytest

from apps.auth import firebase_config

pytestmark = pytest.mark.unit

_ENV = ('RENDER', 'PRODUCTION', 'CI', 'K_SERVICE', 'K_REVISION', 'CLOUD_RUN_JOB', 'RENDER_SERVICE_ID',
        'FIREBASE_SERVICE_ACCOUNT_KEY', 'FIREBASE_AUTH_EMULATOR_HOST', 'GCLOUD_PROJECT', 'GOOGLE_CLOUD_PROJECT')


@pytest.fixture
def entorn(monkeypatch, settings):
    settings.FIREBASE_SERVICE_ACCOUNT_KEY = None
    for v in _ENV:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(firebase_config, '_is_testing_environment', lambda: False)
    monkeypatch.setattr(firebase_admin, '_apps', {})
    return monkeypatch


def _inicialitza_amb_emulador(entorn, host):
    entorn.setenv('FIREBASE_AUTH_EMULATOR_HOST', host)
    with patch('firebase_admin.initialize_app') as init:
        firebase_config.initialize_firebase()
    return init


def _ha_de_fallar(entorn):
    with patch('firebase_admin.initialize_app') as init:
        with pytest.raises(ValueError):
            firebase_config.initialize_firebase()
    init.assert_not_called()


@pytest.mark.parametrize('marker', ['K_SERVICE', 'K_REVISION', 'CLOUD_RUN_JOB', 'RENDER_SERVICE_ID'])
def test_emulador_prohibit_a_cloud_run_i_render_encara_que_production_no_estigui_posada(entorn, marker):
    """Cloud Run no defineix RENDER ni PRODUCTION: el guard no pot dependre només d'aquestes variables."""
    entorn.setenv(marker, 'refugis-api')
    entorn.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')
    _ha_de_fallar(entorn)


@pytest.mark.parametrize('valor', ['true', 'True', 'TRUE', '1', 'yes', ' true '])
@pytest.mark.parametrize('var', ['RENDER', 'PRODUCTION'])
def test_emulador_prohibit_amb_qualsevol_forma_de_veritat(entorn, var, valor):
    entorn.setenv(var, valor)
    entorn.setenv('FIREBASE_AUTH_EMULATOR_HOST', '127.0.0.1:9099')
    _ha_de_fallar(entorn)


@pytest.mark.parametrize('host', [
    'evil.example.com:9099', '10.0.0.5:9099', 'localhost.evil.com:9099', 'http://evil.com:9099',
    'firebase.googleapis.com', '0.0.0.0:9099', 'localhostx:9099',
])
def test_emulador_nomes_amb_hosts_locals(entorn, host):
    entorn.setenv('FIREBASE_AUTH_EMULATOR_HOST', host)
    _ha_de_fallar(entorn)


@pytest.mark.parametrize('host', [
    'localhost:9099', 'LOCALHOST:9099', '127.0.0.1:9099', '[::1]:9099', '::1', 'host.docker.internal:9099',
    'http://localhost:9099',
])
def test_emulador_permes_amb_hosts_locals(entorn, host):
    _inicialitza_amb_emulador(entorn, host).assert_called_once()


def test_emulador_a_ci_continua_permes_en_local(entorn):
    """Els e2e de CI usen l'emulador (decisió del chunk); la protecció és el host local i les marques de plataforma."""
    entorn.setenv('CI', 'true')
    _inicialitza_amb_emulador(entorn, 'localhost:9099').assert_called_once()


def test_sense_emulador_en_plataforma_exigeix_service_account(entorn):
    entorn.setenv('K_SERVICE', 'refugis-api')
    entorn.setenv('PRODUCTION', 'true')
    _ha_de_fallar(entorn)
