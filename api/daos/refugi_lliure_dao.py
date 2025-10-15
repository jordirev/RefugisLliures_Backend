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
            refugis_ref = db.collection(self.collection_name)
            
            # Obtenir documents
            docs = refugis_ref.limit(filters.limit).stream()
            
            refugis = []
            for doc in docs:
                refugi_data = doc.to_dict()
                refugi_data['id'] = doc.id
                
                # Si hi ha text de cerca, filtrar pels noms
                if filters.query_text:
                    nom = refugi_data.get('name', '').lower()
                    if filters.query_text.lower() in nom:
                        refugis.append(refugi_data)
                else:
                    refugis.append(refugi_data)
            
            return refugis
            
        except Exception as e:
            logger.error(f'Error searching refugis: {str(e)}')
            raise
    
    def get_all_coordinates(self, limit: int = 1000) -> Optional[Dict[str, Any]]:
        """Obtenir totes les coordenades dels refugis"""
        try:
            db = firestore_service.get_db()
            
            if limit > 1000:
                limit = 1000
            
            # Obtenir el document únic amb totes les coordenades
            doc_ref = db.collection(self.coords_collection_name).document(self.coords_document_name)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            all_coordinates = data.get('refugis_coordinates', [])
            
            # Aplicar límit si és necessari
            coordinates = all_coordinates[:limit]
            
            return {
                'coordinates': coordinates,
                'total_available': len(all_coordinates)
            }
            
        except Exception as e:
            logger.error(f'Error getting refugi coordinates: {str(e)}')
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