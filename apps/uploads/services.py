"""
Pujada directa de mitjans (substitueix el `MediaUploadController` i l'`UploadIntentDAO` de Firestore; docs/design/
postgres-schema.md §2.19).

Flux (el pipeline d'imatge no canvia):
    1. `create_upload_intents`  -> URL PUT prefirmades a `quarantine/{upload_id}` (600 s) i una fila per fitxer a
       `moderation.upload_intents`;
    2. el client puja directament a R2;
    3. `confirm_upload_intents` -> descarrega de `quarantine/`, valida (mida i tipus real), neteja l'EXIF/GPS, recodifica,
       passa la moderació per hash, publica amb clau UUID i esborra `quarantine/`. El mitjà es publica a
       `refuges.refuge_media` (target `refuge`/`experience`) o a `users.user_avatars` (target `avatar`).

Única via de pujada: `process_and_publish` és el processament compartit (neteja de metadades, compressió, tipus real,
moderació). Una fallada de la BD en publicar (`INSERT`) desfà els fitxers d'R2 i l'intent queda `failed:
processing_error` (no és un 500). La hash-blocklist, les denúncies automàtiques i els avisos de moderació continuen a
Firestore fins al chunk 9.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.db import connection, transaction
from django.db.models import BooleanField, ExpressionWrapper, Q

from apps.audit import services as audit
from apps.uploads import r2_media_service
from apps.uploads.image_processing_service import (
    REASON_MISSING_OBJECT, REASON_MODERATION_BLOCKED, REASON_PROCESSING_ERROR, REASON_TOO_LARGE,
    VIDEO_MAX_BYTES, MediaRejected, ProcessedMedia, image_processing_service, kind_for_content_type,
    max_bytes_for_kind, normalize_content_type)
from apps.moderation.moderation_service import ModerationInput, ModerationService
from apps.core.timezone_utils import get_madrid_timezone
from apps.accounts import selectors as account_selectors
from apps.accounts import services as account_services
from apps.accounts.serializers import avatar_to_dict
from apps.core.db_functions import TransactionNow
from apps.core.rls import system_context
from apps.experiences import selectors as experience_selectors
from apps.moderation import services as moderation_services
from apps.refuges import selectors as refuge_selectors
from apps.refuges.models import RefugeMedia
from apps.refuges.serializers import media_to_dict

from .models import UploadIntent, UploadStatus, UploadTarget

logger = logging.getLogger(__name__)

INTENT_EXPIRES_IN = 600         # segons de validesa de la URL PUT
PRESIGN_SECONDS = 3600          # URLs prefirmades dels mitjans publicats
# Decisió del PO (27/10): un usuari pot tenir com a molt 40 intents `pending` sense caducar (un per fitxer). Els
# `confirmed`/`failed` no compten; els abandonats deixen de comptar quan caduquen (1 dia). No és un *rate limit*.
MAX_PENDING_INTENTS = 40


class RefugeNotFound(Exception):
    """El refugi no existeix (inclou un ID que no és UUID)."""


class ExperienceNotFound(Exception):
    """L'experiència no existeix (inclou un ID que no és UUID)."""


class NotOwner(Exception):
    """L'experiència no és de qui ho demana i no és admin."""


class InvalidRefuge(Exception):
    """El `refuge_id` del cos no és el de l'experiència."""


class TooManyPendingUploads(Exception):
    """Els intents nous superarien `MAX_PENDING_INTENTS` pendents per a l'usuari."""


# ---------------------------------------------------------------------------
# 1. Intents
# ---------------------------------------------------------------------------

def _new_ids(count: int) -> List[uuid.UUID]:
    """`count` UUID v7 de la BD (la mateixa funció que el `DEFAULT` de la PK): cal conèixer-los abans de signar la URL."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT uuidv7() FROM generate_series(1, %s)', [count])
        return [row[0] for row in cursor.fetchall()]


def _check_pending_quota(uid: str, new_count: int) -> None:
    """
    Quota d'intents pendents (`MAX_PENDING_INTENTS`). El bloqueig assessor per usuari serialitza dues peticions
    simultànies del mateix usuari (sense ell, totes dues comptarien abans d'inserir i la superarien); s'allibera al
    final de la transacció de la petició (compatible amb PgBouncer en mode transacció).
    """
    with connection.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', [f'upload-intents:{uid}'])
    pending = UploadIntent.objects.filter(
        user_id=uid, status=UploadStatus.PENDING, expire_at__gt=TransactionNow()).count()
    if pending + new_count > MAX_PENDING_INTENTS:
        raise TooManyPendingUploads()


def create_upload_intents(*, uid: str, target: str, files: List[Dict[str, Any]], refuge_id=None, experience_id=None,
                          is_admin: bool = False) -> Dict[str, Any]:
    """
    Crea un intent (i una URL PUT prefirmada) per fitxer: `{'uploads': [{upload_id, put_url, headers, expires_in}]}`.

    - `experience`: l'experiència existeix (`ExperienceNotFound`), el `refuge_id` del cos (si hi és) és el seu
      (`InvalidRefuge`) i és del sol·licitant o aquest és admin (`NotOwner`); el refugi es deriva de l'experiència.
    - `refuge`: el refugi existeix (`RefugeNotFound`). `avatar`: sense refugi ni experiència.
    - Quota: com a molt `MAX_PENDING_INTENTS` intents pendents sense caducar per usuari (`TooManyPendingUploads`).
    Tot o res: primer es signen totes les URL i després s'insereixen totes les files en un sol `INSERT`.
    `files`: `[{content_type, size}]` ja validats pel serializer.
    """
    refuge_pk = experience_pk = None
    if target == UploadTarget.EXPERIENCE:
        experience = experience_selectors.get_experience(experience_id)
        if experience is None:
            raise ExperienceNotFound('Experience not found')
        if refuge_id and str(experience_selectors.parse_id(refuge_id)) != str(experience.refuge_id):
            raise InvalidRefuge("refuge_id no correspon a l'experiència")
        if not is_admin and experience.creator_id != uid:
            raise NotOwner('No ets el creador')
        refuge_pk, experience_pk = experience.refuge_id, experience.pk
    elif target == UploadTarget.REFUGE:
        refuge_pk = refuge_selectors.parse_refuge_id(refuge_id)
        if refuge_pk is None or not refuge_selectors.refuge_exists(refuge_pk):
            raise RefugeNotFound('Refugi not found')

    _check_pending_quota(uid, len(files))
    service = r2_media_service.get_refugi_media_service()
    ids = _new_ids(len(files))
    intents, uploads = [], []
    for upload_id, spec in zip(ids, files):
        content_type = normalize_content_type(spec['content_type'])
        size = int(spec['size'])
        quarantine = r2_media_service.quarantine_key(str(upload_id))
        put_url = service.generate_presigned_put_url(quarantine, content_type, size, INTENT_EXPIRES_IN)
        intents.append(UploadIntent(
            id=upload_id, user_id=uid, target=target, content_type=content_type, size=size,
            quarantine_key=quarantine, refuge_id=refuge_pk, experience_id=experience_pk,
            rights_confirmed_at=TransactionNow()))
        uploads.append({'upload_id': str(upload_id), 'put_url': put_url,
                        'headers': {'Content-Type': content_type}, 'expires_in': INTENT_EXPIRES_IN})
    UploadIntent.objects.bulk_create(intents)

    audit.audit_log_service.log(uid, audit.ACTION_UPLOAD_INTENT, target,
                                str(experience_pk or refuge_pk or uid),
                                {'count': len(intents), 'upload_ids': [u['upload_id'] for u in uploads]})
    return {'uploads': uploads}


# ---------------------------------------------------------------------------
# 2. Confirmació
# ---------------------------------------------------------------------------

def confirm_upload_intents(*, uid: str, upload_ids: List[str]) -> Dict[str, Any]:
    """
    Processa els fitxers pujats a `quarantine/`: `{'uploaded': [MediaItem], 'failed': [{upload_id, reason}]}`.
    Els ids repetits es processen una sola vegada. Un intent aliè, inexistent, caducat o d'id que no és UUID és
    `missing_object`; una confirmació repetida retorna el mateix `MediaItem` (idempotent).
    """
    uploaded, failed = [], []
    _lock_intents(uid, upload_ids)
    seen = set()
    for upload_id in upload_ids:
        # Un UUID es pot escriure de moltes maneres (majúscules, sense guions, `{...}`, `urn:uuid:`): es deduplica pel
        # valor canònic perquè el mateix intent no es processi (ni es retorni) més d'una vegada.
        canonical = experience_selectors.parse_id(upload_id) or upload_id
        if canonical in seen:
            continue
        seen.add(canonical)
        item, reason = _confirm_one(uid, upload_id)
        if item is not None:
            uploaded.append(item)
        else:
            failed.append({'upload_id': upload_id, 'reason': reason or REASON_PROCESSING_ERROR})
    return {'uploaded': uploaded, 'failed': failed}


def _lock_intents(uid: str, upload_ids: List[str]) -> None:
    """
    Bloqueja (`FOR UPDATE`) **tots** els intents de la petició d'una sola vegada i **en ordre de PK**. Sense això, dues
    confirmacions simultànies de `[a, b]` i `[b, a]` agafarien els bloquejos en ordre invers (`_get_intent` va un a un,
    en l'ordre del client) i es produiria un *deadlock*. Els bloquejos duren fins al final de la transacció.
    """
    pks = {pk for pk in map(experience_selectors.parse_id, upload_ids) if pk is not None}
    if pks:
        list(UploadIntent.objects.select_for_update().filter(pk__in=pks, user_id=uid).order_by('pk')
             .values_list('pk', flat=True))


def _get_intent(uid: str, upload_id: str) -> Optional[UploadIntent]:
    pk = experience_selectors.parse_id(upload_id)
    if pk is None:
        return None
    expired = ExpressionWrapper(Q(expire_at__lt=TransactionNow()), output_field=BooleanField())
    # `FOR UPDATE`: dues confirmacions simultànies del mateix intent es serialitzen (la segona veu `confirmed` i és
    # idempotent) en lloc de publicar dos mitjans. Dins `ATOMIC_REQUESTS` el bloqueig dura fins al final de la petició.
    return (UploadIntent.objects.select_for_update().filter(pk=pk, user_id=uid).annotate(is_expired=expired)
            .order_by().first())


def _mark_failed(intent: UploadIntent, reason: str) -> None:
    UploadIntent.objects.filter(pk=intent.pk).update(status=UploadStatus.FAILED, failure_reason=reason)


def _mark_confirmed(intent: UploadIntent, result_key: str) -> None:
    UploadIntent.objects.filter(pk=intent.pk).update(status=UploadStatus.CONFIRMED, result_key=result_key)


def _confirm_one(uid: str, upload_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    intent = _get_intent(uid, upload_id)
    if intent is None:
        return None, REASON_MISSING_OBJECT

    # Idempotència: un reintent retorna el resultat anterior
    if intent.status == UploadStatus.CONFIRMED:
        item = _existing_item(intent)
        return (item, None) if item else (None, REASON_MISSING_OBJECT)
    if intent.status == UploadStatus.FAILED:
        return None, intent.failure_reason or REASON_PROCESSING_ERROR
    if intent.is_expired:
        return None, REASON_MISSING_OBJECT

    service = r2_media_service.get_refugi_media_service()
    q_key = intent.quarantine_key
    head = service.head_object(q_key)
    if head is None:
        return None, REASON_MISSING_OBJECT       # el client encara pot repetir el PUT mentre l'intent no caduqui

    kind = kind_for_content_type(intent.content_type)
    limit = max_bytes_for_kind(kind) if kind else VIDEO_MAX_BYTES
    if head['size'] > limit:
        _discard_quarantine(service, q_key)
        _mark_failed(intent, REASON_TOO_LARGE)
        return None, REASON_TOO_LARGE

    data = service.get_object_bytes(q_key, max_bytes=limit)
    if data is None:
        return None, REASON_MISSING_OBJECT
    if len(data) > limit:
        _discard_quarantine(service, q_key)
        _mark_failed(intent, REASON_TOO_LARGE)
        return None, REASON_TOO_LARGE

    item, reason = process_and_publish(
        data=data, declared_content_type=intent.content_type, target=intent.target, uid=uid,
        refuge_id=intent.refuge_id, experience_id=intent.experience_id,
        rights_confirmed_at=intent.rights_confirmed_at, quarantine_key=q_key, upload_id=str(intent.pk))

    if item is None:
        if reason != REASON_MODERATION_BLOCKED:      # l'evidència ja s'ha mogut a moderation-hold/
            _discard_quarantine(service, q_key)
        _mark_failed(intent, reason or REASON_PROCESSING_ERROR)
        return None, reason

    _discard_quarantine(service, q_key)
    _mark_confirmed(intent, item['key'])
    audit.audit_log_service.log(uid, audit.ACTION_UPLOAD_CONFIRM, intent.target, item['key'],
                                {'upload_id': str(intent.pk),
                                 'refuge_id': str(intent.refuge_id) if intent.refuge_id else None,
                                 'experience_id': str(intent.experience_id) if intent.experience_id else None})
    return item, None


def _presigner(service):
    return lambda key: service.generate_presigned_url(key, PRESIGN_SECONDS)


def _existing_item(intent: UploadIntent) -> Optional[Dict[str, Any]]:
    """Reconstrueix el `MediaItem` d'un intent ja confirmat (`None` si el mitjà s'ha esborrat o substituït)."""
    if not intent.result_key:
        return None
    if intent.target == UploadTarget.AVATAR:
        avatar = account_selectors.get_avatar(intent.user_id)
        if avatar and avatar.key == intent.result_key:
            return avatar_to_dict(avatar, intent.user_id, _presigner(r2_media_service.get_user_avatar_service()))
        return None
    media = RefugeMedia.objects.filter(pk=intent.result_key).first()
    if media is None:
        return None
    return media_to_dict(media, _presigner(r2_media_service.get_refugi_media_service()))


def _discard_quarantine(service, q_key: Optional[str]) -> None:
    if q_key and not service.delete_file(q_key):
        logger.warning("No s'ha pogut esborrar %s; el lifecycle de R2 l'esborrarà en 1 dia", q_key)


# ---------------------------------------------------------------------------
# 3. Processament + publicació
# ---------------------------------------------------------------------------

def process_and_publish(*, data: bytes, declared_content_type: Optional[str], target: str, uid: str, refuge_id=None,
                        experience_id=None, rights_confirmed_at=None, quarantine_key: Optional[str] = None,
                        upload_id: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Valida, processa, modera i publica un fitxer: `(MediaItem, None)` o `(None, reason)`."""
    try:
        processed = image_processing_service.process(data, declared_content_type, avatar=(target == UploadTarget.AVATAR))
    except MediaRejected as exc:
        logger.info("Fitxer rebutjat (%s) per l'usuari %s: %s", exc.reason, uid, exc)
        return None, exc.reason
    except Exception:
        logger.exception('Error inesperat processant el fitxer')
        return None, REASON_PROCESSING_ERROR

    try:
        moderation = ModerationService().check(ModerationInput(
            sha256=processed.sha256, phash=processed.phash, media_type=processed.media_type))
    except Exception:
        logger.exception('Error a la moderació automàtica (fail-closed)')
        return None, REASON_PROCESSING_ERROR

    if moderation.blocked:
        _handle_moderation_block(uid, data, declared_content_type, target, refuge_id, quarantine_key, moderation,
                                 upload_id)
        return None, REASON_MODERATION_BLOCKED

    if target == UploadTarget.AVATAR:
        return _publish_avatar(uid, processed)
    return _publish_refuge_media(uid, processed, refuge_id, experience_id, rights_confirmed_at)


def _taken_at(value: Optional[str]) -> Optional[datetime]:
    """`taken_at` ISO 8601 del processament -> `datetime` amb zona (una data sense desplaçament és hora de Madrid)."""
    if not value:
        return None
    taken = datetime.fromisoformat(value)
    return taken if taken.tzinfo else taken.replace(tzinfo=get_madrid_timezone())


def _publish_refuge_media(uid: str, processed: ProcessedMedia, refuge_id, experience_id, rights_confirmed_at):
    service = r2_media_service.get_refugi_media_service()
    media_id = str(uuid.uuid4())
    key = service.build_media_key(str(refuge_id), processed.extension, media_id=media_id)
    thumb_key = (service.build_media_key(str(refuge_id), '.webp', suffix='_thumb', media_id=media_id)
                 if processed.thumb_bytes else None)
    written: List[str] = []

    try:
        service.put_bytes(key, processed.main_bytes, processed.content_type)
        written.append(key)
        if thumb_key:
            service.put_bytes(thumb_key, processed.thumb_bytes, 'image/webp')
            written.append(thumb_key)
    except Exception:
        logger.exception('Error pujant el mitjà processat')
        _rollback_files(service, written)
        return None, REASON_PROCESSING_ERROR

    try:
        # Savepoint: una fallada de la BD (`INSERT`, FK o RLS) no trenca la transacció de la petició. Les FK són
        # diferibles: es comproven ara perquè un refugi o experiència esborrats alhora siguin un error d'aquí.
        with transaction.atomic():
            media = RefugeMedia.objects.create(
                key=key, refuge_id=refuge_id, creator_id=uid, experience_id=experience_id,
                media_type=processed.media_type, content_type=processed.content_type, width=processed.width,
                height=processed.height, size_bytes=processed.size, thumb_key=thumb_key, blurhash=processed.blurhash,
                taken_at=_taken_at(processed.taken_at), rights_confirmed_at=rights_confirmed_at)
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
    except Exception:
        logger.exception('Error desant el mitjà publicat a PostgreSQL')
        _rollback_files(service, written)
        return None, REASON_PROCESSING_ERROR

    return media_to_dict(media, _presigner(service)), None


def _publish_avatar(uid: str, processed: ProcessedMedia):
    old = account_selectors.get_avatar(uid)
    old_key = old.key if old else None
    old_thumb = old.thumb_key if old else None

    service = r2_media_service.get_user_avatar_service()
    key = service.build_media_key(uid, processed.extension)
    try:
        service.put_bytes(key, processed.main_bytes, processed.content_type)
    except Exception:
        logger.exception("Error pujant l'avatar processat")
        return None, REASON_PROCESSING_ERROR

    metadata = {                                    # `uploaded_at` el posa la BD (`update_avatar_metadata` l'hi torna)
        'key': key, 'width': processed.width, 'height': processed.height, 'blurhash': processed.blurhash,
        'size': processed.size, 'content_type': processed.content_type,
    }
    try:
        stored = account_services.update_avatar_metadata(uid, metadata)
    except Exception:
        logger.exception("Error desant l'avatar a PostgreSQL")
        stored = False
    if not stored:
        _rollback_files(service, [key])
        return None, REASON_PROCESSING_ERROR

    # L'avatar antic s'esborra NOMÉS després que el nou s'hagi desat bé
    for stale in (old_key, old_thumb):
        if stale and stale != key and not service.delete_file(stale):
            logger.warning("Avatar antic orfe a R2 (no s'ha pogut esborrar): %s", stale)

    audit.audit_log_service.log(uid, audit.ACTION_AVATAR_UPLOAD, 'avatar', key)
    return avatar_to_dict(metadata, uid, _presigner(service)), None


def _rollback_files(service, keys: List[str]) -> None:
    for key in keys:
        if not service.delete_file(key):
            logger.error('Rollback incomplet: fitxer orfe a R2 %s', key)


# ---------------------------------------------------------------------------
# Moderació automàtica: coincidència amb la llista de hashes (PostgreSQL, `apps.moderation`)
# ---------------------------------------------------------------------------

def _handle_moderation_block(uid: str, data: bytes, declared_content_type: Optional[str], target: str, refuge_id,
                             quarantine_key: Optional[str], moderation, upload_id: Optional[str]) -> None:
    """
    No es publica res. L'evidència es conserva a `moderation-hold/<upload_id>` (accés restringit; la clau no porta
    l'UID: les files `legal_hold` es conserven anonimitzades, D41), es bloqueja l'usuari i es crea la denúncia
    `child_sexual_abuse` d'alta prioritat amb `legal_hold`, l'avís de moderació i l'auditoria
    (`moderation_services.register_upload_block`). Una fallada en desar-ho es registra i no trenca la confirmació.
    """
    upload_id = upload_id or str(uuid.uuid4())
    hold_key = r2_media_service.moderation_hold_key(upload_id)
    service = r2_media_service.get_refugi_media_service()
    try:
        if quarantine_key:
            if not service.move_object(quarantine_key, hold_key):
                logger.error("No s'ha pogut moure l'evidència %s a %s", quarantine_key, hold_key)
        else:
            service.put_bytes(hold_key, data, normalize_content_type(declared_content_type) or 'application/octet-stream')
    except Exception:
        logger.exception("Error desant l'evidència de moderació")

    account_services.set_blocked(uid, True, reason='moderation_hash_match')
    try:
        with transaction.atomic():
            moderation_services.register_upload_block(
                uid=uid, refuge_id=refuge_id, hold_key=hold_key, upload_id=upload_id, provider=moderation.provider,
                match_type=moderation.match_type, category=moderation.category)
    except Exception:
        logger.exception("Error desant la denúncia automàtica i l'avís de la pujada bloquejada")


# ---------------------------------------------------------------------------
# Purga (job horari)
# ---------------------------------------------------------------------------

# `FOR UPDATE SKIP LOCKED`: dues execucions del job alhora (o una confirmació en curs d'un intent caducat) no
# s'esperen ni es trepitgen; l'índex `(expire_at)` serveix l'`ORDER BY ... LIMIT` (EXPLAIN verificat).
PURGE_SQL = ('DELETE FROM moderation.upload_intents WHERE id IN ('
             'SELECT id FROM moderation.upload_intents WHERE expire_at < now() ORDER BY expire_at LIMIT %s '
             'FOR UPDATE SKIP LOCKED)')


def purge_expired_intents(batch_size: int = 1000) -> int:
    """
    Esborra els intents caducats (`expire_at < now()`, qualsevol estat) en lots de `batch_size` fins que no en queden
    (§8.3), cada lot a la seva transacció amb `system_context()` (no hi ha usuari: és un job). No toca R2: el lifecycle de
    `quarantine/` ja l'esborra al cap d'1 dia. Retorna el nombre d'intents esborrats.
    """
    total = 0
    while True:
        with system_context():
            with connection.cursor() as cursor:
                cursor.execute(PURGE_SQL, [batch_size])
                deleted = cursor.rowcount
        total += deleted
        if deleted < batch_size:
            return total
