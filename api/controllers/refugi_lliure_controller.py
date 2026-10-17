"""
Controller per a la gestió de refugis
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from api.models.media_metadata import RefugeMediaMetadata
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..daos.user_dao import UserDAO
from ..models.refugi_lliure import Refugi, RefugiCoordinates, RefugiSearchFilters
from ..services import r2_media_service
from ..services import audit_log_service as audit

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDAO()
        self.user_dao = UserDAO()
        self.media_service = r2_media_service.get_refugi_media_service()
    
    @staticmethod
    def filter_media_for_viewer(items, viewer_uid: Optional[str] = None, is_admin: bool = False):
        """Treu els mitjans amb status ≠ visible, llevat que qui consulta en sigui l'autor o un admin"""
        if not items:
            return items
        return [
            item for item in items
            if not hasattr(item, 'is_visible_to') or item.is_visible_to(viewer_uid, is_admin)
        ]

    def get_refugi_by_id(self, refuge_id: str, is_authenticated: bool, viewer_uid: Optional[str] = None,
                         is_admin: bool = False) -> Tuple[Optional[Refugi], Optional[str]]:
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
            else:
                refugi.images_metadata = self.filter_media_for_viewer(refugi.images_metadata, viewer_uid, is_admin)
            
            return refugi, None
            
        except Exception as e:
            logger.error(f'Error in get_refugi_by_id: {str(e)}')
            return None, f"Internal server error: {str(e)}"
    
    def search_refugis(self, query_params: Dict[str, Any], is_authenticated: bool, viewer_uid: Optional[str] = None,
                       is_admin: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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
            elif has_filters:
                for refugi in refugis_results:
                    refugi.images_metadata = self.filter_media_for_viewer(
                        getattr(refugi, 'images_metadata', None), viewer_uid, is_admin)
            
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
    
    def get_refugi_media(self, refugi_id: str, expiration: int = 3600, viewer_uid: Optional[str] = None,
                         is_admin: bool = False) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Obté la llista de tots els mitjans d'un refugi amb URLs prefirmades
        
        Args:
            refugi_id: ID del refugi
            expiration: Temps d'expiració de les URLs en segons
            
        Returns: (Llista de mitjans amb URLs o None, missatge d'error o None)
        """
        try:
            # Obtenir media_metadata de Firestore
            if viewer_uid is None and not is_admin:
                images_metadata_list = self.refugi_dao.get_media_metadata(refugi_id)
            else:
                images_metadata_list = self.refugi_dao.get_media_metadata(refugi_id, viewer_uid=viewer_uid, is_admin=is_admin)
            
            if images_metadata_list is None:
                # Refugi no existeix
                return None, "Refugi not found"

            # Registre d'accés a mitjans (art. 32 RGPD)
            audit.audit_log_service.log(viewer_uid, audit.ACTION_MEDIA_LIST, 'refuge', refugi_id,
                                        {'count': len(images_metadata_list)})
            
            return images_metadata_list, None
            
        except Exception as e:
            logger.error(f"Error obtenint mitjans del refugi {refugi_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def delete_refugi_media(self, refugi_id: str, media_key: str, actor_uid: Optional[str] = None) -> Tuple[bool, Optional[str]]:
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
            
            # Eliminar fitxer de R2 (delete_file retorna False, no llança: cal comprovar-ho)
            try:
                deleted = self.media_service.delete_file(media_key)
            except Exception as e:
                logger.error(f"Error eliminant fitxer de R2: {str(e)}")
                deleted = False

            if not deleted:
                # Rollback real: restaurar Firestore
                logger.info(f"Restoring Firestore media metadata for {media_key}")
                self.refugi_dao.add_media_metadata(refugi_id, {media_key: metadata_backup})
                if experience_id:
                    from ..daos.experience_dao import ExperienceDAO
                    experience_dao = ExperienceDAO()
                    experience_dao.add_media_keys_to_experience(experience_id, [media_key])
                return False, "Error deleting file from storage"

            # Miniatura (si n'hi ha): si falla només queda un fitxer orfe
            thumb_key = metadata_backup.get('thumb_key') if metadata_backup else None
            if thumb_key and not self.media_service.delete_file(thumb_key):
                logger.warning(f"Miniatura òrfena a R2: {thumb_key}")

            audit.audit_log_service.log(actor_uid, audit.ACTION_MEDIA_DELETE, 'media', media_key,
                                        {'refuge_id': refugi_id})
            
            # Eliminar la key de l'array de fotos pujades per l'usuari
            # Obtenir creator_uid de les metadades
            if metadata_backup and 'creator_uid' in metadata_backup:
                creator_uid = metadata_backup['creator_uid']
                self.user_dao.remove_uploaded_photos_keys(creator_uid, [media_key])
            
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

            # Miniatures dels mitjans esborrats (si fallen només queden orfes)
            for metadata in metadata_backup_list:
                thumb_key = metadata.get('thumb_key')
                if thumb_key and metadata['key'] in deleted_keys and not self.media_service.delete_file(thumb_key):
                    logger.warning(f"Miniatura òrfena a R2: {thumb_key}")

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
                        restore_dict[metadata['key']] = metadata
                
                self.refugi_dao.add_media_metadata(refugi_id, restore_dict)
                
                return False, "Error deleting files from storage"

            # Eliminar les keys de l'array de fotos pujades per usuari que no han fallat (agrupat per creator_uid)
            user_photo_keys = {}
            for metadata in metadata_backup_list:
                if metadata['key'] not in failed_keys:
                    creator_uid = metadata.get('creator_uid')
                    if creator_uid:
                        if creator_uid not in user_photo_keys:
                            user_photo_keys[creator_uid] = []
                        user_photo_keys[creator_uid].append(metadata['key'])
            
            # Eliminar keys per cada usuari
            for creator_uid, keys in user_photo_keys.items():
                self.user_dao.remove_uploaded_photos_keys(creator_uid, keys)
            
            logger.info(f"Eliminats correctament {len(metadata_backup_list)} mitjans del refugi {refugi_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant múltiples mitjans del refugi {refugi_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"