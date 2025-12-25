"""
Controller per a la gestió d'experiències
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..daos.experience_dao import ExperienceDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..daos.user_dao import UserDAO
from ..models.experience import Experience
from ..models.media_metadata import RefugeMediaMetadata
from ..services import r2_media_service
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)


class ExperienceController:
    """Controller per a la gestió d'experiències"""
    
    def __init__(self):
        self.experience_dao = ExperienceDAO()
        self.refugi_dao = RefugiLliureDAO()
        self.refugi_controller = RefugiLliureController()
        self.user_dao = UserDAO()
        self.media_service = r2_media_service.get_refugi_media_service()
    
    def get_experiences_by_refuge(self, refuge_id: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Obté totes les experiències d'un refugi amb URLs prefirmades
        
        Args:
            refuge_id: ID del refugi
            
        Returns:
            (Llista d'experiències amb metadata o None, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refuge_id):
                return None, "Refuge not found"
            
            # Obtenir experiències del DAO (ja genera URLs prefirmades)
            experiences = self.experience_dao.get_experiences_by_refuge_id(refuge_id)

            return experiences, None
            
        except Exception as e:
            logger.error(f"Error obtenint experiències del refugi {refuge_id}: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def create_experience(
        self,
        refuge_id: str,
        creator_uid: str,
        comment: str,
        files: Optional[List[Any]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, List[Any]]], Optional[str]]:
        """
        Crea una nova experiència per a un refugi
        
        Args:
            refuge_id: ID del refugi
            creator_uid: UID de l'usuari creador
            comment: Comentari de l'experiència
            files: Llista de fitxers a pujar (opcional)
            
        Returns:
            (Model de l'experiència o None, Diccionari dels mitjans uploaded i failed o None, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refuge_id):
                return None, None, "Refuge not found"
            
            modified_at = get_madrid_now().isoformat()

            # Crear dades de l'experiència
            experience_data = {
                'refuge_id': refuge_id,
                'creator_uid': creator_uid,
                'comment': comment,
                'modified_at': modified_at,
                'media_keys': []
            }
            
            # Crear l'experiència a Firestore
            experience = self.experience_dao.create_experience(experience_data)
            if not experience:
                return None, None, "Error creating experience"
            
            # Pujar fitxers si n'hi ha
            upload_result = None
            if files and len(files) > 0:
                # Primer, pujar mitjans al refugi
                upload_result, error = self._upload_experience_media_to_refuge(
                    experience.id,
                    refuge_id,
                    files,
                    creator_uid,
                    uploaded_at=modified_at
                )
                if error:
                    return experience, None, error
                
                # Després, actualitzar llista de media_keys a l'experiència amb els mitjans pujats
                uploaded = upload_result.get('uploaded', [])
                media_keys = [media['key'] for media in uploaded]
                if media_keys:
                    success, error = self.experience_dao.add_media_keys_to_experience(
                        experience.id,
                        media_keys
                    )
                    if not success:
                        message = f"Error actualitzant media_keys de l'experiència {experience.id}: {error}"
                        logger.error(message)
                        return experience, upload_result, message
            
            experience = self.experience_dao.get_experience_by_id(experience.id)
            return experience, upload_result, None
            
        except Exception as e:
            logger.error(f"Error creant experiència: {str(e)}")
            return None, f"Internal server error: {str(e)}"
    
    def update_experience(
        self,
        experience_id: str,
        comment: Optional[str] = None,
        files: Optional[List[Any]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, List[Any]]], Optional[str]]:
        """
        Actualitza una experiència
        
        Args:
            experience_id: ID de l'experiència
            comment: Nou comentari (opcional)
            files: Nous fitxers a pujar (opcional)
            
        Returns:
            (Model d'experiencia actualitzat o None, Diccionari dels mitjans uploaded i failed o None, missatge d'error o None)
        """
        try:

            # Obtenir l'experiència existent
            experience = self.experience_dao.get_experience_by_id(experience_id)
            if not experience:
                return None, None, "Experience not found"
            
            modified_at = get_madrid_now().isoformat()

            # Preparar dades d'actualització
            update_data = {
                'modified_at': modified_at
            }
            
            if comment is not None:
                update_data['comment'] = comment
            
            # Pujar nous fitxers si n'hi ha
            upload_result = None
            if files and len(files) > 0:
                upload_result, error = self._upload_experience_media_to_refuge(
                    experience_id,
                    experience.refuge_id,
                    files,
                    experience.creator_uid,
                    uploaded_at=modified_at
                )
                if error:
                    return None, None, error
                
                # Recollir les noves claus de media
                uploaded = upload_result.get('uploaded', [])
                update_data['media_keys'] = [media['key'] for media in uploaded]

            # Actualitzar l'experiència
            updated_experience, error = self.experience_dao.update_experience(experience_id, update_data)
            if not updated_experience:
                return None, upload_result, error or "Error updating experience"
            
            # Obtenir l'experiència actualitzada
            updated_experience = self.experience_dao.get_experience_by_id(experience_id)
            return updated_experience, upload_result, None
            
        except Exception as e:
            logger.error(f"Error actualitzant experiència {experience_id}: {str(e)}")
            return None, None, f"Internal server error: {str(e)}"
    
    def delete_experience(self, experience_id: str, refuge_id) -> Tuple[bool, Optional[str]]:
        """
        Elimina una experiència i tots els seus mitjans
        
        Args:
            experience_id: ID de l'experiència
            
        Returns:
            (True si s'ha eliminat correctament, missatge d'error o None)
        """
        try:
            # Verificar que el refugi existeix
            if not self.refugi_dao.refugi_exists(refuge_id):
                return None, None, "Refuge not found"
            
            # Obtenir l'experiència
            experience = self.experience_dao.get_experience_by_id(experience_id)
            if not experience:
                return False, "Experience not found"
            
            # Eliminar fitxers del refugi associats amb l'experiencia
            if experience.media_keys and len(experience.media_keys) > 0:
                try:
                    # Eliminar metadata del refugi
                    success, error = self.refugi_controller.delete_multiple_refugi_media(refugi_id=refuge_id, media_keys=experience.media_keys)

                    # Si fallen algunes eliminacions de fitxers, no eliminar l'experiencia
                    if not success:
                        message = "Error deleting some refuge media: " + error
                        logger.error(message)
                        return False, message
                        
                except Exception as e:
                    logger.error(f"Error eliminant fitxers de l'experiència: {str(e)}")
                    return False, "Error deleting experience media"
            
            # Eliminar l'experiència de Firestore
            success, error = self.experience_dao.delete_experience(experience_id)
            if not success:
                return False, error or "Error deleting experience"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant experiència {experience_id}: {str(e)}")
            return False, f"Internal server error: {str(e)}"
    
    def _upload_experience_media_to_refuge(
        self,
        experience_id: str,
        refuge_id: str,
        files: List[Any],
        creator_uid: str,
        uploaded_at: str
    ) -> Tuple[Optional[Dict[str, List[Any]]], Optional[str]]:
        """
        Puja mitjans al refugi d'una experiència
        
        Args:
            experience_id: ID de l'experiència
            refuge_id: ID del refugi
            files: Llista de fitxers a pujar
            creator_uid: UID de l'usuari creador
            uploaded_at: Data i hora de pujada (ISO 8601 format)
            
        Returns:
            Tuple(Diccionari amb uploaded i failed o None, missatge d'error o None)
        """
        try:            
            # Pujar mitjans al refugi de la experiència
            refugi_controller = RefugiLliureController()
            result, error = refugi_controller.upload_refugi_media(
                refugi_id=refuge_id,
                files=files,
                creator_uid=creator_uid,
                experience_id=experience_id,
                uploaded_at=uploaded_at
            )

            if result is None:
                message = 'Error uploading experience media to refuge: ' + (error or '')
                logger.error(message)
                return None, message
            
            return result, None
            
        except Exception as e:
            logger.error(f"Error pujant mitjans de l'experiència: {str(e)}")
            return None, str(e)