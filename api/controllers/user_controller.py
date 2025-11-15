"""
Controller per a la gestió d'usuaris
"""
import logging
from typing import List, Optional, Dict, Any
from ..daos.user_dao import UserDAO
from ..mappers.user_mapper import UserMapper
from ..models.user import User
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

UID_NOT_PROVIDED_ERROR = "UID no proporcionat"

class UserController:
    """Controller per gestionar operacions d'usuaris"""
    
    def __init__(self):
        """Inicialitza el controller"""
        self.user_dao = UserDAO()
        self.user_mapper = UserMapper()
    
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
            existing_user = self.user_dao.get_user_by_email(user_data['email'])
            if existing_user:
                return False, None, f"Email {user_data['email']} ja està en ús"
            
            # Afegeix el UID a les dades de l'usuari
            user_data['uid'] = uid

            # Estableix la data de creació
            user_data['created_at'] = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()
            
            # Crea l'usuari a Firestore amb l'UID del token
            created_uid = self.user_dao.create_user(user_data, uid)
            if not created_uid:
                return False, None, "Error creant usuari a la base de dades"
            
            # Converteix a model
            user = self.user_mapper.firebase_to_model(user_data)
            logger.info(f"Usuari creat correctament amb UID: {created_uid}")
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
            
            user_data = self.user_dao.get_user_by_uid(uid)
            if not user_data:
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            user = self.user_mapper.firebase_to_model(user_data)
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
            
            user_data = self.user_dao.get_user_by_email(email.lower().strip())
            if not user_data:
                return False, None, f"Usuari amb email {email} no trobat"
            
            user = self.user_mapper.firebase_to_model(user_data)
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
                existing_user = self.user_dao.get_user_by_email(email_normalized)
                # Si existeix un usuari amb aquest email i no és l'usuari actual, error
                if existing_user and existing_user.get('uid') != uid:
                    return False, None, f"Email {user_data['email']} ja està en ús"
                # Re-escriu l'email normalitzat al payload per consistència
                user_data['email'] = email_normalized
            
            # Actualitza a Firebase
            success = self.user_dao.update_user(uid, user_data)
            if not success:
                return False, None, "Error actualitzant usuari a la base de dades"
            
            # Obté l'usuari actualitzat
            updated_data = self.user_dao.get_user_by_uid(uid)
            user = self.user_mapper.firebase_to_model(updated_data)
            
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
    
    