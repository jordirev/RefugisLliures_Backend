"""
Configuració i inicialització de Firebase Admin SDK
"""
import firebase_admin
from firebase_admin import credentials
import os
import json
from django.conf import settings
from dotenv import load_dotenv
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


def _is_production_environment():
    """Detecta si estem en un entorn de producció (Render, GitHub Actions, etc.)"""
    return (
        _is_render_environment() or
        _env_flag('PRODUCTION') or
        _env_flag('CI')  # GitHub Actions configura CI=true
    )


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


def _initialize_firebase_production():
    logger.info("🌐 Entorn: PRODUCCIÓ (Render/GitHub Actions/CI)")
    firebase_creds = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
    
    if not firebase_creds:
        raise ValueError("Variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY no trobada")
    
    logger.info("🔐 Carregant credencials de Firebase des de variable d'entorn")
    cred_dict = json.loads(firebase_creds)
    cred = credentials.Certificate(cred_dict)
    
    firebase_admin.initialize_app(cred, {
        'projectId': cred_dict.get('project_id')
    })
    logger.info(f"✅ Firebase inicialitzat (Producció) amb project_id: {cred_dict.get('project_id')}")


def _initialize_firebase_local():
    logger.info("🏠 Entorn: LOCAL")
    
    # Carrega variables d'entorn des de env/.env.development
    env_path = os.path.join(settings.BASE_DIR, 'env', '.env.development')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f"� Variables d'entorn carregades de: {env_path}")
    
    # Busca el fitxer de credencials
    cred_path = os.path.join(settings.BASE_DIR, 'env', 'firebase-service-account.json')
    
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Fitxer de credencials no trobat: {cred_path}")
    
    logger.info(f"📁 Carregant credencials de: {cred_path}")
    
    with open(cred_path, 'r') as f:
        cred_data = json.load(f)
    
    project_id = cred_data.get('project_id')
    logger.info(f"🔑 Project ID: {project_id}")
    
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'projectId': project_id
    })
    logger.info("✅ Firebase inicialitzat (Local) correctament")


def initialize_firebase():
    """
    Inicialitza Firebase Admin SDK si encara no s'ha inicialitzat.
    - En producció (Render/GitHub Actions): usa la variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY
    - En local: carrega les variables d'entorn des de env/.env.development i busca el fitxer JSON
    - Amb FIREBASE_AUTH_EMULATOR_HOST (Firebase Auth Emulator): sense credencials, només un projectId
    - En tests: no inicialitza Firebase
    
    Detecta automàticament l'entorn segons les variables:
    - RENDER=true (Render)
    - PRODUCTION=true (configuració manual)
    - CI=true (GitHub Actions i altres CI/CD)
    """
    if _is_testing_environment():
        logger.info("🧪 Entorn de testing detectat - Firebase NO s'inicialitza")
        return
    
    if not firebase_admin._apps:
        try:
            if _auth_emulator_host():
                _initialize_firebase_emulator()
            elif _is_production_environment():
                _initialize_firebase_production()
            else:
                _initialize_firebase_local()
        except Exception as e:
            logger.error(f"❌ Error inicialitzant Firebase Admin SDK: {str(e)}")
            raise
    else:
        logger.info("ℹ️ Firebase Admin SDK ja estava inicialitzat")
