"""
Escriptures de `refuges` (substitueixen el controller de Firestore).

Només queda l'esborrat d'un mitjà (la pujada viu al chunk 7). Es fa a la mateixa transacció de la petició
(`ATOMIC_REQUESTS`) i amb un `savepoint` propi: si R2 falla, la fila **no** es perd (error 500).
"""
import logging
from typing import Optional

from django.db import transaction

from apps.audit import services as audit
from apps.uploads import r2_media_service

from . import selectors
from .models import RefugeMedia

logger = logging.getLogger(__name__)


class MediaNotFound(Exception):
    """El mitjà no existeix (o no és d'aquest refugi) i qui ho demana és admin."""


class MediaForbidden(Exception):
    """Qui ho demana no és l'autor ni admin (també quan el mitjà no existeix, per no revelar-ne l'existència)."""


class MediaStorageError(Exception):
    """R2 no ha pogut esborrar el fitxer: la fila es conserva."""


def delete_media(*, refuge_id, key: str, actor_uid: Optional[str], is_admin: bool, media_service=None) -> None:
    """
    Esborra un mitjà del refugi: la fila de `refuge_media` i el fitxer (i la miniatura) de R2.

    - No admin + mitjà inexistent → `MediaForbidden` (403, com fins ara); admin + inexistent → `MediaNotFound` (404).
    - No admin i no és l'autor → `MediaForbidden`.
    - `R2MediaService.delete_file` retorna `False` (no llança): es comprova i es desfà l'esborrat de la fila.
    """
    media = selectors.get_media_by_key(refuge_id, key)
    if media is None:
        raise (MediaNotFound if is_admin else MediaForbidden)('Mitjà no trobat')
    if not is_admin and media.creator_id != actor_uid:
        raise MediaForbidden('Només l\'autor del mitjà o un administrador el poden eliminar')

    service = media_service or r2_media_service.get_refugi_media_service()
    with transaction.atomic():
        deleted, _ = RefugeMedia.objects.filter(pk=key).delete()
        if not deleted:                                  # esborrat concurrent
            raise MediaNotFound('Mitjà no trobat')
        try:
            stored = service.delete_file(key)
        except Exception as exc:
            raise MediaStorageError('R2 ha fallat en esborrar el fitxer') from exc    # desfà l'esborrat de la fila
        if not stored:
            raise MediaStorageError('R2 no ha esborrat el fitxer')                    # desfà l'esborrat de la fila

    # Miniatura: si falla només queda un fitxer orfe.
    if media.thumb_key and not service.delete_file(media.thumb_key):
        logger.warning('Miniatura òrfena a R2: %s', media.thumb_key)

    audit.audit_log_service.log(actor_uid, audit.ACTION_MEDIA_DELETE, 'media', key, {'refuge_id': str(refuge_id)})
