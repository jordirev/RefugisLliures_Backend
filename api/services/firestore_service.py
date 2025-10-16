"""
Servei per gestionar la connexió amb Firestore
"""
import os
import json
import logging
from django.conf import settings
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

class FirestoreService:
    """Servei singleton per gestionar la connexió amb Firestore"""
    
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreService, cls).__new__(cls)
        return cls._instance
    
    def get_db(self):
        """Obté la connexió amb Firestore"""
        if self._db is not None:
            return self._db
        
        try:
            # Comprova si Firebase ja està inicialitzat
            app = firebase_admin.get_app()
            self._db = firestore.client(app)
            return self._db
        except ValueError:
            # Inicialitza Firebase
            return self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Inicialitza Firebase Admin SDK"""
        try:
            cred = None
            
            # Primer, intentem utilitzar la variable d'entorn FIREBASE_SERVICE_ACCOUNT_KEY
            if hasattr(settings, 'FIREBASE_SERVICE_ACCOUNT_KEY') and settings.FIREBASE_SERVICE_ACCOUNT_KEY:
                try:
                    # Parsejem el JSON de la variable d'entorn
                    service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_KEY)
                    cred = credentials.Certificate(service_account_info)
                    logger.info('Firebase credentials loaded from environment variable')
                except json.JSONDecodeError as e:
                    logger.error(f'Error parsing Firebase credentials from environment variable: {str(e)}')
                    raise e
            else:
                # Si no hi ha variable d'entorn, intentem llegir des del fitxer
                cred_path = os.path.join(settings.BASE_DIR, settings.GOOGLE_APPLICATION_CREDENTIALS)
                
                if not os.path.exists(cred_path):
                    logger.error(f'Firebase credentials file not found at {cred_path}')
                    raise FileNotFoundError(f'Firebase credentials file not found at {cred_path}')
                    
                cred = credentials.Certificate(cred_path)
                logger.info(f'Firebase credentials loaded from file: {cred_path}')
            
            # Inicialitzem Firebase amb les credencials
            firebase_admin.initialize_app(cred)
            self._db = firestore.client()
            
            logger.info('Firebase initialized successfully')
            return self._db
            
        except Exception as e:
            logger.error(f'Error initializing Firebase: {str(e)}')
            raise e

# Instància global del servei
firestore_service = FirestoreService()