"""
DAO per a la gestió de refugis amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from firebase_admin import firestore
from ..services import firestore_service, cache_service, r2_media_service
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters
from ..mappers.refugi_lliure_mapper import RefugiLliureMapper
from .search_strategies import SearchStrategySelector

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
    
    def search_refugis(self, filters: RefugiSearchFilters) -> Dict[str, Any]:
        """Cercar refugis amb filtres optimitzats per índexs composats i cache amb estratègia ID caching
        
        Returns:
            Dict amb 'results' (List[Refugi] o List[Dict] segons filtres) i 'has_filters' (bool)
        """
        # Check if any filters are applied (except limit)
        has_filters = self._has_active_filters(filters)
        
        if not has_filters:
            # No filters applied - use coordinate collection for efficiency (sense ID caching)
            results = self._get_coordinates_as_refugi_list()
            return {'results': results, 'has_filters': False}
        
        # Filters applied - usar estratègia ID caching
        cache_key = cache_service.generate_key('refugi_search', **filters.to_dict())
        
        try:
            # Funció per obtenir TOTES les dades completes d'una des de Firestore
            def fetch_all():
                db = firestore_service.get_db()
                return self._build_optimized_query(db, filters)
            
            # Funció per obtenir un refugi individual per ID
            def fetch_single(refugi_id: str):
                db = firestore_service.get_db()
                doc_ref = db.collection(self.collection_name).document(str(refugi_id))
                logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id}")
                doc = doc_ref.get()
                return doc.to_dict() if doc.exists else None
            
            # Funció per extreure l'ID d'un refugi
            def get_id(refugi_data: Dict[str, Any]) -> str:
                return refugi_data['id']
            
            # Usar estratègia ID caching del cache_service
            results_data = cache_service.get_or_fetch_list(
                list_cache_key=cache_key,
                detail_key_prefix='refugi_detail',
                fetch_all_fn=fetch_all,
                fetch_single_fn=fetch_single,
                get_id_fn=get_id,
                list_timeout=cache_service.get_timeout('refugi_search'),
                detail_timeout=cache_service.get_timeout('refugi_detail')
            )
            
            # Convertir a models
            results = self.mapper.firestore_list_to_models(results_data)
            
            return {'results': results, 'has_filters': True}
            
        except Exception as e:
            logger.error(f'Error searching refugis: {str(e)}')
            raise
    
    def _get_coordinates_as_refugi_list(self) -> List[Dict[str, Any]]:
        """Get refugi data from coordinates collection when no filters are applied amb cache"""
        # Clau de cache per coordenades
        cache_key = cache_service.generate_key('refugi_coords', document='all')
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            db = firestore_service.get_db()
            
            # Get coordinates document
            doc_ref = db.collection(self.coords_collection_name).document(self.coords_document_name)
            logger.log(23, f"Firestore READ: collection={self.coords_collection_name} document={self.coords_document_name} (coordinates) ")
            doc = doc_ref.get()
            
            if not doc.exists:
                return []
            
            data = doc.to_dict()
            all_coordinates = data.get('refugis_coordinates', [])
            
            # Convert coordinates format to refugi format (all coordinates)
            refugis = []
            for coord_data in all_coordinates:
                # Convert coordinate data to refugi format
                refugi_data = {
                    'id': coord_data.get('id', ''),
                    'name': coord_data.get('name', ''),
                    'coord': coord_data.get('coord', {}),
                    'geohash': coord_data.get('geohash', None)
                }
                
                # Add surname if available
                if 'surname' in coord_data and coord_data['surname']:
                    refugi_data['surname'] = coord_data['surname']
                    
                refugis.append(refugi_data)
            
            # Guarda a cache (timeout llarg per coordenades)
            timeout = cache_service.get_timeout('refugi_coords')
            cache_service.set(cache_key, refugis, timeout)
            
            return refugis
            
        except Exception as e:
            logger.error(f'Error getting coordinates as refugi list: {str(e)}')
            # Fallback to empty list if coordinates collection fails
            return []
    
    def _has_active_filters(self, filters: RefugiSearchFilters) -> bool:
        """Comprova si hi ha filtres actius (exclou limit)"""
        # Cerca per name sempre és un filtre actiu
        if filters.name and filters.name.strip():
            return True
        
        # Comprova altres filtres - només compte si té valors no buits
        has_type = bool(filters.type and len(filters.type) > 0 and any(t.strip() for t in filters.type if isinstance(t, str)))
        has_condition = bool(filters.condition and len(filters.condition) > 0)
        has_places = filters.places_min is not None or filters.places_max is not None
        has_altitude = filters.altitude_min is not None or filters.altitude_max is not None
        
        return has_type or has_condition or has_places or has_altitude
    
    def _build_optimized_query(self, db, filters: RefugiSearchFilters) -> List[Dict[str, Any]]:
        """
        Construeix i executa una query optimitzada segons els filtres utilitzant el patró Strategy
        
        Args:
            db: Client de Firestore
            filters: Filtres de cerca
            
        Returns:
            Llista de dades de refugis
        """
        # Cas especial: cerca per name (només retorna un refugi)
        if filters.name and filters.name.strip():
            return self._search_by_name(db, filters.name.strip())
        
        # Selecciona l'estratègia òptima segons els filtres
        strategy = SearchStrategySelector.select_strategy(filters)
        logger.info(f"Using search strategy: {strategy.get_strategy_name()}")
        
        # Executa la query amb l'estratègia seleccionada
        results = strategy.execute_query(db, self.collection_name, filters)
        
        return results
    
    def _search_by_name(self, db, name: str) -> List[Dict[str, Any]]:
        """
        Cerca un refugi pel seu nom exacte
        
        Args:
            db: Client de Firestore
            name: Nom del refugi a cercar
            
        Returns:
            Llista amb un sol refugi si es troba, llista buida si no
        """
        try:
            query = db.collection(self.collection_name).where(filter=firestore.FieldFilter('name', '==', name))
            logger.log(23, f"Firestore QUERY: collection={self.collection_name} filters=name")
            docs = query.stream()
            results = [doc.to_dict() for doc in docs]
            
            # Només hauria de retornar un refugi ja que el name és únic
            return results
            
        except Exception as e:
            logger.error(f'Error searching refugi by name {name}: {str(e)}')
            return []

    
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
    
    def get_media_metadata(self, refugi_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Obté el mapa de media_metadata d'un refugi
        
        Args:
            refugi_id: ID del refugi
            
        Returns:
            Diccionari de media_metadata (clau: key, valor: metadata) o None si el refugi no existeix
        """
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            logger.log(23, f"Firestore READ: collection={self.collection_name} document={refugi_id} (media_metadata)")
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()

            # Generem les metadades amb URLs prefirmades
            media_service = r2_media_service.get_refugi_media_service()
            media_metadata = data.get('media_metadata', {})             
            media_metadata_objects = media_service.generate_media_metadata_list(media_metadata)
            
            # Convertir objectes MediaMetadata a diccionaris
            return [obj.to_dict() for obj in media_metadata_objects]
            
        except Exception as e:
            logger.error(f'Error obtenint media_metadata del refugi {refugi_id}: {str(e)}')
            raise
    
    def add_media_metadata(self, refugi_id: str, media_metadata_dict: Dict[str, Dict[str, Any]]) -> bool:
        """
        Afegeix nous media_metadata a un refugi
        
        Args:
            refugi_id: ID del refugi
            media_metadata_dict: Diccionari de media_metadata a afegir (clau: key, valor: metadata)
            
        Returns:
            bool: True si s'ha afegit correctament
        """
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"No es pot afegir media_metadata, refugi no trobat amb ID: {refugi_id}")
                return False
            
            # Obtenir media_metadata actuals i afegir les noves
            current_metadata = doc.to_dict().get('media_metadata', {})
            current_metadata.update(media_metadata_dict)
            
            # Actualitzar document
            doc_ref.update({'media_metadata': current_metadata})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Afegits {len(media_metadata_dict)} media_metadata al refugi {refugi_id}")
            return True
            
        except Exception as e:
            logger.error(f'Error afegint media_metadata al refugi {refugi_id}: {str(e)}')
            return False
    
    def delete_media_metadata(self, refugi_id: str, media_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Elimina un media_metadata específic d'un refugi
        
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
            
            # Obtenir media_metadata actuals
            current_metadata = doc.to_dict().get('media_metadata', {})
            
            # Verificar si el mitjà existeix
            if media_key not in current_metadata:
                return False, None  # No s'ha trobat el mitjà a eliminar
            
            # Guardar metadada eliminada
            metadata_backup = current_metadata[media_key]
            
            # Eliminar el mitjà del diccionari
            del current_metadata[media_key]
            
            # Actualitzar document
            doc_ref.update({'media_metadata': current_metadata})
            
            # Invalida cache del refugi
            cache_service.delete(cache_service.generate_key('refugi_detail', refugi_id=refugi_id))
            
            logger.log(23, f"Eliminat media_metadata {media_key} del refugi {refugi_id}")
            return True, metadata_backup 
            
        except Exception as e:
            logger.error(f'Error eliminant media_metadata del refugi {refugi_id}: {str(e)}')
            return False, None
    
    def delete_multiple_media_metadata(self, refugi_id: str, media_keys: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Elimina múltiples media_metadata d'un refugi (bulk delete)
        
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
            current_metadata = doc.to_dict().get('media_metadata', {})
            
            # Guardar metadades eliminades i eliminar-les del diccionari
            metadata_backup = []
            keys_not_found = []
            
            for media_key in media_keys:
                if media_key in current_metadata:
                    # Guardar metadada amb la key
                    backup_entry = current_metadata[media_key].copy()
                    backup_entry['key'] = media_key
                    metadata_backup.append(backup_entry)
                    
                    # Eliminar del diccionari
                    del current_metadata[media_key]
                else:
                    keys_not_found.append(media_key)
            
            # Si no s'ha trobat cap key, retornar error
            if len(metadata_backup) == 0:
                logger.warning(f"No s'ha trobat cap media_key per eliminar del refugi {refugi_id}")
                return False, []
            
            # Actualitzar document amb bulk update
            logger.log(23, f"Firestore UPDATE: collection={self.collection_name} document={refugi_id} (bulk delete {len(metadata_backup)} media)")
            doc_ref.update({'media_metadata': current_metadata})
            
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
