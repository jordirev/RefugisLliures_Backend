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
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase Admin SDK inicialitzat correctament amb credencials JSON")
            else:
                # Si no troba el fitxer, intenta amb les credencials per defecte
                firebase_admin.initialize_app()
                logger.info("✅ Firebase Admin SDK inicialitzat amb credencials per defecte")
                
        except Exception as e:
            logger.error(f"❌ Error inicialitzant Firebase Admin SDK: {str(e)}")
            raise
    else:
        logger.info("ℹ️ Firebase Admin SDK ja estava inicialitzat")
