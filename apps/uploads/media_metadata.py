"""
Inferència del tipus de mitjà (`image` | `video`) d'una clau d'R2, per a `MediaItemSerializer`.

(Els antics `MediaMetadata`/`RefugeMediaMetadata`, del temps de Firestore, s'han eliminat: la forma pública
d'un mitjà, "MediaItem", la defineix `MediaItemSerializer`.)
"""
from typing import Optional


MEDIA_TYPE_IMAGE = 'image'
MEDIA_TYPE_VIDEO = 'video'

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.webm', '.avi', '.m4v')


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
