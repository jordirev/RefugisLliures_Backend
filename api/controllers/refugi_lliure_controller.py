"""
Controller per a la gestió de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from api.models.media_metadata import RefugeMediaMetadata
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters
from ..services.r2_media_service import get_refugi_media_service

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDAO()
        self.media_service = get_refugi_media_service()
    
    def get_refugi_by_id(self, refuge_id: str, is_authenticated: bool) -> Tuple[Optional[Refugi], Optional[str]]:
        """
        Obtenir un refugi per ID
        Args:
            refuge_id: ID del refugi
            include_visitors: Si True, inclou la llista de visitants. Si False, l'omet.
            include_media_metadata: Si True, inclou media_metadata i images_metadata. Si False, els omet.
        Returns: (Refugi o None, missatge d'error o None)
        """
        try:
            refugi = self.refugi_dao.get_by_id(refuge_id)
            
            if not refugi:
                return None, "Refugi not found"                
            
            # Si volem incloure metadades de mitjans, generar-les
            if is_authenticated:
                # Generar MediaMetadata amb URLs prefirmades per als mitjans si existeixen media_metadata
                if hasattr(refugi, 'media_metadata') and refugi.media_metadata:
                    try:
                        refugi.images_metadata = self.media_service.generate_media_metadata_list(refugi.media_metadata)
                    except Exception as e:
                        logger.warning(f"Error generant MediaMetadata per refugi {refuge_id}: {str(e)}")
                        refugi.images_metadata = []
                else:
                    refugi.images_metadata = []
            else:
                # No incloure metadades de mitjans
                refugi.visitors = []
                refugi.media_metadata = {}
                refugi.images_metadata = []
            
            return refugi, None
            
        except Exception as e:
            logger.error(f'Error in get_refugi_by_id: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def search_refugis(self, query_params: Dict[str, Any], is_authenticated: bool) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Cercar refugis amb filtres
        Args:
            query_params: Paràmetres de cerca
            include_visitors: Si True, inclou la llista de visitants. Si False, l'omet.
            include_media_metadata: Si True, inclou media_metadata i images_metadata. Si False, els omet.
        Returns: (Dades de resposta o None, missatge d'error o None)
        """
        try:
            # Crear filtres de cerca des dels query_params validats
            filters = RefugiSearchFilters(
                name=query_params.get('name', '').strip() if isinstance(query_params.get('name', ''), str) else '',
                type=query_params.get('type', []),
                condition=query_params.get('condition', []),
                places_min=query_params.get('places_min'),
                places_max=query_params.get('places_max'),
                altitude_min=query_params.get('altitude_min'),
                altitude_max=query_params.get('altitude_max'),
            )
            
            # Obtenir dades del DAO (ja inclou models si cal)
            search_result = self.refugi_dao.search_refugis(filters)
            refugis_results = search_result['results']
            has_filters = search_result['has_filters']
            
            # Generar MediaMetadata per als refugis amb filtres aplicats
            if has_filters:
                for refugi in refugis_results:
                    if is_authenticated:
                        if hasattr(refugi, 'media_metadata') and refugi.media_metadata:
                            try:
                                refugi.images_metadata = self.media_service.generate_media_metadata_list(refugi.media_metadata)
                            except Exception as e:
                                logger.warning(f"Error generant MediaMetadata per refugi {refugi.id}: {str(e)}")
                                refugi.images_metadata = []
                        else:
                            refugi.images_metadata = []
                    else:
                        # No incloure metadades de mitjans
                        # Si no volem incloure visitants, eliminar-los
                        refugi.visitors = []
                        refugi.media_metadata = {}
                        refugi.images_metadata = []
            
            # El DAO ja retorna models o dades raw segons calgui
            # Necessitem crear resposta segons el format
            from ..mappers.refugi_lliure_mapper import RefugiLliureMapper
            mapper = RefugiLliureMapper()
            
            if has_filters:
                # Filters applied - refugis_results són models
                response = mapper.format_search_response(refugis_results)
            else:
                # No filters - refugis_results són dades raw de coordenades
                response = mapper.format_search_response_from_raw_data(refugis_results)
            
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
    
    def get_refugi_media(self, refugi_id: str, expiration: int = 3600) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Obté la llista de tots els mitjans d'un refugi amb URLs prefirmades
        
        Args:
            refugi_id: ID del refugi
            expiration: Temps d'expiració de les URLs en segons
            
        Returns: (Llista de mitjans amb URLs o None, missatge d'error o None)
        """
        try:
            # Obtenir media_metadata de Firestore
            media_metadata_dict = self.refugi_dao.get_media_metadata(refugi_id)
            
            if media_metadata_dict is None:
                # Refugi no existeix
                return None, "Refugi not found"
            
            # Generar URLs prefirmades per cada mitjà
            media_with_urls = []
            for key, metadata in media_metadata_dict.items():
                try:
                    url = self.media_service.generate_presigned_url(key, expiration)

                    # Crear instància de RefugeMediaMetadata
                    media_metadata = RefugeMediaMetadata(
                        key=key,
                        url=url,
                        creator_uid=metadata.get('creator_uid', ''),
                        uploaded_at=metadata.get('uploaded_at', '')
                    )

                    media_with_urls.append(media_metadata.to_dict())
                
                except Exception as e:
                    logger.warning(f"Error generant URL per {key}: {str(e)}")
            
            return media_with_urls, None
            
        except Exception as e:
            logger.error(f"Error obtenint mitjans del refugi {refugi_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def upload_refugi_media(self, refugi_id: str, files: List[Any], creator_uid: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Puja mitjans per a un refugi
        
        Args:
            refugi_id: ID del refugi
            files: Llista de fitxers a pujar
            creator_uid: UID de l'usuari que puja els mitjans
            
        Returns: (Diccionari amb uploaded i failed o None, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refugi_id):
                return None, "Refugi not found"
            
            uploaded = []
            failed = []
            media_metadata_dict = {}
            
            for file in files:
                try:
                    # Obtenir content type
                    content_type = file.content_type
                    
                    # Pujar fitxer
                    result = self.media_service.upload_file(
                        file_content=file,
                        entity_id=refugi_id,
                        content_type=content_type,
                        filename=file.name
                    )
                    
                    # Crear metadades del mitjà
                    from ..utils.timezone_utils import get_madrid_today
                    uploaded_at = get_madrid_today().isoformat()
                    
                    # Utilitzar la key com a clau del diccionari
                    media_metadata_dict[result['key']] = {
                        'creator_uid': creator_uid,
                        'uploaded_at': uploaded_at
                    }

                    # Crear instància de MediaMetadata
                    media_metadata = RefugeMediaMetadata(
                        key=result['key'],
                        url=result['url'],
                        creator_uid=creator_uid,
                        uploaded_at=uploaded_at
                    )
                    
                    uploaded.append(media_metadata.to_dict())  
                    
                except ValueError as e:
                    failed.append({
                        'filename': file.name,
                        'error': str(e)
                    })
                except Exception as e:
                    logger.error(f"Error pujant fitxer {file.name}: {str(e)}")
                    failed.append({
                        'filename': file.name,
                        'error': 'Error intern pujant el fitxer'
                    })
            
            # Actualitzar Firestore amb les noves media_metadata
            if media_metadata_dict:
                success = self.refugi_dao.add_media_metadata(refugi_id, media_metadata_dict)
                if not success:
                    logger.warning(f"No s'han pogut guardar les metadata a Firestore per refugi {refugi_id}")
                    # Si no s'ha pogut guardar, eliminar els fitxers pujats
                    self.media_service.delete_files([item['key'] for item in uploaded])
                    return None, "Error intern guardant les metadades a Firestore"
            
            return {
                'uploaded': uploaded,
                'failed': failed
            }, None
            
        except Exception as e:
            logger.error(f"Error pujant mitjans al refugi {refugi_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def delete_refugi_media(self, refugi_id: str, media_key: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina un mitjà d'un refugi
        
        Args:
            refugi_id: ID del refugi
            media_key: Key del mitjà a eliminar
            
        Returns: (True si s'ha eliminat correctament, missatge d'error o None)
        """
        try:
            # Eliminar metadades de Firestore
            success, metadata_backup = self.refugi_dao.delete_media_metadata(refugi_id, media_key)
            if not success:
                # Refugi no existeix
                return False, "Refugi or Media not found"
            
            # Eliminar fitxer de R2
            try:
                self.media_service.delete_file(media_key)
            except Exception as e:
                logger.error(f"Error eliminant fitxer de R2: {str(e)}")

                # Restore Firestore media_metadata
                logger.info(f"Restoring Firestore media metadata for {media_key}")
                self.refugi_dao.add_media_metadata(refugi_id, {media_key: metadata_backup})

                return False, "Error deleting file from storage"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant mitjà {media_key} del refugi {refugi_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"