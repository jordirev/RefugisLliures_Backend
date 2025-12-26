"""
Model d'usuari per a l'aplicació RefugisLliures
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from venv import logger

from api.services import r2_media_service
from .media_metadata import MediaMetadata

@dataclass
class User:
    """Model per representar un usuari"""
    uid: str
    username: str
    email: str
    avatar_metadata: MediaMetadata = None  # Metadades amb URLs prefirmades (generades dinàmicament) {'key': str, 'url': str, 'uploaded_at': str}
    language: str = 'ca'
    favourite_refuges: Optional[list] = None # Llista d'IDs de refugis preferits
    visited_refuges: Optional[list] = None # Llista d'IDs de refugis visitats
    uploaded_photos_keys: Optional[List[str]] = None # Llista de keys de fotos pujades
    num_shared_experiences: int = 0
    num_renovated_refuges: int = 0
    created_at: str = ''

    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.uid:
            raise ValueError("UID és requerit")
        if not self.email:
            raise ValueError("Email és requerit")
        if '@' not in self.email:
            raise ValueError("Format d'email invàlid")
    
    def to_dict(self) -> dict:
        """Converteix l'usuari a diccionari"""

        media_metadata = {}
        if self.avatar_metadata:
            media_metadata = {
                'key': self.avatar_metadata.key,
                'uploaded_at': self.avatar_metadata.uploaded_at
            }

        return {
            'uid': self.uid,
            'username': self.username,
            'email': self.email,
            'media_metadata': media_metadata,
            'avatar_metadata': self.avatar_metadata.to_dict() if self.avatar_metadata else None,
            'language': self.language,
            'favourite_refuges': self.favourite_refuges,
            'visited_refuges': self.visited_refuges,
            'uploaded_photos_keys': self.uploaded_photos_keys,
            'num_shared_experiences': self.num_shared_experiences,
            'num_renovated_refuges': self.num_renovated_refuges,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Crea un usuari des d'un diccionari"""

        # Generem les metadades amb URL prefirmada per a l'avatar
        avatar_metadata = None
        if 'media_metadata' in data and data['media_metadata']:
            try:
                media_service = r2_media_service.get_user_avatar_service()
                avatar_metadata = media_service.generate_media_metadata_from_dict(data['media_metadata'])
            except Exception as e:
                logger.warning(f"Error generant MediaMetadata per usuari {data.get('uid', '')}: {str(e)}")
                avatar_metadata = None

        return cls(
            uid=data.get('uid', ''),
            username=data.get('username', ''),
            email=data.get('email', ''),
            avatar_metadata= avatar_metadata,
            language=data.get('language', 'ca'),
            favourite_refuges=data.get('favourite_refuges', []),
            visited_refuges=data.get('visited_refuges', []),
            uploaded_photos_keys=data.get('uploaded_photos_keys', []),
            num_shared_experiences=data.get('num_shared_experiences', 0),
            num_renovated_refuges=data.get('num_renovated_refuges', 0),
            created_at=data.get('created_at', '')
        )
    
    def __str__(self) -> str:
        """Representació textual de l'usuari"""
        return f"User(uid={self.uid}, username={self.username}, email={self.email})"
    
    def __repr__(self) -> str:
        """Representació detallada de l'usuari"""
        return self.__str__()