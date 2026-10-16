"""
Model d'usuari per a l'aplicació RefugisLliures
"""
import logging
from dataclasses import dataclass
from typing import Optional, List

from api.services import r2_media_service
from .media_metadata import MediaMetadata

logger = logging.getLogger(__name__)

# Edat mínima per usar l'app (RGPD art. 8 / LOPDGDD art. 7 → 14; l'app exigeix 16)
AGE_THRESHOLD = 16


@dataclass
class User:
    """Model per representar un usuari"""
    uid: str
    username: str
    avatar_metadata: MediaMetadata = None  # Metadades amb URLs prefirmades (generades dinàmicament) en forma MediaItem
    language: str = 'ca'
    favourite_refuges: Optional[list] = None # Llista d'IDs de refugis preferits
    visited_refuges: Optional[list] = None # Llista d'IDs de refugis visitats
    uploaded_photos_keys: Optional[List[str]] = None # Llista de keys de fotos pujades
    num_shared_experiences: int = 0
    num_renovated_refuges: int = 0
    created_at: str = ''
    # Edat: NOMÉS es desa quan s'ha confirmat i el llindar (minimització, mai la data de naixement)
    age_confirmed_at: Optional[str] = None
    age_threshold: Optional[int] = None
    # Moderació
    moderation_strikes: int = 0
    is_blocked: bool = False

    def __post_init__(self):
        """Validacions després de la inicialització"""
        if not self.uid:
            raise ValueError("UID és requerit")
    
    @property
    def age_confirmed(self) -> bool:
        return bool(self.age_confirmed_at)

    def to_dict(self) -> dict:
        """Converteix l'usuari a diccionari (representació de l'API)"""

        media_metadata = {}
        if self.avatar_metadata:
            media_metadata = {
                'key': self.avatar_metadata.key,
                'uploaded_at': self.avatar_metadata.uploaded_at
            }
            for field_name in ('width', 'height', 'blurhash', 'thumb_key', 'size', 'content_type'):
                value = getattr(self.avatar_metadata, field_name, None)
                if value is not None:
                    media_metadata[field_name] = value

        return {
            'uid': self.uid,
            'username': self.username,
            'media_metadata': media_metadata,
            'avatar_metadata': self.avatar_metadata.to_dict() if self.avatar_metadata else None,
            'language': self.language,
            'favourite_refuges': self.favourite_refuges,
            'visited_refuges': self.visited_refuges,
            'uploaded_photos_keys': self.uploaded_photos_keys,
            'num_shared_experiences': self.num_shared_experiences,
            'num_renovated_refuges': self.num_renovated_refuges,
            'created_at': self.created_at,
            'age_confirmed': self.age_confirmed,
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
                if avatar_metadata is not None and hasattr(avatar_metadata, 'creator_uid'):
                    avatar_metadata.creator_uid = data.get('uid', '')
            except Exception as e:
                logger.warning(f"Error generant MediaMetadata per usuari {data.get('uid', '')}: {str(e)}")
                avatar_metadata = None

        return cls(
            uid=data.get('uid', ''),
            username=data.get('username', ''),
            avatar_metadata= avatar_metadata,
            language=data.get('language', 'ca'),
            favourite_refuges=data.get('favourite_refuges', []),
            visited_refuges=data.get('visited_refuges', []),
            uploaded_photos_keys=data.get('uploaded_photos_keys', []),
            num_shared_experiences=data.get('num_shared_experiences', 0),
            num_renovated_refuges=data.get('num_renovated_refuges', 0),
            created_at=data.get('created_at', ''),
            age_confirmed_at=data.get('age_confirmed_at'),
            age_threshold=data.get('age_threshold'),
            moderation_strikes=int(data.get('moderation_strikes') or 0),
            is_blocked=bool(data.get('is_blocked', False)),
        )
    
    def __str__(self) -> str:
        """Representació textual de l'usuari"""
        return f"User(uid={self.uid}, username={self.username})"
    
    def __repr__(self) -> str:
        """Representació detallada de l'usuari"""
        return self.__str__()
