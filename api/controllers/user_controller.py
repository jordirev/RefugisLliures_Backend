"""
Controller per a la gestió d'usuaris
"""
import logging
from typing import List, Optional, Dict, Any
from ..daos.user_dao import UserDAO
from ..mappers.user_mapper import UserMapper
from ..models.user import User

logger = logging.getLogger(__name__)

class UserController:
    """Controller per gestionar operacions d'usuaris"""
    
    def __init__(self):
        """Inicialitza el controller"""
        self.user_dao = UserDAO()
        self.user_mapper = UserMapper()
    
    def create_user(self, user_data: Dict[str, Any]) -> tuple[bool, Optional[User], Optional[str]]:
        """
        Crea un nou usuari
        
        Args:
            user_data: Diccionari amb les dades de l'usuari
            
        Returns:
            tuple: (success, user_object, error_message)
        """
        try:
            # Neteja i valida les dades
            cleaned_data = self.user_mapper.clean_firebase_data(user_data)
            is_valid, validation_error = self.user_mapper.validate_firebase_data(cleaned_data)
            
            if not is_valid:
                return False, None, validation_error
            
            # Comprova si l'usuari ja existeix
            if self.user_dao.user_exists(cleaned_data['uid']):
                return False, None, f"Usuari amb UID {cleaned_data['uid']} ja existeix"
            
            # Comprova si l'email ja està en ús
            existing_user = self.user_dao.get_user_by_email(cleaned_data['email'])
            if existing_user:
                return False, None, f"Email {cleaned_data['email']} ja està en ús"
            
            # Crea l'usuari a Firebase
            created_uid = self.user_dao.create_user(cleaned_data)
            if not created_uid:
                return False, None, "Error creant usuari a la base de dades"
            
            # Converteix a model
            user = self.user_mapper.dict_to_model(cleaned_data)
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
                return False, None, "UID no proporcionat"
            
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
                return False, None, "UID no proporcionat"
            
            # Comprova que l'usuari existeixi
            if not self.user_dao.user_exists(uid):
                return False, None, f"Usuari amb UID {uid} no trobat"
            
            # Neteja les dades (sense UID per evitar modificar-lo)
            update_data = {}
            if 'username' in user_data:
                update_data['username'] = str(user_data['username']).strip()
            if 'email' in user_data:
                new_email = str(user_data['email']).strip().lower()
                # Comprova si el nou email ja està en ús per un altre usuari
                existing_user = self.user_dao.get_user_by_email(new_email)
                if existing_user and existing_user.get('uid') != uid:
                    return False, None, f"Email {new_email} ja està en ús per un altre usuari"
                update_data['email'] = new_email
            if 'avatar' in user_data:
                update_data['avatar'] = str(user_data['avatar']).strip()
            
            if not update_data:
                return False, None, "No s'han proporcionat dades per actualitzar"
            
            # Actualitza a Firebase
            success = self.user_dao.update_user(uid, update_data)
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
                return False, "UID no proporcionat"
            
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
    
    def list_users(self, limit: int = 100, offset: int = 0) -> tuple[bool, List[User], Optional[str]]:
        """
        Obté una llista d'usuaris
        
        Args:
            limit: Nombre màxim d'usuaris a retornar
            offset: Nombre d'usuaris a saltar
            
        Returns:
            tuple: (success, user_list, error_message)
        """
        try:
            # Validació de paràmetres
            if limit < 1:
                limit = 100
            if offset < 0:
                offset = 0
            
            users_data = self.user_dao.list_users(limit, offset)
            users = [self.user_mapper.firebase_to_model(user_data) for user_data in users_data]
            
            return True, users, None
            
        except Exception as e:
            logger.error(f"Error en list_users: {str(e)}")
            return False, [], f"Error intern: {str(e)}"