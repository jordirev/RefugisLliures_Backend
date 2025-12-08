"""
Model per representar metadades de mitjans (imatges i vídeos) emmagatzemats a R2
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class MediaMetadata:
    """
    Model per representar les metadades d'un mitjà (imatge o vídeo).
    
    Atributs:
        key: Path del fitxer al bucket R2
        url: URL prefirmada per accedir al fitxer
        creator_uid: UID de l'usuari que ha pujat el mitjà
        uploaded_at: Data i hora de pujada (ISO 8601 format)
    """
    key: str
    url: str
    creator_uid: str
    uploaded_at: str  # ISO 8601 format: "2024-12-08T10:30:00Z"
    
    def to_dict(self) -> dict:
        """Converteix les metadades a diccionari"""
        return {
            'key': self.key,
            'url': self.url,
            'creator_uid': self.creator_uid,
            'uploaded_at': self.uploaded_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MediaMetadata':
        """Crea MediaMetadata des d'un diccionari"""
        return cls(
            key=data.get('key', ''),
            url=data.get('url', ''),
            creator_uid=data.get('creator_uid', ''),
            uploaded_at=data.get('uploaded_at', '')
        )
    
    def __str__(self) -> str:
        return f"MediaMetadata(key={self.key}, creator_uid={self.creator_uid}, uploaded_at={self.uploaded_at})"
