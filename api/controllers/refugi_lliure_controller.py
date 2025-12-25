"""
Controller per a la gestió de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from api.models.media_metadata import RefugeMediaMetadata
from api.utils.timezone_utils import get_madrid_now
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..daos.user_dao import UserDAO
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters
from ..services import r2_media_service

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDAO()
        self.user_dao = UserDAO()
        self.media_service = r2_media_service.get_refugi_media_service()
    
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
            
            # Excloure informació sensible si l'usuari no està autenticat
            if not is_authenticated:
                refugi.visitors = []
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
            
            # Excloure informació sensible si l'usuari no està autenticat
            if has_filters and not is_authenticated:
                for refugi in refugis_results:
                    refugi.visitors = []
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
            images_metadata_list = self.refugi_dao.get_media_metadata(refugi_id)
            
            if images_metadata_list is None:
                # Refugi no existeix
                return None, "Refugi not found"
            
            return images_metadata_list, None
            
        except Exception as e:
            logger.error(f"Error obtenint mitjans del refugi {refugi_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def upload_refugi_media(self, refugi_id: str, files: List[Any], creator_uid: str, experience_id: str = None, uploaded_at: str = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Puja mitjans per a un refugi
        
        Args:
            refugi_id: ID del refugi
            files: Llista de fitxers a pujar
            creator_uid: UID de l'usuari que puja els mitjans
            experience_id: ID de l'experiència associada (opcional)
            uploaded_at: Data i hora de pujada (ISO 8601 format, opcional) Si no es proporciona, es genera la data actual
            
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
                    if uploaded_at is None:
                        uploaded_at = get_madrid_now().isoformat()
                    
                    # Utilitzar la key com a clau del diccionari
                    key = result['key']
                    metadata = {
                        'creator_uid': creator_uid,
                        'uploaded_at': uploaded_at,
                        'experience_id': experience_id
                    }
                    media_metadata_dict[key] = metadata

                    # Generar l'objecte RefugeMediaMetadata per a la resposta
                    # Passar només l'entrada actual amb la key i metadata
                    single_entry = {key: metadata}
                    image_metadata = self.media_service.generate_media_metadata_from_dict(single_entry)
                    
                    uploaded.append(image_metadata.to_dict())  
                    
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
                
                # Incrementar el comptador de fotos pujades per l'usuari (només les pujades correctes)
                for _ in uploaded:
                    self.user_dao.increment_uploaded_photos(creator_uid)
            
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
            
            # Si el mitjà pertany a una experiència, eliminar-lo també de l'experiència
            experience_id = metadata_backup.get('experience_id') if metadata_backup else None
            if experience_id:
                from ..daos.experience_dao import ExperienceDAO
                experience_dao = ExperienceDAO()
                experience_dao.remove_media_key(experience_id, media_key)
            
            # Eliminar fitxer de R2
            try:
                self.media_service.delete_file(media_key)
            except Exception as e:
                logger.error(f"Error eliminant fitxer de R2: {str(e)}")

                # Restore Firestore media_metadata
                logger.info(f"Restoring Firestore media metadata for {media_key}")
                self.refugi_dao.add_media_metadata(refugi_id, {media_key: metadata_backup})
                
                # Restore experience media_key if needed
                if experience_id:
                    from ..daos.experience_dao import ExperienceDAO
                    experience_dao = ExperienceDAO()
                    experience_dao.add_media_key(experience_id, media_key)

                return False, "Error deleting file from storage"
            
            # Decrementar el comptador de fotos pujades per l'usuari
            # Obtenir creator_uid de les metadades
            if metadata_backup and 'creator_uid' in metadata_backup:
                creator_uid = metadata_backup['creator_uid']
                self.user_dao.decrement_uploaded_photos(creator_uid)
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant mitjà {media_key} del refugi {refugi_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"
        
    def delete_multiple_refugi_media(self, refugi_id: str, media_keys: List[str]) -> Tuple[bool, Optional[str]]:
        """
        Elimina múltiples mitjans d'un refugi amb bulk delete
        
        Args:
            refugi_id: ID del refugi
            media_keys: Llista de keys dels mitjans a eliminar
            
        Returns: (True si s'han eliminat correctament, missatge d'error o None)
        """
        try:
            # Eliminar metadades de Firestore (bulk delete)
            success, metadata_backup_list = self.refugi_dao.delete_multiple_media_metadata(refugi_id, media_keys)
            if not success or not metadata_backup_list:
                # Refugi no existeix o no s'han trobat mitjans
                return False, "Refugi or Media not found"
            
            # Agrupem les metadades per experience_id per optimitzar
            experiences_to_update = {}
            for metadata in metadata_backup_list:
                experience_id = metadata.get('experience_id')
                if experience_id:
                    if experience_id not in experiences_to_update:
                        experiences_to_update[experience_id] = []
                    experiences_to_update[experience_id].append(metadata['key'])
            
            # Eliminar fitxers de R2
            result = self.media_service.delete_files(media_keys)

            deleted_keys = result['deleted']
            failed_keys = result['failed']

            # Eliminar keys de les experiències
            if experiences_to_update:
                from ..daos.experience_dao import ExperienceDAO
                experience_dao = ExperienceDAO()
                for exp_id, keys in experiences_to_update.items():
                    for key in keys:
                        if key not in failed_keys:
                            experience_dao.remove_media_key(exp_id, key)

            # Si hi ha errors eliminant de R2, fer rollback de les failed_deletions
            if failed_keys:
                logger.error(f"Error eliminant {len(failed_keys)} fitxers de R2, fent rollback...")
                
                # Restore Firestore media_metadata
                restore_dict = {}
                for metadata in metadata_backup_list:
                    if metadata['key'] in failed_keys:
                        restore_dict[key] = metadata
                
                self.refugi_dao.add_media_metadata(refugi_id, restore_dict)
                
                return False, "Error deleting files from storage"

            # Decrementar el comptador de fotos pujades per usuari que no han fallat (agrupat per creator_uid)
            user_photo_counts = {}
            for metadata in metadata_backup_list:
                if metadata['key'] not in failed_keys:
                    creator_uid = metadata.get('creator_uid')
                    if creator_uid:
                        user_photo_counts[creator_uid] = user_photo_counts.get(creator_uid, 0) + 1
            
            # Decrementar amb count per cada usuari
            for creator_uid, count in user_photo_counts.items():
                self.user_dao.decrement_uploaded_photos(creator_uid, count)
            
            logger.info(f"Eliminats correctament {len(metadata_backup_list)} mitjans del refugi {refugi_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant múltiples mitjans del refugi {refugi_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"