"""
DAO per a la gestió de refugis amb Firestore
"""
import logging
from typing import List, Optional, Dict, Any
from ..services import firestore_service
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters

logger = logging.getLogger(__name__)

class RefugiLliureDao:
    """DAO per a la gestió de refugis"""
    
    def __init__(self):
        self.collection_name = 'data_refugis_lliures'
        self.coords_collection_name = 'coords_refugis'
        self.coords_document_name = 'all_refugis_coords'
    
    def get_by_id(self, refugi_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir un refugi per ID"""
        try:
            db = firestore_service.get_db()
            doc_ref = db.collection(self.collection_name).document(str(refugi_id))
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            refugi_data = doc.to_dict()
            #refugi_data['id'] = doc.id
            return refugi_data
            
        except Exception as e:
            logger.error(f'Error getting refugi by ID {refugi_id}: {str(e)}')
            raise
    
    def search_refugis(self, filters: RefugiSearchFilters) -> List[Dict[str, Any]]:
        """Cercar refugis amb filtres"""
        try:
            db = firestore_service.get_db()
            
            # Check if any filters are applied (except limit)
            has_filters = self._has_active_filters(filters)
            
            if not has_filters:
                # No filters applied - use coordinate collection for efficiency
                return self._get_coordinates_as_refugi_list()
            else:
                # Filters applied - need full data from main collection
                refugis_ref = db.collection(self.collection_name)
                
                # Obtenir tots els documents (Firestore no permet filtres complexos en una sola query)
                docs = refugis_ref.stream()
                
                refugis = []
                for doc in docs:
                    refugi_data = doc.to_dict()
                    
                    # Apply all filters
                    if self._matches_filters(refugi_data, filters):
                        refugis.append(refugi_data)
                
                return refugis
            
        except Exception as e:
            logger.error(f'Error searching refugis: {str(e)}')
            raise
    
    def _matches_filters(self, refugi_data: Dict[str, Any], filters: RefugiSearchFilters) -> bool:
        """Check if a refugi matches all the provided filters"""
        
        # Exact name match
        if filters.name:
            if refugi_data.get('name', '').lower() != filters.name.lower():
                return False
        
        # Location filters
        if filters.region and refugi_data.get('region') != filters.region:
            return False
        if filters.departement and refugi_data.get('departement') != filters.departement:
            return False
        
        # Type filter
        if filters.type and refugi_data.get('type') != filters.type:
            return False
        
        # Numeric range filters - if field is null, refugi fails the filter
        places = refugi_data.get('places')
        if filters.places_min is not None or filters.places_max is not None:
            if places is None:
                return False  # Refugi with null places fails filter
            if filters.places_min is not None and places < filters.places_min:
                return False
            if filters.places_max is not None and places > filters.places_max:
                return False
        
        altitude = refugi_data.get('altitude')
        if filters.altitude_min is not None or filters.altitude_max is not None:
            if altitude is None:
                return False  # Refugi with null altitude fails filter
            if filters.altitude_min is not None and altitude < filters.altitude_min:
                return False
            if filters.altitude_max is not None and altitude > filters.altitude_max:
                return False
        
        # Info complementaria filters (only check if filter value is 1)
        info_comp = refugi_data.get('info_comp', {})
        
        filter_checks = [
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
        
        for field_name, filter_value in filter_checks:
            if filter_value == 1:  # Only check when specifically requesting this feature
                if info_comp.get(field_name, 0) != 1:
                    return False
        
        return True
    
    def _has_active_filters(self, filters: RefugiSearchFilters) -> bool:
        """Check if any filters are active (excluding limit)"""
        return bool(
            filters.query_text or
            filters.name or
            filters.region or
            filters.departement or
            filters.type or
            filters.places_min is not None or
            filters.places_max is not None or
            filters.altitude_min is not None or
            filters.altitude_max is not None or
            filters.cheminee is not None or
            filters.poele is not None or
            filters.couvertures is not None or
            filters.latrines is not None or
            filters.bois is not None or
            filters.eau is not None or
            filters.matelas is not None or
            filters.couchage is not None or
            filters.lits is not None
        )
    
    def _get_coordinates_as_refugi_list(self) -> List[Dict[str, Any]]:
        """Get refugi data from coordinates collection when no filters are applied"""
        try:
            db = firestore_service.get_db()
            
            # Get coordinates document
            doc_ref = db.collection(self.coords_collection_name).document(self.coords_document_name)
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
                    'id': coord_data.get('refugi_id', ''),
                    'name': coord_data.get('refugi_name', ''),
                    'coord': {
                        'long': coord_data.get('coordinates', {}).get('longitude', 0.0),
                        'lat': coord_data.get('coordinates', {}).get('latitude', 0.0)
                    },
                    'geohash': coord_data.get('geohash', None)
                }
                refugis.append(refugi_data)
            
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