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
        return User.from_dict(firebase_data)
    
    @staticmethod
    def model_to_firebase(user: User) -> Dict[str, Any]:
        """
        Converteix model Django User a diccionari per Firebase
        
        Args:
            user: Instància del model User
            
        Returns:
            Dict: Diccionari amb dades per Firebase
        """
        return User.to_dict(user)
    
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
        
        # Validació d'idioma
        language = firebase_data.get('language', 'ca')
        valid_languages = ['ca', 'es', 'en', 'fr']
        if language not in valid_languages:
            return False, f"Idioma no vàlid. Opcions vàlides: {', '.join(valid_languages)}"
        
        return True, None
    
    @staticmethod
    def clean_firebase_data(firebase_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Neteja i prepara les dades de Firebase per a l'ús intern
        
        Args:
            firebase_data: Diccionari amb dades de Firebase
            
        Returns:
            Dict: Diccionari netejat
        """
        cleaned_data = firebase_data.copy()
        
        if 'email' in cleaned_data and isinstance(cleaned_data['email'], str):
            cleaned_data['email'] = cleaned_data['email'].lower().strip()
        
        if 'username' in cleaned_data and isinstance(cleaned_data['username'], str):
            cleaned_data['username'] = cleaned_data['username'].strip()

        if 'language' in cleaned_data and isinstance(cleaned_data['language'], str):
            cleaned_data['language'] = cleaned_data['language'].strip().lower()
        
        return cleaned_data