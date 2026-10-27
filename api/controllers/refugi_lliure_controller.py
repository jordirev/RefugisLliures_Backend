"""
Controller legacy de refugis: només el health check i l'esborrat en bloc de mitjans (Firestore), que encara
usen altres dominis (experiències, propostes, usuaris). Les lectures, la cerca i l'esborrat d'un mitjà viuen a
`apps.refuges` (selectors/services). S'elimina al chunk 11.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..services import r2_media_service
from ..services.database_health import check_database

logger = logging.getLogger(__name__)

class RefugiLliureController:
    """Controller per a la gestió de refugis"""
    
    def __init__(self):
        self.refugi_dao = RefugiLliureDAO()
        self._media_service = None

    @property
    def media_service(self):
        """Servei R2, creat sota demanda (el health check i les lectures no han de dependre d'R2)"""
        if self._media_service is None:
            self._media_service = r2_media_service.get_refugi_media_service()
        return self._media_service

    @media_service.setter
    def media_service(self, value):
        self._media_service = value
    

    
    

    
    def health_check(self) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Comprovar l'estat de l'API, la connexió amb PostgreSQL (`SELECT 1`) i amb Firebase
        Returns: (Dades de health check, missatge d'error o None)
        """
        database_ok = check_database()
        try:
            health_data = self.refugi_dao.health_check()
        except Exception as e:
            logger.error(f'Health check failed: {type(e).__name__}')
            response = {
                'status': 'unhealthy',
                'message': 'Health check failed' if database_ok else 'Database unavailable',
                'firebase': False,
                'database': database_ok
            }
            return response, "Health check failed"

        if not database_ok:
            return {
                'status': 'unhealthy',
                'message': 'Database unavailable',
                'firebase': health_data['firebase'],
                'firestore': health_data['firestore'],
                'collections_count': health_data['collections_count'],
                'database': False
            }, "Health check failed: database unavailable"

        response = {
            'status': 'healthy',
            'message': 'API is running correctly',
            'firebase': health_data['firebase'],
            'firestore': health_data['firestore'],
            'collections_count': health_data['collections_count'],
            'database': True
        }
        return response, None
    
    
        
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
            
            # Eliminar fitxers de R2
            result = self.media_service.delete_files(media_keys)

            deleted_keys = result['deleted']
            failed_keys = result['failed']

            # Miniatures dels mitjans esborrats (si fallen només queden orfes)
            for metadata in metadata_backup_list:
                thumb_key = metadata.get('thumb_key')
                if thumb_key and metadata['key'] in deleted_keys and not self.media_service.delete_file(thumb_key):
                    logger.warning(f"Miniatura òrfena a R2: {thumb_key}")

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

            logger.info(f"Eliminats correctament {len(metadata_backup_list)} mitjans del refugi {refugi_id}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant múltiples mitjans del refugi {refugi_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"