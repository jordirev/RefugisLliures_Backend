"""
Controller per a la gestió de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from ..daos.refugi_lliure_dao import RefugiLliureDao
from ..mappers.refugi_lliure_mapper import RefugiLliureMapper
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDao()
        self.refugi_mapper = RefugiLliureMapper()
    
    def get_refugi_by_id(self, refugi_id: str) -> Tuple[Optional[Refugi], Optional[str]]:
        """
        Obtenir un refugi per ID
        Returns: (Refugi o None, missatge d'error o None)
        """
        try:
            refugi_data = self.refugi_dao.get_by_id(refugi_id)
            
            if not refugi_data:
                return None, "Refugi not found"
            
            refugi = self.refugi_mapper.firestore_to_model(refugi_data)
            return refugi, None
            
        except Exception as e:
            logger.error(f'Error in get_refugi_by_id: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def search_refugis(self, query_params: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Cercar refugis amb filtres
        Returns: (Dades de resposta o None, missatge d'error o None)
        """
        try:
            # Crear filtres de cerca
            query_text = query_params.get('q', '').strip()
            limit = query_params.get('limit', 10)
            
            try:
                limit = int(limit)
                if limit > 100:
                    limit = 100
            except ValueError:
                limit = 10
            
            filters = RefugiSearchFilters(
                query_text=query_text,
                limit=limit
            )
            
            # Obtenir dades del DAO
            refugis_data = self.refugi_dao.search_refugis(filters)
            
            # Convertir a models
            refugis = self.refugi_mapper.firestore_list_to_models(refugis_data)
            
            # Formatar resposta
            response = self.refugi_mapper.format_search_response(
                refugis, 
                {
                    'query': query_text
                }
            )
            
            return response, None
            
        except Exception as e:
            logger.error(f'Error in search_refugis: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def get_refugi_coordinates(self, query_params: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Obtenir coordenades dels refugis
        Returns: (Dades de coordenades o None, missatge d'error o None)
        """
        try:
            # Obtenir paràmetre de límit
            limit = query_params.get('limit', 1000)
            try:
                limit = int(limit)
                if limit > 1000:
                    limit = 1000
            except ValueError:
                limit = 1000
            
            # Obtenir dades del DAO
            coords_data = self.refugi_dao.get_all_coordinates(limit)
            
            if not coords_data:
                return {
                    'count': 0,
                    'coordinates': [],
                    'message': 'No coordinates document found. Run extract_coords_to_firestore command first.'
                }, None
            
            # Convertir coordenades a models
            coordinates_list = self.refugi_mapper.coordinates_list_to_models(
                coords_data['coordinates']
            )
            
            # Formatar resposta
            response = self.refugi_mapper.format_coordinates_response(
                coordinates_list,
                coords_data['total_available']
            )
            
            return response, None
            
        except Exception as e:
            logger.error(f'Error in get_refugi_coordinates: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def health_check(self) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Comprovar l'estat de l'API i la connexió amb Firebase
        Returns: (Dades de health check, missatge d'error o None)
        """
        try:
            health_data = self.refugi_dao.health_check()
            
            response = {
                'status': 'healthy',
                'message': 'API is running correctly',
                'firebase': health_data['firebase'],
                'firestore': health_data['firestore'],
                'collections_count': health_data['collections_count']
            }
            
            return response, None
            
        except Exception as e:
            logger.error(f'Health check failed: {str(e)}')
            response = {
                'status': 'unhealthy',
                'message': f'Error: {str(e)}',
                'firebase': False
            }
            return response, f"Health check failed: {str(e)}"