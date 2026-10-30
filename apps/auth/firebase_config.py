"""
Configuració i inicialització de Firebase Admin SDK
"""
import firebase_admin
from firebase_admin import credentials
import os
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _is_testing_environment():
    import sys
    return 'pytest' in sys.modules or os.environ.get('TESTING') == 'true'


def _env_flag(name):
    """Interpreta una variable com a booleana (`true`, `1`, `yes`, `on`; sense distingir majúscules)."""
    return (os.environ.get(name) or '').strip().lower() in ('true', '1', 'yes', 'on')


def _is_render_environment():
    return _env_flag('RENDER')


# Variables que defineix la plataforma (Cloud Run / Cloud Run Jobs / Render): no depenen de cap configuració manual.
_PLATFORM_MARKERS = ('K_SERVICE', 'K_REVISION', 'CLOUD_RUN_JOB', 'RENDER_SERVICE_ID')


def _is_deployed_platform():
    """True si s'executa en una plataforma gestionada (Cloud Run o Render), encara que `PRODUCTION` no estigui posada."""
    return _is_render_environment() or any(os.environ.get(m) for m in _PLATFORM_MARKERS)


# L'emulador només pot ser a la màquina local (o al host Docker): mai un servei remot.
_EMULATOR_ALLOWED_HOSTS = frozenset({'localhost', '127.0.0.1', '::1', 'host.docker.internal'})


def _emulator_hostname(value):
    """Nom de host de `host:port` (admet `[::1]:9099`, `::1` i URLs amb esquema)."""
    value = value.strip().lower()
    if '://' in value:
        value = value.split('://', 1)[1]
    value = value.split('/', 1)[0]
    if value.startswith('['):
        return value[1:].split(']', 1)[0]
    if value.count(':') == 1:
        return value.split(':', 1)[0]
    return value


def _auth_emulator_host():
    """Host del Firebase Auth Emulator (e2e locals) o cadena buida si no n'hi ha."""
    return (os.environ.get('FIREBASE_AUTH_EMULATOR_HOST') or '').strip()


def _initialize_firebase_emulator():
    """
    Inicialitza Firebase Admin per al Firebase Auth Emulator: no cal cap service account (ni fitxer ni variable).
    El SDK detecta `FIREBASE_AUTH_EMULATOR_HOST` i verifica els tokens (sense signatura) contra l'emulador; només
    cal un `projectId` qualsevol (per defecte `demo-refugis-lliures`, o `GCLOUD_PROJECT`/`GOOGLE_CLOUD_PROJECT`).
    """
    # L'emulador accepta tokens sense signatura: qui en controli el host pot fer-se passar per qualsevol usuari
    # (admin inclòs). Mai en producció (Render, Cloud Run, PRODUCTION) i només cap a un host local.
    if _is_deployed_platform() or _env_flag('PRODUCTION'):
        raise ValueError("FIREBASE_AUTH_EMULATOR_HOST no es pot usar en un entorn de producció")
    if _emulator_hostname(_auth_emulator_host()) not in _EMULATOR_ALLOWED_HOSTS:
        raise ValueError("FIREBASE_AUTH_EMULATOR_HOST només pot apuntar a localhost, 127.0.0.1, ::1 o host.docker.internal")
    project_id = (
        os.environ.get('GCLOUD_PROJECT')
        or os.environ.get('GOOGLE_CLOUD_PROJECT')
        or 'demo-refugis-lliures'
    )
    logger.info(f"Entorn: Firebase Auth Emulator ({_auth_emulator_host()}), projectId={project_id}")
    firebase_admin.initialize_app(options={'projectId': project_id})


def _initialize_firebase_service_account():
    # JSON en una sola línia: `settings` el llegeix de l'entorn real (Render, Cloud Run, GitHub Actions) o, si no hi és,
    # de `env/.env.<entorn>` (`PRODUCTION=true` carrega `.env.production`)
    firebase_creds = settings.FIREBASE_SERVICE_ACCOUNT_KEY

    if not firebase_creds:
        raise ValueError("Variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY no trobada")

    cred_dict = json.loads(firebase_creds)
    cred = credentials.Certificate(cred_dict)

    firebase_admin.initialize_app(cred, {
        'projectId': cred_dict.get('project_id')
    })
    logger.info(f"✅ Firebase inicialitzat amb project_id: {cred_dict.get('project_id')}")


def initialize_firebase():
    """
    Inicialitza Firebase Admin SDK (només Auth) si encara no s'ha inicialitzat.
    - Amb FIREBASE_AUTH_EMULATOR_HOST (Firebase Auth Emulator, e2e locals): sense credencials, només un projectId
    - Altrament: el JSON del service account a FIREBASE_SERVICE_ACCOUNT_KEY (variable d'entorn o `env/.env.<entorn>`)
    - En tests: no inicialitza Firebase
    """
    if _is_testing_environment():
        logger.info("🧪 Entorn de testing detectat - Firebase NO s'inicialitza")
        return

    if not firebase_admin._apps:
        try:
            if _auth_emulator_host():
                _initialize_firebase_emulator()
            else:
                _initialize_firebase_service_account()
        except Exception as e:
            logger.error(f"❌ Error inicialitzant Firebase Admin SDK: {str(e)}")
            raise
    else:
        logger.info("ℹ️ Firebase Admin SDK ja estava inicialitzat")
