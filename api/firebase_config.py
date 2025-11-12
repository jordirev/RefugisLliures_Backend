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


def initialize_firebase():
    """
    Inicialitza Firebase Admin SDK si encara no s'ha inicialitzat.
    - A Render: usa la variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY
    - En local: carrega les variables d'entorn des de env/.env.development i busca el fitxer JSON
    - En tests: no inicialitza Firebase
    """
    # No inicialitzar Firebase durant els tests
    import sys
    if 'pytest' in sys.modules or os.environ.get('TESTING') == 'true':
        logger.info("🧪 Entorn de testing detectat - Firebase NO s'inicialitza")
        return
    
    if not firebase_admin._apps:
        try:
            # Detecta si estem a Render (servidor de producció)
            is_render = os.environ.get('RENDER') == 'true'
            
            if is_render:
                # PRODUCCIÓ (Render): Usar variable d'entorn
                logger.info("🌐 Entorn: PRODUCCIÓ (Render)")
                firebase_creds = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
                
                if not firebase_creds:
                    raise ValueError("Variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY no trobada a Render")
                
                logger.info("� Carregant credencials de Firebase des de variable d'entorn")
                cred_dict = json.loads(firebase_creds)
                cred = credentials.Certificate(cred_dict)
                
                firebase_admin.initialize_app(cred, {
                    'projectId': cred_dict.get('project_id')
                })
                logger.info(f"✅ Firebase inicialitzat (Render) amb project_id: {cred_dict.get('project_id')}")
                
            else:
                # LOCAL: Carregar variables d'entorn i buscar fitxer JSON
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
                
        except Exception as e:
            logger.error(f"❌ Error inicialitzant Firebase Admin SDK: {str(e)}")
            raise
    else:
        logger.info("ℹ️ Firebase Admin SDK ja estava inicialitzat")
