"""
DAO per a la gestió de refugis amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from firebase_admin import firestore
from google.cloud.firestore_v1.field_path import FieldPath
from google.cloud.firestore import DELETE_FIELD
from ..services import firestore_service, cache_service
from ..models.refugi_lliure import Refugi
from ..mappers.refugi_lliure_mapper import RefugiLliureMapper

logger = logging.getLogger(__name__)

class RefugiLliureDAO:
    """DAO per a la gestió de refugis"""
    
    def __init__(self):
        self.collection_name = 'data_refugis_lliures'
        self.coords_collection_name = 'coords_refugis'
        self.coords_document_name = 'all_refugis_coords'
        self.mapper = RefugiLliureMapper()
    
    def get_by_id(self, refugi_id: str) -> Optional[Refugi]:
        """Obtenir un refugi per ID amb cache"""
        # Genera clau de cache
        cache_key = cache_service.generate_key('refugi_detail', refugi_id=refugi_id)
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return self.mapper.firestore_to_model(cached_data)
        
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            refugi_data = doc.to_dict()
            
            # Guarda a cache
            timeout = cache_service.get_timeout('refugi_detail')
            cache_service.set(cache_key, refugi_data, timeout)
            
            return self.mapper.firestore_to_model(refugi_data)
            
        except Exception as e:
            logger.error(f'Error getting refugi by ID {refugi_id}: {str(e)}')
            raise
    
    
    
    
    

    
    def health_check(self) -> Dict[str, Any]:
        """Comprovar l'estat de la connexió amb Firestore"""
        try:
            db = firestore_service.get_db()
            collections = list(db.collections())
            
            return {
                'firebase': True,
                'firestore': True,
                'collections_count': len(collections)
            }
            
        except Exception as e:
            logger.error(f'Health check failed: {str(e)}')
            raise

    def refugi_exists(self, refugi_id: str) -> bool:
        """Comprovar si un refugi existeix per ID"""
        try:
            # Mirem primer a la cache
            cache_key = cache_service.generate_key('refugi_detail', refugi_id=refugi_id)
            cached_data = cache_service.get(cache_key)
            if cached_data is not None:
                return True  # Si està a cache, existeix
            
            # Si no està a la cache, consulta a Firestore
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            logger.log(23, f"Firestore READ (exists check): collection={self.collection_name} document={refugi_id}")
            doc = doc_ref.get()

            if not doc.exists:
                return False
            
            refugi_data = doc.to_dict()
            
            # Guarda a cache les dades del refugi existent
            timeout = cache_service.get_timeout('refugi_detail')
            cache_service.set(cache_key, refugi_data, timeout)
            return True
        except Exception as e:
            logger.error(f'Error checking if refugi exists by ID {refugi_id}: {str(e)}')
            raise
    
    def add_visitor_to_refugi(self, refugi_id: str, uid: str) -> bool:
        """
        Afegeix un visitant a la llista de visitants d'un refugi
        
        Args:
            refugi_id: ID del refugi
            uid: UID de l'usuari visitant
            
        Returns:
            bool: True si s'ha afegit correctament
        """
        try:
            # Obté el refugi actual
            refugi = self.get_by_id(refugi_id)
            if not refugi:
                logger.warning(f"No es pot afegir visitant, refugi no trobat amb ID: {refugi_id}")
                return False
            
            # Obté la llista actual de visitants
            current_visitors = refugi.visitors if refugi.visitors else []
            
            # Comprova si ja està a la llista
            if uid in current_visitors:
                logger.info(f"Usuari {uid} ja està a la llista de visitants del refugi {refugi_id}")
                return True
            
            # Afegeix l'usuari a la llista
            current_visitors.append(uid)
            
            # Actualitza a Firestore
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc_ref.update({'visitors': current_visitors})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Usuari {uid} afegit a la llista de visitants del refugi {refugi_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error afegint visitant {uid} al refugi {refugi_id}: {str(e)}")
            return False
    
    def remove_visitor_from_refugi(self, refugi_id: str, uid: str) -> bool:
        """
        Elimina un visitant de la llista de visitants d'un refugi
        
        Args:
            refugi_id: ID del refugi
            uid: UID de l'usuari visitant
            
        Returns:
            bool: True si s'ha eliminat correctament
        """
        try:
            # Obté el refugi actual
            refugi = self.get_by_id(refugi_id)
            if not refugi:
                logger.warning(f"No es pot eliminar visitant, refugi no trobat amb ID: {refugi_id}")
                return False
            
            # Obté la llista actual de visitants
            current_visitors = refugi.visitors if refugi.visitors else []
            
            # Comprova si l'usuari està a la llista
            if uid not in current_visitors:
                logger.info(f"Usuari {uid} no està a la llista de visitants del refugi {refugi_id}")
                return True
            
            # Elimina l'usuari de la llista
            current_visitors.remove(uid)
            
            # Actualitza a Firestore
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc_ref.update({'visitors': current_visitors})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Usuari {uid} eliminat de la llista de visitants del refugi {refugi_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error eliminant visitant {uid} del refugi {refugi_id}: {str(e)}")
            return False
    
    @staticmethod
    def _media_field(media_key: str, *subfields: str) -> str:
        """Ruta de camp escapada per a una entrada del map media_metadata (les claus R2 contenen '/', '.' i '-')"""
        return FieldPath('media_metadata', media_key, *subfields).to_api_repr()

    def get_raw_media_metadata(self, refugi_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Retorna el map media_metadata tal com està desat (sense URLs), cache-first.
        None si el refugi no existeix.
        """
        cache_key = cache_service.generate_key('refugi_detail', refugi_id=refugi_id)
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return cached_data.get('media_metadata') or {}
        db = firestore_service.get_db()
        doc_ref = db.collection(self.collection_name).document(str(refugi_id))
        logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id} (raw media_metadata)")
        doc = doc_ref.get()
        if not doc.exists:
            return None
        refugi_data = doc.to_dict()
        cache_service.set(cache_key, refugi_data, cache_service.get_timeout('refugi_detail'))
        return refugi_data.get('media_metadata') or {}

    def get_media_entry(self, refugi_id: str, media_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Retorna (refugi_existeix, entrada desada del mitjà o None).
        Llegeix directament de Firestore (sense cache) per decisions de permisos/moderació.
        """
        db = firestore_service.get_db()
        doc_ref = db.collection(self.collection_name).document(str(refugi_id))
        logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id} (media entry)")
        doc = doc_ref.get()
        if not doc.exists:
            return False, None
        media_metadata = (doc.to_dict() or {}).get('media_metadata') or {}
        entry = media_metadata.get(media_key)
        return True, (dict(entry) if entry is not None else None)

    
    def add_media_metadata(self, refugi_id: str, media_metadata_dict: Dict[str, Dict[str, Any]]) -> bool:
        """
        Afegeix nous media_metadata a un refugi de forma ATÒMICA: cada entrada s'escriu
        amb la seva ruta de camp (FieldPath) i no es reescriu el map sencer.
        
        Args:
            refugi_id: ID del refugi
            media_metadata_dict: Diccionari de media_metadata a afegir (clau: key, valor: metadata)
            
        Returns:
            bool: True si s'ha afegit correctament
        """
        try:
            if not media_metadata_dict:
                return True
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"No es pot afegir media_metadata, refugi no trobat amb ID: {refugi_id}")
                return False
            
            updates = {self._media_field(key): value for key, value in media_metadata_dict.items()}
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refugi_id} (add {len(updates)} media)")
            doc_ref.update(updates)
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Afegits {len(media_metadata_dict)} media_metadata al refugi {refugi_id}")
            return True
            
        except Exception as e:
            logger.error(f'Error afegint media_metadata al refugi {refugi_id}: {str(e)}')
            return False
    
    def update_media_status(self, refugi_id: str, media_key: str, new_status: str,
                            only_if_status: Optional[List[str]] = None) -> bool:
        """
        Canvia el status d'un mitjà (visible | hidden_pending_review | removed) atòmicament.

        Args:
            only_if_status: si s'indica, només es canvia si l'estat actual és un d'aquests

        Returns:
            True si s'ha canviat, False si el refugi/mitjà no existeix o no calia canviar-lo
        """
        try:
            exists, entry = self.get_media_entry(refugi_id, media_key)
            if not exists or entry is None:
                return False
            current = entry.get('status') or 'visible'
            if only_if_status is not None and current not in only_if_status:
                return False
            if current == new_status:
                return False
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refugi_id} (media status -> {new_status})")
            doc_ref.update({self._media_field(media_key, 'status'): new_status})
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            return True
        except Exception as e:
            logger.error(f'Error actualitzant status del mitjà {media_key} del refugi {refugi_id}: {str(e)}')
            return False

    def delete_media_metadata(self, refugi_id: str, media_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Elimina un media_metadata específic d'un refugi (DELETE_FIELD atòmic)
        
        Args:
            refugi_id: ID del refugi
            media_key: Key del mitjà a eliminar
            
        Returns:
            bool: True si s'ha eliminat correctament
            Optional[Dict[str, Any]]: Metadada del mitjà eliminat o None si no s'ha trobat
        """
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"No es pot eliminar media_metadata, refugi no trobat amb ID: {refugi_id}")
                return False, None
            
            # Obtenir media_metadata actuals (només per tenir còpia per al rollback)
            current_metadata = doc.to_dict().get('media_metadata', {}) or {}
            
            # Verificar si el mitjà existeix
            if media_key not in current_metadata:
                return False, None  # No s'ha trobat el mitjà a eliminar
            
            # Guardar metadada eliminada
            metadata_backup = current_metadata[media_key]
            
            # Eliminar només aquesta entrada
            doc_ref.update({self._media_field(media_key): DELETE_FIELD})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Eliminat media_metadata {media_key} del refugi {refugi_id}")
            return True, metadata_backup 
            
        except Exception as e:
            logger.error(f'Error eliminant media_metadata del refugi {refugi_id}: {str(e)}')
            return False, None
    
    def delete_multiple_media_metadata(self, refugi_id: str, media_keys: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Elimina múltiples media_metadata d'un refugi (bulk delete atòmic amb DELETE_FIELD)
        
        Args:
            refugi_id: ID del refugi
            media_keys: Llista de keys dels mitjans a eliminar
            
        Returns:
            bool: True si s'han eliminat correctament
            List[Dict[str, Any]]: Llista de metadades eliminades amb 'key' i les dades de metadata
        """
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"No es pot eliminar media_metadata, refugi no trobat amb ID: {refugi_id}")
                return False, []
            
            # Obtenir media_metadata actuals
            current_metadata = doc.to_dict().get('media_metadata', {}) or {}
            
            # Guardar metadades eliminades
            metadata_backup = []
            keys_not_found = []
            updates = {}
            
            for media_key in media_keys:
                if media_key in current_metadata:
                    # Guardar metadada amb la key
                    backup_entry = dict(current_metadata[media_key] or {})
                    backup_entry['key'] = media_key
                    metadata_backup.append(backup_entry)
                    updates[self._media_field(media_key)] = DELETE_FIELD
                else:
                    keys_not_found.append(media_key)
            
            # Si no s'ha trobat cap key, retornar error
            if len(metadata_backup) == 0:
                logger.warning(f"No s'ha trobat cap media_key per eliminar del refugi {refugi_id}")
                return False, []
            
            # Actualitzar document amb bulk update
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refugi_id} (bulk delete {len(metadata_backup)} media)")
            doc_ref.update(updates)
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            if keys_not_found:
                logger.warning(f"Algunes keys no s'han trobat al refugi {refugi_id}: {keys_not_found}")
            
            logger.log(23, f"Eliminats {len(metadata_backup)} media_metadata del refugi {refugi_id}")
            return True, metadata_backup
            
        except Exception as e:
            logger.error(f'Error eliminant múltiples media_metadata del refugi {refugi_id}: {str(e)}')
            return False, []
    
    def update_refugi_visitors(self, refugi_id: str, visitors: List[str]) -> bool:
        """
        Actualitza la llista de visitors d'un refugi
        
        Args:
            refugi_id: ID del refugi
            visitors: Llista d'UIDs de visitants
            
        Returns:
            bool: True si s'ha actualitzat correctament
        """
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            
            logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id}")
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"No es pot actualitzar visitors, refugi no trobat amb ID: {refugi_id}")
                return False
            
            # Actualitza la llista de visitors
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refugi_id}")
            doc_ref.update({'visitors': visitors})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.info(f"Actualitzada llista de visitors del refugi {refugi_id}")
            return True
            
        except Exception as e:
            logger.error(f'Error actualitzant visitors del refugi {refugi_id}: {str(e)}')
            return False
    
    def remove_visitor_from_all_refuges(self, uid: str, visited_refuges: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Elimina un usuari de la llista de visitors de tots els refugis que ha visitat
        
        Args:
            uid: UID de l'usuari
            visited_refuges: Llista d'IDs dels refugis visitats per l'usuari
            
        Returns:
            Tuple (èxit: bool, missatge d'error: Optional[str])
        """
        try:
            if not visited_refuges:
                logger.info(f"Usuari {uid} no té refugis visitats")
                return True, None
            
            db = firestore_service.get_db()
            removed_count = 0
            
            for refuge_id in visited_refuges:
                try:
                    doc_ref = db.collection(self.collection_name).document(str(refuge_id))
                    logger.log(23, f"Firestore READ: collection={self.collection_name} document={refuge_id}")
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        # Eliminar uid de visitors
                        from google.cloud.firestore import ArrayRemove
                        logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refuge_id} (remove visitor)")
                        doc_ref.update({'visitors': ArrayRemove([uid])})
                        removed_count += 1
                        
                        # Invalida cache del refugi
                        cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refuge_id))
                    else:
                        logger.warning(f"Refugi {refuge_id} no trobat al eliminar visitor {uid}")
                except Exception as e:
                    logger.error(f"Error eliminant visitor {uid} del refugi {refuge_id}: {str(e)}")
                    # Continua amb els altres refugis
            
            logger.info(f"Usuari {uid} eliminat de {removed_count} refugis")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant visitor {uid} de refugis: {str(e)}")
            return False, str(e)
