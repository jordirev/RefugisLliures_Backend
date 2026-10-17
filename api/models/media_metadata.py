"""
Model per representar metadades de mitjans (imatges i vídeos) emmagatzemats a R2.

Forma pública (contracte d'API, "MediaItem"):
    {key, url, thumb_url, media_type: "image"|"video", width, height, blurhash,
     creator_uid, uploaded_at, taken_at|null, experience_id|null}

Camps interns (només Firestore, mai a la resposta): status, thumb_key, size,
rights_confirmed_at, content_type.

Compatibilitat: els items antics (abans de la feature images) només tenen
creator_uid/uploaded_at/experience_id. Per a ells thumb_url = url, media_type
s'infereix de l'extensió i la resta de camps són null.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


MEDIA_STATUS_VISIBLE = 'visible'
MEDIA_STATUS_HIDDEN = 'hidden_pending_review'
MEDIA_STATUS_REMOVED = 'removed'
MEDIA_STATUSES = (MEDIA_STATUS_VISIBLE, MEDIA_STATUS_HIDDEN, MEDIA_STATUS_REMOVED)

MEDIA_TYPE_IMAGE = 'image'
MEDIA_TYPE_VIDEO = 'video'

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.avi', '.m4v')

# Camps que es desen al map media_metadata de Firestore (clau = key R2)
STORED_FIELDS = (
    'creator_uid', 'uploaded_at', 'taken_at', 'experience_id', 'media_type',
    'content_type', 'width', 'height', 'size', 'thumb_key', 'blurhash', 'status',
    'rights_confirmed_at',
)


def infer_media_type(key: Optional[str], content_type: Optional[str] = None) -> str:
    """Infereix 'image' o 'video' a partir del content type o de l'extensió de la clau."""
    if content_type:
        if content_type.startswith('video/'):
            return MEDIA_TYPE_VIDEO
        if content_type.startswith('image/'):
            return MEDIA_TYPE_IMAGE
    if key and key.lower().endswith(VIDEO_EXTENSIONS):
        return MEDIA_TYPE_VIDEO
    return MEDIA_TYPE_IMAGE


@dataclass
class MediaMetadata:
    """
    Metadades d'un mitjà amb URL prefirmada (MediaItem).
    Utilitzat per avatars, fotos de refugi i fotos d'experiències.
    
    Atributs públics:
        key: Path del fitxer al bucket R2
        url: URL prefirmada (GET, 1 h)
        uploaded_at: Data de pujada (ISO 8601)
        thumb_url: URL prefirmada de la miniatura (o la mateixa url si no n'hi ha)
        media_type: 'image' | 'video'
        width/height: dimensions de la variant publicada
        blurhash: placeholder
        creator_uid: UID de qui l'ha pujat
        taken_at: data de presa (EXIF), només a Firestore
        experience_id: experiència associada
    Atributs interns (no surten a to_dict):
        status, thumb_key, size, rights_confirmed_at, content_type
    """
    key: str
    url: str
    uploaded_at: Optional[str] = None  # ISO 8601 format: "2024-12-08T10:30:00Z"
    creator_uid: Optional[str] = None
    experience_id: Optional[str] = None
    thumb_url: Optional[str] = None
    media_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    blurhash: Optional[str] = None
    taken_at: Optional[str] = None
    # Interns
    status: str = MEDIA_STATUS_VISIBLE
    thumb_key: Optional[str] = None
    size: Optional[int] = None
    rights_confirmed_at: Optional[str] = None
    content_type: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Converteix les metadades a diccionari amb la forma pública MediaItem"""
        return {
            'key': self.key,
            'url': self.url,
            'thumb_url': self.thumb_url or self.url,
            'media_type': self.media_type or infer_media_type(self.key, self.content_type),
            'width': self.width,
            'height': self.height,
            'blurhash': self.blurhash,
            'creator_uid': self.creator_uid,
            'uploaded_at': self.uploaded_at,
            'taken_at': self.taken_at,
            'experience_id': self.experience_id,
        }

    def to_firestore_dict(self) -> dict:
        """Entrada del map media_metadata (sense URLs ni key)"""
        data = {
            'creator_uid': self.creator_uid,
            'uploaded_at': self.uploaded_at,
            'experience_id': self.experience_id,
        }
        for field_name in ('taken_at', 'media_type', 'content_type', 'width', 'height', 'size',
                           'thumb_key', 'blurhash', 'rights_confirmed_at'):
            value = getattr(self, field_name)
            if value is not None:
                data[field_name] = value
        data['status'] = self.status or MEDIA_STATUS_VISIBLE
        return data

    def is_visible_to(self, viewer_uid: Optional[str] = None, is_admin: bool = False) -> bool:
        """Els items amb status ≠ visible només els veu el seu autor o un admin"""
        if (self.status or MEDIA_STATUS_VISIBLE) == MEDIA_STATUS_VISIBLE:
            return True
        if is_admin:
            return True
        return bool(viewer_uid) and viewer_uid == self.creator_uid

    @classmethod
    def from_stored(cls, key: str, stored: Optional[Dict[str, Any]], url: str,
                    thumb_url: Optional[str] = None) -> 'MediaMetadata':
        """Crea l'item a partir de l'entrada desada a Firestore i les URLs ja prefirmades"""
        stored = stored or {}
        return cls(
            key=key,
            url=url,
            uploaded_at=stored.get('uploaded_at', ''),
            creator_uid=stored.get('creator_uid', ''),
            experience_id=stored.get('experience_id'),
            thumb_url=thumb_url or url,
            media_type=stored.get('media_type') or infer_media_type(key, stored.get('content_type')),
            width=stored.get('width'),
            height=stored.get('height'),
            blurhash=stored.get('blurhash'),
            taken_at=stored.get('taken_at'),
            status=stored.get('status') or MEDIA_STATUS_VISIBLE,
            thumb_key=stored.get('thumb_key'),
            size=stored.get('size'),
            rights_confirmed_at=stored.get('rights_confirmed_at'),
            content_type=stored.get('content_type'),
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MediaMetadata':
        """Crea MediaMetadata des d'un diccionari (forma pública o desada)"""
        key = data.get('key', '')
        url = data.get('url', '')
        return cls.from_stored(key, data, url, data.get('thumb_url'))
    
    def __str__(self) -> str:
        return f"MediaMetadata(key={self.key}, uploaded_at={self.uploaded_at})"


@dataclass
class RefugeMediaMetadata(MediaMetadata):
    """
    Metadades d'un mitjà d'un refugi (o d'una experiència, que es desa al refugi).
    Mateixa forma que MediaMetadata; es manté com a classe per compatibilitat.
    """
    
    def __str__(self) -> str:
        return f"RefugeMediaMetadata(key={self.key}, creator_uid={self.creator_uid})"
