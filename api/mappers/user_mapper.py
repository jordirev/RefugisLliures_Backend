"""
Mapper per a la transformació de dades d'usuaris entre Firebase i Django
"""
from typing import Dict, Any, Optional
from ..models.user import User

class UserMapper:
    """Mapper per transformar dades entre Firebase i models Django"""
    
    @staticmethod
    def firebase_to_model(firebase_data: Dict[str, Any]) -> User:
        """
        Converteix dades de Firebase a model Django User
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            User: Instància del model User
        """
        return User(
            uid=firebase_data.get('uid'),
            username=firebase_data.get('username', ''),
            email=firebase_data.get('email', ''),
            avatar=firebase_data.get('avatar', '')
        )
    
    @staticmethod
    def model_to_firebase(user: User) -> Dict[str, Any]:
        """
        Converteix model Django User a diccionari per Firebase
        
        Args:
            user: Instància del model User
            
        Returns:
            Dict: Diccionari amb dades per Firebase
        """
        return {
            'uid': user.uid,
            'username': user.username,
            'email': user.email,
            'avatar': user.avatar
        }
    
    @staticmethod
    def dict_to_model(user_dict: Dict[str, Any]) -> User:
        """
        Converteix diccionari a model Django User
        
        Args:
            user_dict: Diccionari amb dades d'usuari
            
        Returns:
            User: Instància del model User
        """
        return User(
            uid=user_dict.get('uid'),
            username=user_dict.get('username', ''),
            email=user_dict.get('email', ''),
            avatar=user_dict.get('avatar', '')
        )
    
    @staticmethod
    def model_to_dict(user: User) -> Dict[str, Any]:
        """
        Converteix model Django User a diccionari
        
        Args:
            user: Instància del model User
            
        Returns:
            Dict: Diccionari amb dades d'usuari
        """
        return {
            'uid': user.uid,
            'username': user.username,
            'email': user.email,
            'avatar': user.avatar
        }
    
    @staticmethod
    def validate_firebase_data(firebase_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Valida les dades rebudes de Firebase
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            tuple: (és_vàlid, missatge_error)
        """
        required_fields = ['uid', 'email']
        
        for field in required_fields:
            if not firebase_data.get(field):
                return False, f"Camp requerit '{field}' no trobat o buit"
        
        # Validació bàsica d'email
        email = firebase_data.get('email')
        if '@' not in email:
            return False, "Format d'email invàlid"
        
        return True, None
    
    @staticmethod
    def clean_firebase_data(firebase_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Neteja i normalitza les dades de Firebase
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            Dict: Dades netejades
        """
        cleaned_data = {}
        
        # UID (requerit)
        if firebase_data.get('uid'):
            cleaned_data['uid'] = str(firebase_data['uid']).strip()
        
        # Email (requerit)
        if firebase_data.get('email'):
            cleaned_data['email'] = str(firebase_data['email']).strip().lower()
        
        # Username (opcional)
        username = firebase_data.get('username', '')
        cleaned_data['username'] = str(username).strip() if username else ''
        
        # Avatar URL (opcional)
        avatar = firebase_data.get('avatar', '')
        cleaned_data['avatar'] = str(avatar).strip() if avatar else ''
        
        return cleaned_data