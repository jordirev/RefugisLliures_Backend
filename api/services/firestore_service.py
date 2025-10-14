"""
Servei per gestionar la connexió amb Firestore
"""
import os
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
            cred_path = os.path.join(settings.BASE_DIR, 'env', 'firebase-service-account.json')
            
            if not os.path.exists(cred_path):
                logger.error(f'Firebase credentials file not found at {cred_path}')
                raise FileNotFoundError(f'Firebase credentials file not found at {cred_path}')
                
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            self._db = firestore.client()
            
            logger.info('Firebase initialized successfully')
            return self._db
            
        except Exception as e:
            logger.error(f'Error initializing Firebase: {str(e)}')
            raise e

# Instància global del servei
firestore_service = FirestoreService()