"""
Configuració i inicialització de Firebase Admin SDK
"""
import firebase_admin
from firebase_admin import credentials
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def initialize_firebase():
    """
    Inicialitza Firebase Admin SDK si encara no s'ha inicialitzat
    """
    if not firebase_admin._apps:
        try:
            # Busca el fitxer de credencials a la carpeta env
            cred_path = os.path.join(settings.BASE_DIR, 'env', 'firebase-service-account.json')
            
            if os.path.exists(cred_path):
                logger.info(f"📁 Carregant credencials de: {cred_path}")
                
                # Llegeix el fitxer per obtenir el project_id
                import json
                with open(cred_path, 'r') as f:
                    service_account_info = json.load(f)
                
                project_id = service_account_info.get('project_id')
                logger.info(f"🔑 Project ID: {project_id}")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    'projectId': project_id
                })
                logger.info("✅ Firebase Admin SDK inicialitzat correctament amb credencials JSON")
            else:
                # Si no troba el fitxer, intenta amb les credencials per defecte
                logger.warning(f"⚠️ No s'ha trobat el fitxer: {cred_path}")
                firebase_admin.initialize_app()
                logger.info("✅ Firebase Admin SDK inicialitzat amb credencials per defecte")
                
        except Exception as e:
            logger.error(f"❌ Error inicialitzant Firebase Admin SDK: {str(e)}")
            raise
    else:
        logger.info("ℹ️ Firebase Admin SDK ja estava inicialitzat")
