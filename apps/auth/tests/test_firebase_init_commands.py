"""`FirebaseAuthConfig.ready()`: les comandes de gestió que no usen Firebase no n'inicialitzen el service account.

Motiu: `PRODUCTION=true python manage.py migrate` (p. ex. contra la BD de Neon de producció des d'un entorn local) no ha
de fallar perquè `FIREBASE_SERVICE_ACCOUNT_KEY` no és a `os.environ` (`decouple` llegeix `env/.env.production` però no
l'exporta, GOTCHAS #6). El servidor (gunicorn, `runserver`) sí que ha de fallar fort si falta la credencial.
"""
import sys
from unittest.mock import patch

import pytest
from django.apps import apps

pytestmark = pytest.mark.unit

COMMANDS = ['migrate', 'makemigrations', 'showmigrations', 'sqlmigrate', 'collectstatic', 'check_neon',
            'load_refuges', 'load_hash_blocklist', 'purge_audit_logs', 'purge_moderation', 'purge_upload_intents',
            'process_yesterday_visits']


def _ready(monkeypatch, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with patch('apps.auth.firebase_config.initialize_firebase') as init:
        apps.get_app_config('firebase_auth').ready()
    return init


@pytest.mark.parametrize('command', COMMANDS)
def test_les_comandes_sense_firebase_no_l_inicialitzen(monkeypatch, command):
    init = _ready(monkeypatch, ['manage.py', command, '--database=migrator'])
    init.assert_not_called()


def test_funciona_amb_ruta_completa_a_manage_py(monkeypatch):
    init = _ready(monkeypatch, ['/srv/app/manage.py', 'migrate'])
    init.assert_not_called()


@pytest.mark.parametrize('argv', [
    ['manage.py', 'runserver', '0.0.0.0:8000'],            # servidor de desenvolupament / e2e
    ['manage.py', 'shell'],
    ['manage.py', 'delete_user'],                          # qualsevol comanda no llistada continua inicialitzant
    ['manage.py'],                                         # sense subcomanda
    ['/usr/local/bin/gunicorn', 'refugis_lliures.wsgi'],   # producció (Render / Cloud Run)
    ['/usr/local/bin/gunicorn', 'migrate'],                # un argument que coincideix amb una comanda, però no és manage.py
    ['scripts/manage_admins.py', 'list'],
])
def test_la_resta_continua_inicialitzant_firebase(monkeypatch, argv):
    init = _ready(monkeypatch, argv)
    init.assert_called_once_with()


def test_el_servidor_falla_fort_sense_credencial_en_produccio(monkeypatch):
    """`runserver`/gunicorn amb `PRODUCTION=true` i sense `FIREBASE_SERVICE_ACCOUNT_KEY` continua donant error."""
    from apps.auth import firebase_config
    import firebase_admin
    for v in ('RENDER', 'CI', 'FIREBASE_SERVICE_ACCOUNT_KEY', 'FIREBASE_AUTH_EMULATOR_HOST'):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv('PRODUCTION', 'true')
    monkeypatch.setattr(firebase_config, '_is_testing_environment', lambda: False)
    monkeypatch.setattr(firebase_admin, '_apps', {})
    monkeypatch.setattr(sys, 'argv', ['manage.py', 'runserver'])
    with pytest.raises(ValueError):
        apps.get_app_config('firebase_auth').ready()
