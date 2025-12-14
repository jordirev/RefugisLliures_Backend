"""
Controller per a la gestió d'usuaris
"""
import logging
from typing import List, Optional, Dict, Any, Tuple

from api.models.media_metadata import MediaMetadata
from ..daos.user_dao import UserDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..models.user import User
from ..utils.timezone_utils import get_madrid_now
from ..services import r2_media_service

logger = logging.getLogger(__name__)

UID_NOT_PROVIDED_ERROR = "UID no proporcionat"

class UserController:
    """Controller per gestionar operacions d'usuaris"""
    
    def __init__(self):
        """Inicialitza el controller"""
        self.user_dao = UserDAO()
        self.refugi_dao = RefugiLliureDAO()
        self.avatar_service = r2_media_service.get_user_avatar_service()
    
    def create_user(self, user_data: Dict[str, Any], uid: str) -> tuple[bool, Optional[User], Optional[str]]:
        """
        Crea un nou usuari amb el UID del token de Firebase
        
        Args:
            user_data: Diccionari amb les dades de l'usuari
            uid: UID del token de Firebase
            
        Returns:
            tuple: (success, user_object, error_message)
        """
        try:            
            # Comprova si l'usuari ja existeix amb aquest UID
            existing_user = self.user_dao.get_user_by_uid(uid)
            if existing_user:
                return False, None, f"Usuari amb UID {uid} ja existeix"
            
            # Comprova si l'email ja està en ús
            email_exists = self.user_dao.user_exists_by_email(user_data['email'])
            if email_exists:
                return False, None, f"Email {user_data['email']} ja està en ús"
            
            # Afegeix el UID a les dades de l'usuari
            user_data['uid'] = uid

            # Estableix la data de creació
            user_data['created_at'] = get_madrid_now().isoformat()
            
            # Crea l'usuari a Firestore amb l'UID del token (retorna model)
            user = self.user_dao.create_user(user_data, uid)
            if not user:
                return False, None, "Error creant usuari a la base de dades"
            
            logger.info(f"Usuari creat correctament amb UID: {uid}")
            return True, user, None
            
        except Exception as e:
            logger.error(f"Error en create_user: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def get_user_by_uid(self, uid: str) -> tuple[bool, Optional[User], Optional[str]]:
        """
        Obté un usuari per UID
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, user_object, error_message)
        """
        try:
            if not uid:
                return False, None, UID_NOT_PROVIDED_ERROR
            
            user = self.user_dao.get_user_by_uid(uid)
            if not user:
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            return True, user, None
            
        except Exception as e:
            logger.error(f"Error en get_user_by_uid: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def get_user_by_email(self, email: str) -> tuple[bool, Optional[User], Optional[str]]:
        """
        Obté un usuari per email
        
        Args:
            email: Email de l'usuari
            
        Returns:
            tuple: (success, user_object, error_message)
        """
        try:
            if not email:
                return False, None, "Email no proporcionat"
            
            user = self.user_dao.get_user_by_email(email.lower().strip())
            if not user:
                return False, None, f"Usuari amb email {email} no trobat"
            
            return True, user, None
            
        except Exception as e:
            logger.error(f"Error en get_user_by_email: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def update_user(self, uid: str, user_data: Dict[str, Any]) -> tuple[bool, Optional[User], Optional[str]]:
        """
        Actualitza les dades d'un usuari
        
        Args:
            uid: UID de l'usuari
            user_data: Diccionari amb les noves dades
            
        Returns:
            tuple: (success, user_object, error_message)
        """
        try:
            if not uid:
                return False, None, UID_NOT_PROVIDED_ERROR
            
            # Comprova que l'usuari existeixi
            if not self.user_dao.user_exists(uid):
                return False, None, f"Usuari amb UID {uid} no trobat"
        
            if not user_data:
                return False, None, "No s'han proporcionat dades per actualitzar"

            # Si s'envia un email a actualitzar, comprova que no estigui en ús per un altre usuari
            if 'email' in user_data and user_data.get('email'):
                # Normalitza l'email abans de la cerca
                email_normalized = user_data['email'].lower().strip()
                # Comprova si l'email existeix
                email_exists = self.user_dao.user_exists_by_email(email_normalized)
                if email_exists:
                    # Si existeix, obté l'usuari per veure si és el mateix
                    existing_user = self.user_dao.get_user_by_email(email_normalized)
                    if existing_user and existing_user.uid != uid:
                        return False, None, f"Email {user_data['email']} ja està en ús"
                # Re-escriu l'email normalitzat al payload per consistència
                user_data['email'] = email_normalized
            
            # Actualitza a Firebase
            success = self.user_dao.update_user(uid, user_data)
            if not success:
                return False, None, "Error actualitzant usuari a la base de dades"
            
            # Obté l'usuari actualitzat (ja és un model)
            user = self.user_dao.get_user_by_uid(uid)
            
            logger.info(f"Usuari actualitzat correctament amb UID: {uid}")
            return True, user, None
            
        except Exception as e:
            logger.error(f"Error en update_user: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def delete_user(self, uid: str) -> tuple[bool, Optional[str]]:
        """
        Elimina un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            if not uid:
                return False, UID_NOT_PROVIDED_ERROR
            
            # Comprova que l'usuari existeixi
            if not self.user_dao.user_exists(uid):
                return False, f"Usuari amb UID {uid} no trobat"
            
            # Elimina de Firebase
            success = self.user_dao.delete_user(uid)
            if not success:
                return False, "Error eliminant usuari de la base de dades"
            
            logger.info(f"Usuari eliminat correctament amb UID: {uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error en delete_user: {str(e)}")
            return False, f"Error intern: {str(e)}"
    
    # Patró Template Method per gestionar llistes de refugis
    def _manage_refugi_list(
        self, 
        uid: str, 
        refuge_id: str, 
        list_type: str, 
        operation: str,
        operation_name: str
    ) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Mètode plantilla per gestionar refugis en llistes (preferits/visitats)
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi
            list_type: Tipus de llista ('favourite_refuges' o 'visited_refuges')
            operation: Tipus d'operació ('add' o 'remove')
            operation_name: Nom de l'operació per als missatges d'error i logs
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        try:
            # Validacions comunes
            if not uid:
                return False, None, UID_NOT_PROVIDED_ERROR
            
            if not refuge_id:
                return False, None, "ID del refugi no proporcionat"
            
            if not self.user_dao.user_exists(uid):
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            if not self.refugi_dao.refugi_exists(refuge_id):
                return False, None, f"Refugi amb ID {refuge_id} no trobat"
            
            # Operació sobre la llista de l'usuari
            if operation == 'add':
                success, list_refugis = self.user_dao.add_refugi_to_list(uid, refuge_id, list_type)
                error_msg = f"Error afegint refugi als {operation_name}"
            else:  # remove
                success, list_refugis = self.user_dao.remove_refugi_from_list(uid, refuge_id, list_type)
                error_msg = f"Error eliminant refugi dels {operation_name}"
            
            if not success:
                return False, None, error_msg
            
            # Hook: operació específica al refugi (només per visitats)
            self._update_refugi_visitor_list(uid, refuge_id, list_type, operation)
            
            # Obté la informació actualitzada
            refugis_info = self.user_dao.get_refugis_info(uid, list_type, refugis_ids=list_refugis)
            
            action = "afegit" if operation == 'add' else "eliminat"
            preposition = "als" if operation == 'add' else "dels"
            logger.info(f"Refugi {refuge_id} {action} {preposition} {operation_name} de l'usuari {uid}")
            return True, refugis_info, None
            
        except Exception as e:
            method_name = f"{operation}_refugi_{list_type.split('_')[1][:-1]}"
            logger.error(f"Error en {method_name}: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def _update_refugi_visitor_list(self, uid: str, refuge_id: str, list_type: str, operation: str) -> None:
        """
        Hook method: actualitza la llista de visitants del refugi només si és necessari
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi
            list_type: Tipus de llista
            operation: Tipus d'operació ('add' o 'remove')
        """
        if list_type == 'visited_refuges':
            if operation == 'add':
                visitor_success = self.refugi_dao.add_visitor_to_refugi(refuge_id, uid)
                if not visitor_success:
                    logger.warning(f"No s'ha pogut afegir l'usuari {uid} a la llista de visitants del refugi {refuge_id}")
            else:  # remove
                visitor_success = self.refugi_dao.remove_visitor_from_refugi(refuge_id, uid)
                if not visitor_success:
                    logger.warning(f"No s'ha pogut eliminar l'usuari {uid} de la llista de visitants del refugi {refuge_id}")
    
    def _get_refugis_info_by_type(self, uid: str, list_type: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Mètode plantilla per obtenir informació de refugis per tipus de llista
        
        Args:
            uid: UID de l'usuari
            list_type: Tipus de llista ('favourite_refuges' o 'visited_refuges')
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        try:
            if not uid:
                return False, None, UID_NOT_PROVIDED_ERROR
            
            if not self.user_dao.user_exists(uid):
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            refugis_info = self.user_dao.get_refugis_info(uid, list_type)
            return True, refugis_info, None
            
        except Exception as e:
            list_name = list_type.split('_')[1]
            logger.error(f"Error en get_refugis_{list_name}_info: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    # Mètodes públics per preferits
    def add_refugi_preferit(self, uid: str, refuge_id: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Afegeix un refugi als preferits de l'usuari
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi a afegir
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._manage_refugi_list(uid, refuge_id, 'favourite_refuges', 'add', 'preferits')
    
    def remove_refugi_preferit(self, uid: str, refuge_id: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Elimina un refugi dels preferits de l'usuari
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi a eliminar
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._manage_refugi_list(uid, refuge_id, 'favourite_refuges', 'remove', 'preferits')
    
    def get_refugis_preferits_info(self, uid: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Obté la informació dels refugis preferits de l'usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._get_refugis_info_by_type(uid, 'favourite_refuges')
    
    # Mètodes públics per visitats
    def add_refugi_visitat(self, uid: str, refuge_id: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Afegeix un refugi als visitats de l'usuari i actualitza la llista de visitants del refugi
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi a afegir
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._manage_refugi_list(uid, refuge_id, 'visited_refuges', 'add', 'visitats')
    
    def remove_refugi_visitat(self, uid: str, refuge_id: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Elimina un refugi dels visitats de l'usuari i actualitza la llista de visitants del refugi
        
        Args:
            uid: UID de l'usuari
            refuge_id: ID del refugi a eliminar
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._manage_refugi_list(uid, refuge_id, 'visited_refuges', 'remove', 'visitats')
    
    def get_refugis_visitats_info(self, uid: str) -> tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Obté la informació dels refugis visitats de l'usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, list_refugis_info, error_message)
        """
        return self._get_refugis_info_by_type(uid, 'visited_refuges')
    
    def upload_user_avatar(self, uid: str, file: Any) -> Tuple[bool, Optional[MediaMetadata], Optional[str]]:
        """
        Puja o actualitza l'avatar d'un usuari
        
        Args:
            uid: UID de l'usuari
            file: Fitxer de l'avatar a pujar
            
        Returns:
            tuple: (success, avatar_metadata, error_message)
        """
        try:
            # Verificar que l'usuari existeix
            user = self.user_dao.get_user_by_uid(uid)
            if not user:
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            # Si ja té un avatar, eliminar-lo abans de pujar el nou
            if user.avatar_metadata:
                old_key = user.avatar_metadata.key
                if old_key:
                    try:
                        self.avatar_service.delete_file(old_key)
                        logger.info(f"Avatar anterior eliminat: {old_key}")
                    except Exception as e:
                        logger.warning(f"Error eliminant avatar anterior: {str(e)}")
            
            # Pujar nou avatar
            content_type = file.content_type
            result = self.avatar_service.upload_file(
                file_content=file,
                entity_id=uid,
                content_type=content_type,
                filename=file.name
            )
            
            # Preparar metadades
            from ..utils.timezone_utils import get_madrid_today
            media_metadata = {
                'key': result['key'],
                'uploaded_at': get_madrid_today().isoformat()
            }
            
            # Actualitzar metadades a Firestore
            success = self.user_dao.update_avatar_metadata(uid, media_metadata)
            if not success:
                # Si falla l'actualització a Firestore, intentar eliminar el fitxer pujat
                try:
                    self.avatar_service.delete_file(result['key'])
                except:
                    pass
                return False, None, "Error actualitzant metadades de l'avatar"
            else:
                logger.info(f"Avatar pujat correctament per l'usuari {uid}")
                #Generar objecte MediaMetadata per retornar
                media_service = r2_media_service.get_user_avatar_service()
                avatar_metadata = media_service.generate_media_metadata_from_dict(media_metadata)
                return True, avatar_metadata, None
            
        except ValueError as e:
            logger.warning(f"Error de validació pujant avatar: {str(e)}")
            return False, None, str(e)
        except Exception as e:
            logger.error(f"Error pujant avatar per l'usuari {uid}: {str(e)}")
            return False, None, f"Error intern: {str(e)}"
    
    def delete_user_avatar(self, uid: str) -> Tuple[bool, Optional[str]]:
        """
        Elimina l'avatar d'un usuari
        
        Args:
            uid: UID de l'usuari
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            # Obtenir metadades de l'avatar abans d'eliminar
            success, media_metadata = self.user_dao.delete_avatar_metadata(uid)
            
            if not success:
                return False, f"Usuari amb UID {uid} no trobat"
            
            if not media_metadata:
                return False, "L'usuari no té cap avatar"
            
            # Eliminar fitxer de R2
            media_key = media_metadata.get('key')
            if media_key:
                try:
                    self.avatar_service.delete_file(media_key)
                    logger.info(f"Avatar eliminat de R2: {media_key}")
                except Exception as e:
                    logger.error(f"Error eliminant avatar de R2: {str(e)}")
                    # Tornar a afegir les metadades a l'usuari a Firestore ja que no s'ha pogut eliminar el fitxer
                    self.user_dao.update_avatar_metadata(uid, media_metadata)
            
            logger.info(f"Avatar eliminat correctament per l'usuari {uid}")
            return True, None
            
        except Exception as e:
            logger.error(f"Error eliminant avatar per l'usuari {uid}: {str(e)}")
            return False, f"Error intern: {str(e)}"
    
    
    