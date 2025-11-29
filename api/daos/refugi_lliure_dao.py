"""
DAO per a la gestió de refugis amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any
from ..services import firestore_service, cache_service
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters
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
    
    def search_refugis(self, filters: RefugiSearchFilters) -> Dict[str, Any]:
        """Cercar refugis amb filtres optimitzats per índexs composats i cache
        
        Returns:
            Dict amb 'results' (List[Refugi] o List[Dict] segons filtres) i 'has_filters' (bool)
        """
        # Genera clau de cache basada en filtres
        cache_key = cache_service.generate_key(
            'refugi_search',
            **filters.to_dict()
        )
        
        # Intenta obtenir de cache
        cached_data = cache_service.get(cache_key)
        if cached_data is not None:
            # Convertir a models si té filtres
            if cached_data['has_filters']:
                return {
                    'results': self.mapper.firestore_list_to_models(cached_data['results']),
                    'has_filters': True
                }
            return cached_data
        
        try:
            db = firestore_service.get_db()
            
            # Check if any filters are applied (except limit)
            has_filters = self._has_active_filters(filters)
            
            if not has_filters:
                # No filters applied - use coordinate collection for efficiency
                results = self._get_coordinates_as_refugi_list()
                data = {'results': results, 'has_filters': False}
            else:
                # Filters applied - build optimized query
                results_data = self._build_optimized_query(db, filters)
                data = {'results': results_data, 'has_filters': True}
            
            # Guarda a cache (raw data)
            timeout = cache_service.get_timeout('refugi_search')
            cache_service.set(cache_key, data, timeout)
            
            # Retornar amb models si té filtres
            if data['has_filters']:
                return {
                    'results': self.mapper.firestore_list_to_models(data['results']),
                    'has_filters': True
                }
            return data
            
        except Exception as e:
            logger.error(f'Error searching refugis: {str(e)}')
            raise

    def _build_optimized_query(self, db, filters: RefugiSearchFilters) -> List[Dict[str, Any]]:
        """Build query optimized for composite indexes"""
        
        # Exact name match - most specific, use direct query
        if filters.name:
            return self._query_by_name(db, filters.name)
        
        # Try composite index patterns (order matters for Firestore)
        refugis_ref = db.collection(self.collection_name)
        
        # Pattern 1: (departement, region, type, places) - most specific composite
        if all([filters.departement, filters.region, filters.type, 
               filters.places_min is not None or filters.places_max is not None]):
            query = refugis_ref.where('departement', '==', filters.departement) \
                              .where('region', '==', filters.region) \
                              .where('type', '==', filters.type)
            
            # Both min and max can be applied to the same field
            if filters.places_min is not None:
                query = query.where('places', '>=', filters.places_min)
            if filters.places_max is not None:
                query = query.where('places', '<=', filters.places_max)
            
            return self._execute_query_with_memory_filters(query, filters)
        
        # Pattern 2: (departement, region, places)
        elif all([filters.departement, filters.region, 
                 filters.places_min is not None or filters.places_max is not None]):
            query = refugis_ref.where('departement', '==', filters.departement) \
                              .where('region', '==', filters.region)
            
            # Both min and max can be applied to the same field
            if filters.places_min is not None:
                query = query.where('places', '>=', filters.places_min)
            if filters.places_max is not None:
                query = query.where('places', '<=', filters.places_max)
            
            return self._execute_query_with_memory_filters(query, filters)
        
        # Pattern 3: (departement, region, altitude)
        elif all([filters.departement, filters.region,
                 filters.altitude_min is not None or filters.altitude_max is not None]):
            query = refugis_ref.where('departement', '==', filters.departement) \
                              .where('region', '==', filters.region)
            
            # Both min and max can be applied to the same field
            if filters.altitude_min is not None:
                query = query.where('altitude', '>=', filters.altitude_min)
            if filters.altitude_max is not None:
                query = query.where('altitude', '<=', filters.altitude_max)
            
            return self._execute_query_with_memory_filters(query, filters)
        
        # Pattern 4: (departement, region) - basic location composite
        elif filters.departement and filters.region:
            query = refugis_ref.where('departement', '==', filters.departement) \
                              .where('region', '==', filters.region)
            
            return self._execute_query_with_memory_filters(query, filters)
        
        # Pattern 5: Single field queries with chained where clauses
        else:
            return self._build_chained_where_query(refugis_ref, filters)

    def _query_by_name(self, db, name: str) -> List[Dict[str, Any]]:
        """Direct query by name - exact match"""
        refugis_ref = db.collection(self.collection_name)
        logger.log(23, f"Firestore QUERY: collection={self.collection_name} filter=name=={name}")
        docs = refugis_ref.where('name', '==', name).stream()
        
        results = []
        for doc in docs:
            refugi_data = doc.to_dict()
            refugi_data['id'] = doc.id
            results.append(refugi_data)
        
        return results

    def _build_chained_where_query(self, refugis_ref, filters: RefugiSearchFilters) -> List[Dict[str, Any]]:
        """Build query using chained where clauses for non-composite scenarios"""
        query = refugis_ref
        
        # Apply single-field equality filters first (most selective)
        if filters.departement:
            query = query.where('departement', '==', filters.departement)
        
        if filters.region:
            query = query.where('region', '==', filters.region)
        
        if filters.type:
            query = query.where('type', '==', filters.type)
        
        # Prioritize places range over altitude if both present (can't have ranges on different fields)
        if filters.places_min is not None or filters.places_max is not None:
            if filters.places_min is not None:
                query = query.where('places', '>=', filters.places_min)
            if filters.places_max is not None:
                query = query.where('places', '<=', filters.places_max)
        
        elif filters.altitude_min is not None or filters.altitude_max is not None:
            if filters.altitude_min is not None:
                query = query.where('altitude', '>=', filters.altitude_min)
            if filters.altitude_max is not None:
                query = query.where('altitude', '<=', filters.altitude_max)
        
        return self._execute_query_with_memory_filters(query, filters)

    def _execute_query_with_memory_filters(self, query, filters: RefugiSearchFilters) -> List[Dict[str, Any]]:
        """Execute Firestore query and apply remaining filters in memory"""
        logger.log(23, f"Firestore QUERY (stream) executed for refugis with post-filters applied in memory")
        docs = query.stream()
        
        results = []
        for doc in docs:
            refugi_data = doc.to_dict()
            refugi_data['id'] = doc.id
            
            # Apply filters that couldn't be handled by Firestore query
            if self._matches_memory_filters(refugi_data, filters):
                results.append(refugi_data)
        
        return results

    def _matches_memory_filters(self, refugi_data: Dict[str, Any], filters: RefugiSearchFilters) -> bool:
        """Apply filters in memory that weren't handled by the Firestore query"""
        
        # Check numeric ranges that might not have been applied in query
        places = refugi_data.get('places')
        if filters.places_min is not None or filters.places_max is not None:
            if places is None:
                return False
            if filters.places_min is not None and places < filters.places_min:
                return False
            if filters.places_max is not None and places > filters.places_max:
                return False
        
        altitude = refugi_data.get('altitude')
        if filters.altitude_min is not None or filters.altitude_max is not None:
            if altitude is None:
                return False
            if filters.altitude_min is not None and altitude < filters.altitude_min:
                return False
            if filters.altitude_max is not None and altitude > filters.altitude_max:
                return False
        
        # Check info_comp filters (amenities)
        info_comp = refugi_data.get('info_comp', {})
        
        amenity_filters = [
            ('cheminee', filters.cheminee),
            ('poele', filters.poele),
            ('couvertures', filters.couvertures),
            ('latrines', filters.latrines),
            ('bois', filters.bois),
            ('eau', filters.eau),
            ('matelas', filters.matelas),
            ('couchage', filters.couchage),
            ('lits', filters.lits)
        ]
        
        for field_name, filter_value in amenity_filters:
            if filter_value == 1:  # Only check when specifically requesting this feature
                if info_comp.get(field_name, 0) != 1:
                    return False
        
        return True
    
    def _has_active_filters(self, filters: RefugiSearchFilters) -> bool:
        """Check if any filters are active"""
        return bool(
            filters.name or
            filters.region or
            filters.departement or
            filters.type or
            filters.places_min is not None or
            filters.places_max is not None or
            filters.altitude_min is not None or
            filters.altitude_max is not None or
            filters.cheminee == 1 or
            filters.poele == 1 or
            filters.couvertures == 1 or
            filters.latrines == 1 or
            filters.bois == 1 or
            filters.eau == 1 or
            filters.matelas == 1 or
            filters.couchage == 1 or
            filters.lits == 1
        )
    
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
