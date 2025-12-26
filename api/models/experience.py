"""
Model d'experiència per a l'aplicació RefugisLliures

Les metadades de les imatges e guaden al refugi que correspon a l'experiència.
D'aquesta manera, no dupliquem informació a Firestore i només ens guardem les keys de les imatges a l'experiència per poder recuperar-les.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from asyncio.log import logger
from api.services import r2_media_service
from .media_metadata import MediaMetadata


@dataclass
class Experience:
    """Model per representar una experiència d'un usuari en un refugi"""
    id: str
    refuge_id: str
    creator_uid: str
    modified_at: str  # ISO 8601 format
    comment: str
    media_keys: Optional[List[str]] = field(default_factory=list)  # Keys de les fotos guardades a Firestore (No es mostren a la resposta)
    images_metadata: Optional[List[MediaMetadata]] = field(default_factory=list)  # Keys i Urls prefirmades (No es guarden a Firestore)
    
    def to_dict(self) -> dict:
        """Converteix l'experiència a diccionari"""

        # Nomes guardem a firestore les keys de les imatges
        media_keys = [img.key for img in self.images_metadata] if self.images_metadata else self.media_keys

        return {
            'id': self.id,
            'refuge_id': self.refuge_id,
            'creator_uid': self.creator_uid,
            'modified_at': self.modified_at,
            'comment': self.comment,
            'media_keys': media_keys,
            'images_metadata': [img.to_dict() for img in self.images_metadata] if self.images_metadata else []
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Experience':
        """Crea una experiència des d'un diccionari"""
        
        # Generem les urls prefirmades per les imatges
        images_metadata = []
        if 'media_keys' in data and data['media_keys']:
            try:
                media_service = r2_media_service.get_refugi_media_service()
                for key in data['media_keys']:
                    url = media_service.generate_presigned_url(key)
                    images_metadata.append(MediaMetadata(key=key, url=url, uploaded_at=None))
            except Exception as e:
                logger.warning(f"Error generant MediaMetadata per experiència {data.get('id', '')}: {str(e)}")
                images_metadata = []
        
        return cls(
            id=data.get('id', ''),
            refuge_id=data.get('refuge_id', ''),
            creator_uid=data.get('creator_uid', ''),
            modified_at=data.get('modified_at', ''),
            comment=data.get('comment', ''),
            media_keys=data.get('media_keys', []),
            images_metadata=images_metadata
        )
