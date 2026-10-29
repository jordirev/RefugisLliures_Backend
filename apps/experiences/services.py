"""
Escriptures d'`experiences` (substitueixen l'`ExperienceController` de Firestore; docs/design/postgres-schema.md §2.9,
§2.15).

Excepcions de domini (cap tupla). La **propietat es comprova aquí** (només el creador o un admin editen i esborren) a
més de la RLS, que ho reforça a la BD. La mitjana de condició del refugi la manté el *trigger* `SECURITY DEFINER` de la
migració (mai es calcula aquí): `INSERT` vota, un `UPDATE` de `condition` ajusta el vot, i esborrar no toca res. Els
mitjans d'una experiència cauen per la FK `ON DELETE CASCADE`; els seus fitxers d'R2 s'esborren dins la mateixa
transacció (si R2 falla es desfà l'esborrat, com `apps.refuges.services.delete_media`).
"""
import logging
from typing import Optional

from django.db import IntegrityError, connection, transaction

from apps.uploads import r2_media_service
from apps.core.db_functions import TransactionNow
from apps.core.rls import system_context
from apps.refuges import selectors as refuge_selectors
from apps.refuges.models import RefugeMedia

from . import selectors
from .models import Experience

logger = logging.getLogger(__name__)


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és UUID)."""


class ExperienceNotFound(Exception):
    """L'experiència no existeix (inclou un ID que no és UUID)."""


class NotOwner(Exception):
    """Qui ho demana no és el creador ni admin."""


class MediaStorageError(Exception):
    """R2 no ha pogut esborrar un fitxer de l'experiència: es desfà l'esborrat de les files."""


def _insert_checked(**fields) -> Experience:
    """
    `INSERT` amb les FK comprovades **ara** i no al `COMMIT`. Les FK són `DEFERRABLE INITIALLY DEFERRED` (§6.3): si el
    refugi s'esborra entre la lectura i l'`INSERT` (o el `COMMIT` d'`ATOMIC_REQUESTS`), l'error sortiria en tancar la
    transacció, fora de la vista, i seria un 500. Amb `SET CONSTRAINTS ALL IMMEDIATE` dins d'un *savepoint*
    l'`IntegrityError` surt aquí i es converteix en 404. Qualsevol altra violació es propaga.
    """
    try:
        with transaction.atomic():
            obj = Experience.objects.create(**fields)
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
    except IntegrityError as exc:
        diag = getattr(exc.__cause__, 'diag', None)
        if getattr(diag, 'constraint_name', None) == 'experiences_refuge_id_fk':
            raise RefugeNotFound('Refuge not found') from exc
        raise
    return obj


def create_experience(*, refuge_id, creator_uid: str, comment: str, condition: int) -> Experience:
    """Crea l'experiència (existència del refugi + `INSERT … RETURNING`); el *trigger* vota a la mitjana del refugi."""
    pk = selectors.parse_id(refuge_id)
    if pk is None or not refuge_selectors.refuge_exists(pk):
        raise RefugeNotFound('Refuge not found')
    return _insert_checked(refuge_id=pk, creator_id=creator_uid, comment=comment, condition=condition)


def _check_owner(experience: Experience, actor_uid: Optional[str], is_admin: bool) -> None:
    if not is_admin and (not actor_uid or experience.creator_id != actor_uid):
        raise NotOwner('No ets el creador')


def update_experience(*, experience_id, actor_uid: Optional[str], is_admin: bool = False,
                      comment: Optional[str] = None, condition: Optional[int] = None) -> Experience:
    """
    Edita el comentari i/o la condició (`None` = no tocar; `0` és un valor vàlid). Sempre actualitza `modified_at`
    (rellotge de la BD). Si canvia la condició, el *trigger* ajusta la mitjana del refugi.
    """
    experience = selectors.get_experience(experience_id)
    if experience is None:
        raise ExperienceNotFound('Experience not found')
    _check_owner(experience, actor_uid, is_admin)
    changes = {'modified_at': TransactionNow()}
    if comment is not None:
        changes['comment'] = comment
    if condition is not None:
        changes['condition'] = condition
    if not Experience.objects.filter(pk=experience.pk).update(**changes):       # esborrada alhora
        raise ExperienceNotFound('Experience not found')
    if comment is not None:
        experience.comment = comment
    if condition is not None:
        experience.condition = condition
    experience.refresh_from_db(fields=['modified_at'])
    return experience


def delete_experience(*, experience_id, actor_uid: Optional[str], is_admin: bool = False,
                      media_service=None) -> None:
    """
    Esborra l'experiència (un sol `DELETE`: la BD cascadeja els mitjans i els intents de pujada) i els fitxers d'R2 dels
    seus mitjans (clau i miniatura), també els pujats per un altre (un admin). No toca la mitjana del refugi.

    Les claus es llegeixen amb `system_context()`: un mitjà amagat d'un altre no és visible per al creador, però
    la cascada també l'esborra i el fitxer no pot quedar orfe (RGPD). Si R2 no esborra algun fitxer principal
    (`delete_files` informa de `failed` o llança), es desfà l'esborrat (`MediaStorageError`); una miniatura que falla
    només queda al log.
    """
    experience = selectors.get_experience(experience_id)
    if experience is None:
        raise ExperienceNotFound('Experience not found')
    _check_owner(experience, actor_uid, is_admin)

    service = media_service or r2_media_service.get_refugi_media_service()
    with transaction.atomic():
        # Es bloqueja l'experiència abans de llegir les claus: una confirmació concurrent insereix un mitjà amb una FK
        # cap a aquesta fila (necessita `KEY SHARE`), de manera que no pot colar-s'hi un mitjà que la cascada esborri
        # sense que se n'esborri el fitxer d'R2 (orfe amb dades personals).
        if Experience.objects.select_for_update().filter(pk=experience.pk).first() is None:
            raise ExperienceNotFound('Experience not found')
        with system_context():
            rows = list(RefugeMedia.objects.filter(experience_id=experience.pk).values_list('key', 'thumb_key'))
        keys = [key for key, _ in rows]
        thumbs = [thumb for _, thumb in rows if thumb]
        if not Experience.objects.filter(pk=experience.pk).delete()[0]:          # esborrada alhora
            raise ExperienceNotFound('Experience not found')
        if keys:
            try:
                result = service.delete_files(keys)
            except Exception as exc:
                raise MediaStorageError('R2 ha fallat en esborrar els fitxers') from exc   # desfà l'esborrat
            if result.get('failed'):
                raise MediaStorageError('R2 no ha esborrat tots els fitxers')              # desfà l'esborrat

    # Miniatures: si falla només queden fitxers orfes.
    if thumbs:
        try:
            failed = service.delete_files(thumbs).get('failed')
        except Exception:
            failed = thumbs
        if failed:
            logger.warning('Miniatures òrfenes a R2: %d fitxers', len(failed))
