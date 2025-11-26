"""
Controller per a la gestió de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDAO()
    
    def get_refugi_by_id(self, refuge_id: str) -> Tuple[Optional[Refugi], Optional[str]]:
        """
        Obtenir un refugi per ID
        Returns: (Refugi o None, missatge d'error o None)
        """
        try:
            refugi = self.refugi_dao.get_by_id(refuge_id)
            
            if not refugi:
                return None, "Refugi not found"
            
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
            # Crear filtres de cerca des dels query_params validats
            filters = RefugiSearchFilters(
                name=query_params.get('name', '').strip(),
                region=query_params.get('region', '').strip(),
                departement=query_params.get('departement', '').strip(),
                type=query_params.get('type', '').strip(),
                places_min=query_params.get('places_min'),
                places_max=query_params.get('places_max'),
                altitude_min=query_params.get('altitude_min'),
                altitude_max=query_params.get('altitude_max'),
                cheminee=query_params.get('cheminee'),
                poele=query_params.get('poele'),
                couvertures=query_params.get('couvertures'),
                latrines=query_params.get('latrines'),
                bois=query_params.get('bois'),
                eau=query_params.get('eau'),
                matelas=query_params.get('matelas'),
                couchage=query_params.get('couchage'),
                lits=query_params.get('lits')
            )
            
            # Obtenir dades del DAO (ja inclou models si cal)
            search_result = self.refugi_dao.search_refugis(filters)
            refugis_results = search_result['results']
            has_filters = search_result['has_filters']
            
            # Prepare applied filters for response
            applied_filters = {
                'name': filters.name,
                'region': filters.region,
                'departement': filters.departement,
                'type': filters.type
            }
            # Only include non-empty filters in response
            applied_filters = {k: v for k, v in applied_filters.items() if v}
            
            # El DAO ja retorna models o dades raw segons calgui
            # Necessitem crear resposta segons el format
            from ..mappers.refugi_lliure_mapper import RefugiLliureMapper
            mapper = RefugiLliureMapper()
            
            if has_filters:
                # Filters applied - refugis_results són models
                response = mapper.format_search_response(refugis_results, applied_filters)
            else:
                # No filters - refugis_results són dades raw de coordenades
                response = mapper.format_search_response_from_raw_data(refugis_results, applied_filters)
            
            return response, None
            
        except Exception as e:
            logger.error(f'Error in search_refugis: {str(e)}')
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