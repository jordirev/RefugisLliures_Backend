"""
DAO per a la gestió d'usuaris amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service

logger = logging.getLogger(__name__)

class UserDAO:
    """Data Access Object per a usuaris"""
    
    COLLECTION_NAME = 'users'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
    
    def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """
        Crea un nou usuari a Firestore
        
        Args:
            user_data: Diccionari amb les dades de l'usuari
            
        Returns:
            str: UID de l'usuari creat o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()

            #crea un usuari i assigna uid automàticament
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            doc_ref.set(user_data)
            uid = doc_ref.id
            
            logger.info(f"Usuari creat amb UID: {uid}")
            return uid
            
        except Exception as e:
            logger.error(f"Error creant usuari: {str(e)}")
            return None
    
    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Obté un usuari per UID amb cache
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            Dict amb les dades de l'usuari o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('user_detail', uid=uid)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={uid}")
            doc = doc_ref.get()
            
            if doc.exists:
                user_data = doc.to_dict()
                user_data['uid'] = doc.id  # Assegura que l'UID estigui inclòs
                
                # Guarda a cache
                timeout = cache_service.get_timeout('user_detail')
                cache_service.set(cache_key, user_data, timeout)
                
                logger.log(23, f"Usuari trobat amb UID: {uid}")
                return user_data
            else:
                logger.warning(f"Usuari no trobat amb UID: {uid}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint usuari amb UID {uid}: {str(e)}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Obté un usuari per email amb cache
        
        Args:
            email: Email de l'usuari
            
        Returns:
            Dict amb les dades de l'usuari o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('user_email', email=email.lower())
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=email=={email}")
            query = db.collection(self.COLLECTION_NAME).where('email', '==', email).limit(1)
            docs = query.get()

            if docs:
                doc = docs[0]  # Agafa el primer document
                user_data = doc.to_dict()
                user_data['uid'] = doc.id
                
                # Guarda a cache
                timeout = cache_service.get_timeout('user_detail')
                cache_service.set(cache_key, user_data, timeout)
                
                logger.log(23, f"Usuari trobat amb email: {email}")
                return user_data
            
            logger.warning(f"Usuari no trobat amb email: {email}")
            return None
            
        except Exception as e:
            logger.error(f"Error obtenint usuari amb email {email}: {str(e)}")
            return None
    
    def update_user(self, uid: str, user_data: Dict[str, Any]) -> bool:
        """
        Actualitza les dades d'un usuari
        
        Args:
            uid: UID de l'usuari
            user_data: Diccionari amb les noves dades
            
        Returns:
            bool: True si s'ha actualitzat correctament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi
            logger.log(23, f"Firestore READ (exists check): collection={self.COLLECTION_NAME} document={uid}")
            if not doc_ref.get().exists:
                logger.warning(f"No es pot actualitzar, usuari no trobat amb UID: {uid}")
                return False
            
            # Actualitza les dades
            doc_ref.update(user_data)
            
            # Invalida cache relacionada
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            if 'email' in user_data:
                cache_service.delete(cache_service.generate_key('user_email', email=user_data['email']))
            
            logger.log(23, f"Usuari actualitzat amb UID: {uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualitzant usuari amb UID {uid}: {str(e)}")
            return False
    
    def delete_user(self, uid: str) -> bool:
        """
        Elimina un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si s'ha eliminat correctament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi
            logger.info(f"Firestore READ (exists check): collection={self.COLLECTION_NAME} document={uid}")
            if not doc_ref.get().exists:
                logger.warning(f"No es pot eliminar, usuari no trobat amb UID: {uid}")
                return False
            
            # Elimina l'usuari
            doc_ref.delete()
            
            # Invalida cache relacionada
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            
            logger.log(23, f"Usuari eliminat amb UID: {uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant usuari amb UID {uid}: {str(e)}")
            return False
    
    def user_exists(self, uid: str) -> bool:
        """
        Comprova si un usuari existeix
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si l'usuari existeix
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            logger.log(23, f"Firestore READ (exists check): collection={self.COLLECTION_NAME} document={uid}")
            return doc_ref.get().exists
            
        except Exception as e:
            logger.error(f"Error comprovant si existeix usuari amb UID {uid}: {str(e)}")
            return False