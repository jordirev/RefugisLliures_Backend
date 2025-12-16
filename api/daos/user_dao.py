"""
DAO per a la gestió d'usuaris amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from ..services.firestore_service import FirestoreService
from ..services.cache_service import cache_service
from ..mappers.user_mapper import UserMapper
from ..models.user import User

logger = logging.getLogger(__name__)

class UserDAO:
    """Data Access Object per a usuaris"""
    
    COLLECTION_NAME = 'users'
    
    def __init__(self):
        """Inicialitza el DAO amb la connexió a Firestore"""
        self.firestore_service = FirestoreService()
        self.mapper = UserMapper()
    
    def create_user(self, user_data: Dict[str, Any], uid: str) -> Optional[User]:
        """
        Crea un nou usuari a Firestore amb el UID del token de Firebase
        
        Args:
            user_data: Diccionari amb les dades de l'usuari
            uid: UID del token de Firebase que s'utilitzarà com a ID del document
            
        Returns:
            User: Instància del model User creada o None si hi ha error
        """
        try:
            db = self.firestore_service.get_db()

            # Crea un usuari amb l'UID del token de Firebase com a ID del document
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            doc_ref.set(user_data)
            
            # Invalida cache d'existència per email
            if 'email' in user_data:
                cache_service.delete(cache_service.generate_key('user_email_exists', email=user_data['email'].lower()))
            
            logger.info(f"Usuari creat amb UID: {uid}")
            return self.mapper.firebase_to_model(user_data)
            
        except Exception as e:
            logger.error(f"Error creant usuari: {str(e)}")
            return None
    
    def get_user_by_uid(self, uid: str) -> Optional[User]:
        """
        Obté un usuari per UID amb cache
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            User: Instància del model User o None si no existeix
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('user_detail', uid=uid)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firebase_to_model(cached_data)
        
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
                return self.mapper.firebase_to_model(user_data)
            else:
                logger.warning(f"Usuari no trobat amb UID: {uid}")
                return None
                
        except Exception as e:
            logger.error(f"Error obtenint usuari amb UID {uid}: {str(e)}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Obté un usuari per email (sense cache, ja que només s'usa internament)
        
        Args:
            email: Email de l'usuari
            
        Returns:
            User: Instància del model User o None si no existeix
        """
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=email=={email}")
            query = db.collection(self.COLLECTION_NAME).where(filter=self.firestore_service.firestore.FieldFilter('email', '==', email)).limit(1)
            docs = query.get()

            if docs:
                doc = docs[0]  # Agafa el primer document
                user_data = doc.to_dict()
                user_data['uid'] = doc.id
                
                logger.log(23, f"Usuari trobat amb email: {email}")
                return self.mapper.firebase_to_model(user_data)
            
            logger.warning(f"Usuari no trobat amb email: {email}")
            return None
            
        except Exception as e:
            logger.error(f"Error obtenint usuari amb email {email}: {str(e)}")
            return None
    
    def user_exists_by_email(self, email: str) -> bool:
        """
        Comprova si existeix un usuari amb l'email especificat (amb cache optimitzat)
        Aquest mètode només guarda un booleà a cache, evitant duplicació de dades
        
        Args:
            email: Email de l'usuari
            
        Returns:
            bool: True si l'usuari existeix, False altrament
        """
        # Genera clau de cache específica per existència
        cache_key = cache_service.generate_key('user_email_exists', email=email.lower())
        
        # Intenta obtenir de cache
        cached_result = cache_service.get(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} filter=email=={email} (exists check)")
            query = db.collection(self.COLLECTION_NAME).where(filter=self.firestore_service.firestore.FieldFilter('email', '==', email)).limit(1)
            docs = query.get()
            
            exists = len(docs) > 0
            
            # Guarda només el booleà a cache
            timeout = cache_service.get_timeout('user_detail')
            cache_service.set(cache_key, exists, timeout)
            
            logger.log(23, f"Email {email} {'existeix' if exists else 'no existeix'}")
            return exists
            
        except Exception as e:
            logger.error(f"Error comprovant existència d'usuari amb email {email}: {str(e)}")
            return False
    
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
            # Només invalida cache d'email si s'està canviant l'email
            if 'email' in user_data:
                cache_service.delete(cache_service.generate_key('user_email_exists', email=user_data['email'].lower()))
            
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
            
            # Comprova que l'usuari existeixi i obté l'email abans d'eliminar
            logger.info(f"Firestore READ (exists check): collection={self.COLLECTION_NAME} document={uid}")
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot eliminar, usuari no trobat amb UID: {uid}")
                return False
            
            # Obté l'email abans d'eliminar
            user_data = doc.to_dict()
            email = user_data.get('email')
            
            # Elimina l'usuari
            doc_ref.delete()
            
            # Invalida cache relacionada
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            if email:
                cache_service.delete(cache_service.generate_key('user_email_exists', email=email.lower()))
            
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
    
    def add_refugi_to_list(self, uid: str, refugi_id: str, list_name: str) -> tuple[bool, Optional[List[str]]]:
        """
        Afegeix un refugi a una llista de l'usuari (favourite_refuges o visited_refuges)
        
        Args:
            uid: UID de l'usuari
            refugi_id: ID del refugi a afegir
            list_name: Nom de la llista ('favourite_refuges' o 'visited_refuges')
            
        Returns:
            bool: True si s'ha afegit correctament
            Optional[List[str]]: Llista actualitzada després d'afegir el refugi, o None si hi ha error
        """
        try:
            # Primer obté l'usuari actual per veure si ja té el refugi a la llista
            user = self.get_user_by_uid(uid)
            if not user:
                logger.warning(f"No es pot afegir refugi, usuari no trobat amb UID: {uid}")
                return (False, None)
            
            # Obté la llista actual
            current_list = getattr(user, list_name, [])
            if current_list is None:
                current_list = []
            
            # Comprova si ja està a la llista
            if refugi_id in current_list:
                logger.info(f"Refugi {refugi_id} ja està a {list_name} de l'usuari {uid}")
                return (True, current_list)
            
            # Afegeix el refugi a la llista
            current_list.append(refugi_id)
            
            # Actualitza a Firestore
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            doc_ref.update({list_name: current_list})
            
            # Invalida cache de l'usuari i de la info dels refugis
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            cache_service.delete(cache_service.generate_key('user_refugis_info', uid=uid, list_name=list_name))
            
            logger.log(23, f"Refugi {refugi_id} afegit a {list_name} de l'usuari {uid}")
            return (True, current_list)
            
        except Exception as e:
            logger.error(f"Error afegint refugi {refugi_id} a {list_name} de l'usuari {uid}: {str(e)}")
            return (False, None)
    
    def remove_refugi_from_list(self, uid: str, refugi_id: str, list_name: str) -> tuple[bool, Optional[List[str]]]:
        """
        Elimina un refugi d'una llista de l'usuari (favourite_refuges o visited_refuges)
        
        Args:
            uid: UID de l'usuari
            refugi_id: ID del refugi a eliminar
            list_name: Nom de la llista ('favourite_refuges' o 'visited_refuges')
            
        Returns:
            bool: True si s'ha eliminat correctament
        """
        try:
            # Primer obté l'usuari actual
            user = self.get_user_by_uid(uid)
            if not user:
                logger.warning(f"No es pot eliminar refugi, usuari no trobat amb UID: {uid}")
                return (False, None)
            
            # Obté la llista actual
            current_list = getattr(user, list_name, [])
            if current_list is None:
                current_list = []
            
            # Comprova si el refugi no està a la llista
            if refugi_id not in current_list:
                logger.info(f"Refugi {refugi_id} no està a {list_name} de l'usuari {uid}")
                return (True, current_list)
            
            # Elimina el refugi de la llista
            current_list.remove(refugi_id)
            
            # Actualitza a Firestore
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            doc_ref.update({list_name: current_list})
            
            # Invalida cache de l'usuari i de la info dels refugis
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            cache_service.delete(cache_service.generate_key('user_refugis_info', uid=uid, list_name=list_name))
            
            logger.log(23, f"Refugi {refugi_id} eliminat de {list_name} de l'usuari {uid}")
            return (True, current_list)
            
        except Exception as e:
            logger.error(f"Error eliminant refugi {refugi_id} de {list_name} de l'usuari {uid}: {str(e)}")
            return (False, None)
    
    def get_refugis_info(self, uid: str, list_name: str, refugis_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Obté la informació dels refugis d'una llista de l'usuari
        Només retorna: id, name, region, places, coordinates
        
        Args:
            uid: UID de l'usuari
            list_name: Nom de la llista ('favourite_refuges' o 'visited_refuges')
            refugis_ids: Llista d'IDs de refugis (opcional). Si no es proporciona, s'obté de l'usuari.
            
        Returns:
            List[Dict]: Llista amb la informació dels refugis
        """
        # Genera clau de cache
        cache_key = cache_service.generate_key('user_refugis_info', uid=uid, list_name=list_name)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            if not refugis_ids:
                # Obté l'usuari
                user = self.get_user_by_uid(uid)
                if not user:
                    return []
                
                # Obté la llista de IDs
                refugis_ids = getattr(user, list_name, [])
                if not refugis_ids:
                    return []
            
            # Obté la informació de cada refugi
            db = self.firestore_service.get_db()
            refugis_info = []
            
            for refugi_id in refugis_ids:
                # Comprova primer si està a cache
                refugi_cache_key = cache_service.generate_key('refugi_detail', refugi_id=refugi_id)
                refugi_data = cache_service.get(refugi_cache_key)
                
                if refugi_data is None:
                    # Si no està a cache, obté de Firestore
                    doc_ref = db.collection('data_refugis_lliures').document(str(refugi_id))
                    logger.log(23, f"Firestore READ: collection=data_refugis_lliures document={refugi_id}")
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        refugi_data = doc.to_dict()
                        # Guarda a cache
                        timeout = cache_service.get_timeout('refugi_detail')
                        cache_service.set(refugi_cache_key, refugi_data, timeout)
                
                if refugi_data:
                    # Extreu només els camps necessaris
                    refugi_info = {
                        'id': refugi_id,
                        'name': refugi_data.get('name', ''),
                        'region': refugi_data.get('region', ''),
                        'places': refugi_data.get('places', 0),
                        'coord': refugi_data.get('coord', {})
                    }
                    refugis_info.append(refugi_info)
            
            # Guarda a cache
            timeout = cache_service.get_timeout('user_detail')
            cache_service.set(cache_key, refugis_info, timeout)
            
            logger.log(23, f"Informació de refugis de {list_name} obtinguda per l'usuari {uid}")
            return refugis_info
            
        except Exception as e:
            logger.error(f"Error obtenint informació de refugis de {list_name} per l'usuari {uid}: {str(e)}")
            return []
    
    def increment_renovated_refuges(self, uid: str) -> bool:
        """
        Incrementa el comptador de refugis renovats per un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si s'ha incrementat correctament
        """
        try:
            db = self.firestore_service.get_db()
            from google.cloud.firestore_v1.transforms import Increment
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi i obté les dades per tenir l'email
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot incrementar comptador, usuari no trobat amb UID: {uid}")
                return False
            
            # Incrementa el comptador
            doc_ref.update({'num_renovated_refuges': Increment(1)})
            
            # Invalida cache de l'usuari
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            
            logger.info(f"Comptador de refugis renovats incrementat per l'usuari {uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error incrementant comptador de refugis renovats per l'usuari {uid}: {str(e)}")
            return False
    
    def increment_uploaded_photos(self, uid: str) -> bool:
        """
        Incrementa el comptador de fotos pujades per un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si s'ha incrementat correctament
        """
        try:
            db = self.firestore_service.get_db()
            from google.cloud.firestore_v1.transforms import Increment
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot incrementar comptador, usuari no trobat amb UID: {uid}")
                return False
            
            # Incrementa el comptador
            doc_ref.update({'num_uploaded_photos': Increment(1)})
            
            # Invalida cache de l'usuari
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            
            logger.info(f"Comptador de fotos pujades incrementat per l'usuari {uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error incrementant comptador de fotos pujades per l'usuari {uid}: {str(e)}")
            return False
    
    def decrement_uploaded_photos(self, uid: str) -> bool:
        """
        Decrementa el comptador de fotos pujades per un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si s'ha decrementat correctament
        """
        try:
            db = self.firestore_service.get_db()
            from google.cloud.firestore_v1.transforms import Increment
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi i obté el valor actual
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot decrementar comptador, usuari no trobat amb UID: {uid}")
                return False
            
            # Obté el valor actual del comptador
            user_data = doc.to_dict()
            current_value = user_data.get('num_uploaded_photos', 0)
            
            # Només decrementa si el valor actual és major que 0
            if current_value > 0:
                # Decrementa el comptador (Increment amb valor negatiu)
                doc_ref.update({'num_uploaded_photos': Increment(-1)})
                
                # Invalida cache de l'usuari
                cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
                
                logger.info(f"Comptador de fotos pujades decrementat per l'usuari {uid} ({current_value} -> {current_value - 1})")
            else:
                logger.warning(f"No es pot decrementar comptador de fotos pujades per l'usuari {uid}, valor actual és {current_value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error decrementant comptador de fotos pujades per l'usuari {uid}: {str(e)}")
            return False
    
    def decrement_renovated_refuges(self, uid: str) -> bool:
        """
        Decrementa el comptador de refugis renovats per un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            bool: True si s'ha decrementat correctament
        """
        try:
            db = self.firestore_service.get_db()
            from google.cloud.firestore_v1.transforms import Increment
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi i obté el valor actual
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot decrementar comptador, usuari no trobat amb UID: {uid}")
                return False
            
            # Obté el valor actual del comptador
            user_data = doc.to_dict()
            current_value = user_data.get('num_renovated_refuges', 0)
            
            # Només decrementa si el valor actual és major que 0
            if current_value > 0:
                # Decrementa el comptador (increment amb valor negatiu)
                doc_ref.update({'num_renovated_refuges': Increment(-1)})
                
                # Invalida cache de l'usuari
                cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
                
                logger.info(f"Comptador de refugis renovats decrementat per l'usuari {uid} ({current_value} -> {current_value - 1})")
            else:
                logger.warning(f"No es pot decrementar comptador de refugis renovats per l'usuari {uid}, valor actual és {current_value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error decrementant comptador de refugis renovats per l'usuari {uid}: {str(e)}")
            return False
    
    def update_avatar_metadata(self, uid: str, media_metadata: Dict[str, str]) -> bool:
        """
        Actualitza les metadades de l'avatar d'un usuari
        
        Args:
            uid: UID de l'usuari
            media_metadata: Diccionari amb metadades de l'avatar (key, uploaded_at)
            
        Returns:
            bool: True si s'ha actualitzat correctament
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot actualitzar avatar, usuari no trobat amb UID: {uid}")
                return False
            
            # Actualitza les metadades de l'avatar
            doc_ref.update({
                'media_metadata': media_metadata,
            })
            
            # Invalida cache de l'usuari
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            
            logger.info(f"Avatar actualitzat per l'usuari {uid}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualitzant avatar per l'usuari {uid}: {str(e)}")
            return False
    
    def delete_avatar_metadata(self, uid: str) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Elimina les metadades de l'avatar d'un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            Tuple[bool, Optional[Dict]]: (True si s'ha eliminat correctament, metadades de l'avatar eliminat)
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(uid)
            
            # Comprova que l'usuari existeixi i obté les metadades actuals
            doc = doc_ref.get()
            if not doc.exists:
                logger.warning(f"No es pot eliminar avatar, usuari no trobat amb UID: {uid}")
                return False, None
            
            user_data = doc.to_dict()
            media_metadata = user_data.get('media_metadata')
            
            # Elimina les metadades de l'avatar
            doc_ref.update({
                'media_metadata': None,
            })
            
            # Invalida cache de l'usuari
            cache_service.delete(cache_service.generate_key('user_detail', uid=uid))
            
            logger.info(f"Avatar eliminat per l'usuari {uid}")
            return True, media_metadata
            
        except Exception as e:
            logger.error(f"Error eliminant avatar per l'usuari {uid}: {str(e)}")
            return False, None
