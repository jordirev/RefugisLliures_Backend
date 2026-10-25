"""
Controller de pujada de mitjans (feature images).

Flux nou (recomanat):
    1. create_upload_intents  → URL PUT prefirmades a quarantine/{upload_id} (600 s)
    2. el client puja directament a R2
    3. confirm_upload_intents → descarrega de quarantine, valida, processa, modera,
       publica a la clau final UUID i esborra quarantine

Única via de pujada: process_and_publish() és el processament compartit (neteja de
metadades, compressió, tipus real, moderació) que crida confirm_upload_intents. Els camins
multipart antics (POST refuges/{id}/media, PATCH users/{uid}/avatar, files[] a experiències)
s'han eliminat.
"""
import logging
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..daos.upload_intent_dao import UploadIntentDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from apps.accounts import selectors as account_selectors
from apps.accounts import services as account_services
from apps.accounts.serializers import avatar_to_dict
from ..daos.experience_dao import ExperienceDAO
from ..daos.media_report_dao import MediaReportDAO
from ..daos.moderation_notice_dao import ModerationNoticeDAO
from ..models.upload_intent import (
    UploadIntent, UPLOAD_TARGET_AVATAR, UPLOAD_TARGET_EXPERIENCE, UPLOAD_TARGET_REFUGE,
    INTENT_STATUS_CONFIRMED, INTENT_STATUS_FAILED,
)
from ..models.media_metadata import MEDIA_STATUS_VISIBLE
from ..models.media_report import (
    MediaReport, build_report_id, REPORT_PRIORITY_HIGH, SYSTEM_REPORTER_UID,
)
from ..models.moderation_notice import NOTICE_ACCOUNT_BLOCKED
from ..services import r2_media_service
from ..services.image_processing_service import (
    image_processing_service, MediaRejected, ProcessedMedia, normalize_content_type,
    kind_for_content_type, max_bytes_for_kind, VIDEO_MAX_BYTES,
    REASON_MISSING_OBJECT, REASON_TOO_LARGE, REASON_INVALID_TYPE,
    REASON_PROCESSING_ERROR, REASON_MODERATION_BLOCKED,
)
from ..services.moderation_service import ModerationService, ModerationInput
from ..services import audit_log_service as audit
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)

# Errors retornats a la vista (la vista tria l'HTTP status)
ERROR_REFUGE_NOT_FOUND = "Refugi not found"
ERROR_EXPERIENCE_NOT_FOUND = "Experience not found"
ERROR_NOT_OWNER = "not_owner"
ERROR_INVALID_PREFIX = "invalid:"

INTENT_EXPIRES_IN = 600              # segons de validesa de la URL PUT
INTENT_RETENTION = timedelta(days=1)  # el document caduca (TTL) igual que quarantine/


class MediaUploadController:
    """Orquestra intents, confirmació i publicació de mitjans"""

    def __init__(self):
        self.intent_dao = UploadIntentDAO()
        self.refugi_dao = RefugiLliureDAO()
        self.accounts = account_services                # escriptures d'usuari a PostgreSQL (D20)
        self.account_selectors = account_selectors
        self.experience_dao = ExperienceDAO()
        self.report_dao = MediaReportDAO()
        self.notice_dao = ModerationNoticeDAO()
        self.refugi_media_service = r2_media_service.get_refugi_media_service()
        self.avatar_service = r2_media_service.get_user_avatar_service()
        self.processor = image_processing_service
        self.moderation_service = ModerationService()

    # ------------------------------------------------------------------
    # 1. Intents
    # ------------------------------------------------------------------

    def create_upload_intents(
        self,
        uid: str,
        target: str,
        files: List[Dict[str, Any]],
        refuge_id: Optional[str] = None,
        experience_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Crea un intent (i una URL PUT prefirmada) per fitxer.

        Args:
            files: [{content_type, size}] ja validats pel serializer

        Returns:
            ({'uploads': [...]}, None) o (None, error)
        """
        try:
            if target == UPLOAD_TARGET_EXPERIENCE:
                experience = self.experience_dao.get_experience_by_id(experience_id)
                if not experience:
                    return None, ERROR_EXPERIENCE_NOT_FOUND
                if refuge_id and refuge_id != experience.refuge_id:
                    return None, f"{ERROR_INVALID_PREFIX} refuge_id no correspon a l'experiència"
                if not is_admin and experience.creator_uid != uid:
                    return None, ERROR_NOT_OWNER
                refuge_id = experience.refuge_id
            elif target == UPLOAD_TARGET_REFUGE:
                if not self.refugi_dao.refugi_exists(refuge_id):
                    return None, ERROR_REFUGE_NOT_FOUND
                experience_id = None
            else:  # avatar
                refuge_id = None
                experience_id = None

            now = get_madrid_now()
            rights_confirmed_at = now.isoformat()
            intents, uploads = [], []
            for spec in files:
                content_type = normalize_content_type(spec['content_type'])
                size = int(spec['size'])
                upload_id = self.intent_dao.new_id()
                q_key = r2_media_service.quarantine_key(upload_id)
                put_url = self.refugi_media_service.generate_presigned_put_url(
                    q_key, content_type, size, INTENT_EXPIRES_IN
                )
                intents.append(UploadIntent(
                    id=upload_id,
                    uid=uid,
                    target=target,
                    content_type=content_type,
                    size=size,
                    quarantine_key=q_key,
                    refuge_id=refuge_id,
                    experience_id=experience_id,
                    rights_confirmed_at=rights_confirmed_at,
                    created_at=now.isoformat(),
                    expire_at=now + INTENT_RETENTION,
                ))
                uploads.append({
                    'upload_id': upload_id,
                    'put_url': put_url,
                    'headers': {'Content-Type': content_type},
                    'expires_in': INTENT_EXPIRES_IN,
                })

            if not self.intent_dao.create_intents(intents):
                return None, "Error intern creant els intents de pujada"

            audit.audit_log_service.log(uid, audit.ACTION_UPLOAD_INTENT, target,
                                        experience_id or refuge_id or uid,
                                        {'count': len(intents), 'upload_ids': [i.id for i in intents]})
            return {'uploads': uploads}, None

        except Exception as e:
            logger.error(f"Error creant intents de pujada: {str(e)}")
            return None, f"Error intern: {str(e)}"

    # ------------------------------------------------------------------
    # 2. Confirmació
    # ------------------------------------------------------------------

    def confirm_upload_intents(self, uid: str, upload_ids: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Processa els fitxers pujats a quarantine.

        Returns:
            ({'uploaded': [MediaItem], 'failed': [{upload_id, reason}]}, None)
        """
        try:
            uploaded, failed = [], []
            seen = set()
            for upload_id in upload_ids:
                if upload_id in seen:
                    continue
                seen.add(upload_id)
                item, reason = self._confirm_one(uid, upload_id)
                if item is not None:
                    uploaded.append(item)
                else:
                    failed.append({'upload_id': upload_id, 'reason': reason or REASON_PROCESSING_ERROR})
            return {'uploaded': uploaded, 'failed': failed}, None
        except Exception as e:
            logger.error(f"Error confirmant intents de pujada: {str(e)}")
            return None, f"Error intern: {str(e)}"

    def _confirm_one(self, uid: str, upload_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        intent = self.intent_dao.get_intent(upload_id)
        if intent is None or intent.uid != uid:
            return None, REASON_MISSING_OBJECT

        # Idempotència: un reintent retorna el resultat anterior
        if intent.status == INTENT_STATUS_CONFIRMED:
            item = self._existing_item(intent)
            return (item, None) if item else (None, REASON_MISSING_OBJECT)
        if intent.status == INTENT_STATUS_FAILED:
            return None, intent.failure_reason or REASON_PROCESSING_ERROR

        if intent.expire_at is not None:
            try:
                if get_madrid_now() > intent.expire_at:
                    return None, REASON_MISSING_OBJECT
            except TypeError:
                pass

        service = self.refugi_media_service
        q_key = intent.quarantine_key
        head = service.head_object(q_key)
        if head is None:
            # El client encara pot repetir el PUT mentre l'intent no caduqui
            return None, REASON_MISSING_OBJECT

        kind = kind_for_content_type(intent.content_type)
        limit = max_bytes_for_kind(kind) if kind else VIDEO_MAX_BYTES
        if head['size'] > limit:
            self._discard_quarantine(q_key)
            self.intent_dao.mark_failed(upload_id, REASON_TOO_LARGE)
            return None, REASON_TOO_LARGE

        data = service.get_object_bytes(q_key, max_bytes=limit)
        if data is None:
            return None, REASON_MISSING_OBJECT
        if len(data) > limit:
            self._discard_quarantine(q_key)
            self.intent_dao.mark_failed(upload_id, REASON_TOO_LARGE)
            return None, REASON_TOO_LARGE

        item, reason = self.process_and_publish(
            data=data,
            declared_content_type=intent.content_type,
            target=intent.target,
            uid=uid,
            refuge_id=intent.refuge_id,
            experience_id=intent.experience_id,
            rights_confirmed_at=intent.rights_confirmed_at,
            quarantine_key=q_key,
            upload_id=upload_id,
        )

        if item is None:
            if reason != REASON_MODERATION_BLOCKED:  # l'evidència ja s'ha mogut a moderation-hold/
                self._discard_quarantine(q_key)
            self.intent_dao.mark_failed(upload_id, reason or REASON_PROCESSING_ERROR)
            return None, reason

        self._discard_quarantine(q_key)
        self.intent_dao.mark_confirmed(upload_id, item['key'])
        audit.audit_log_service.log(uid, audit.ACTION_UPLOAD_CONFIRM, intent.target, item['key'],
                                    {'upload_id': upload_id, 'refuge_id': intent.refuge_id,
                                     'experience_id': intent.experience_id})
        return item, None

    def _existing_item(self, intent: UploadIntent) -> Optional[Dict[str, Any]]:
        """Reconstrueix el MediaItem d'un intent ja confirmat"""
        if not intent.result_key:
            return None
        if intent.target == UPLOAD_TARGET_AVATAR:
            avatar = self.account_selectors.get_avatar(intent.uid)
            if avatar and avatar.key == intent.result_key:
                return avatar_to_dict(avatar, intent.uid, lambda k: self.avatar_service.generate_presigned_url(k))
            return None
        exists, entry = self.refugi_dao.get_media_entry(intent.refuge_id, intent.result_key)
        if not exists or entry is None:
            return None
        return self.refugi_media_service.generate_media_metadata_from_dict({intent.result_key: entry}).to_dict()

    def _discard_quarantine(self, q_key: Optional[str]) -> None:
        if not q_key:
            return
        if not self.refugi_media_service.delete_file(q_key):
            logger.warning(f"No s'ha pogut esborrar {q_key}; el lifecycle de R2 l'esborrarà en 1 dia")

    # ------------------------------------------------------------------
    # 3. Processament + publicació (compartit amb el multipart antic)
    # ------------------------------------------------------------------

    def process_and_publish(
        self,
        data: bytes,
        declared_content_type: Optional[str],
        target: str,
        uid: str,
        refuge_id: Optional[str] = None,
        experience_id: Optional[str] = None,
        rights_confirmed_at: Optional[str] = None,
        quarantine_key: Optional[str] = None,
        upload_id: Optional[str] = None,
        uploaded_at: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Valida, processa, modera i publica un fitxer.

        Returns:
            (MediaItem dict, None) o (None, reason)
        """
        try:
            processed = self.processor.process(
                data, declared_content_type, avatar=(target == UPLOAD_TARGET_AVATAR)
            )
        except MediaRejected as e:
            logger.info(f"Fitxer rebutjat ({e.reason}) per l'usuari {uid}: {e}")
            return None, e.reason
        except Exception as e:
            logger.error(f"Error inesperat processant el fitxer: {str(e)}")
            return None, REASON_PROCESSING_ERROR

        try:
            moderation = self.moderation_service.check(ModerationInput(
                sha256=processed.sha256, phash=processed.phash, media_type=processed.media_type
            ))
        except Exception as e:
            logger.error(f"Error a la moderació automàtica (fail-closed): {str(e)}")
            return None, REASON_PROCESSING_ERROR

        if moderation.blocked:
            self._handle_moderation_block(uid, data, declared_content_type, target, refuge_id,
                                          quarantine_key, moderation, upload_id)
            return None, REASON_MODERATION_BLOCKED

        if target == UPLOAD_TARGET_AVATAR:
            return self._publish_avatar(uid, processed, uploaded_at)
        return self._publish_refuge_media(uid, processed, refuge_id, experience_id,
                                          rights_confirmed_at, uploaded_at)

    def _publish_refuge_media(self, uid: str, processed: ProcessedMedia, refuge_id: str,
                              experience_id: Optional[str], rights_confirmed_at: Optional[str],
                              uploaded_at: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        service = self.refugi_media_service
        media_id = str(uuid.uuid4())
        key = service.build_media_key(refuge_id, processed.extension, media_id=media_id)
        thumb_key = service.build_media_key(refuge_id, '.webp', suffix='_thumb', media_id=media_id) \
            if processed.thumb_bytes else None
        written: List[str] = []

        try:
            service.put_bytes(key, processed.main_bytes, processed.content_type)
            written.append(key)
            if thumb_key:
                service.put_bytes(thumb_key, processed.thumb_bytes, 'image/webp')
                written.append(thumb_key)
        except Exception as e:
            logger.error(f"Error pujant el mitjà processat: {str(e)}")
            self._rollback_files(written)
            return None, REASON_PROCESSING_ERROR

        metadata = {
            'creator_uid': uid,
            'uploaded_at': uploaded_at or get_madrid_now().isoformat(),
            'taken_at': processed.taken_at,
            'experience_id': experience_id,
            'media_type': processed.media_type,
            'content_type': processed.content_type,
            'width': processed.width,
            'height': processed.height,
            'size': processed.size,
            'thumb_key': thumb_key,
            'blurhash': processed.blurhash,
            'status': MEDIA_STATUS_VISIBLE,
            'rights_confirmed_at': rights_confirmed_at,
        }

        if not self.refugi_dao.add_media_metadata(refuge_id, {key: metadata}):
            self._rollback_files(written)
            return None, REASON_PROCESSING_ERROR

        if experience_id:
            success, _ = self.experience_dao.add_media_keys_to_experience(experience_id, [key])
            if not success:
                self._rollback_media(refuge_id, key, written)
                return None, REASON_PROCESSING_ERROR

        item = service.generate_media_metadata_from_dict({key: metadata})
        return item.to_dict(), None

    def _publish_avatar(self, uid: str, processed: ProcessedMedia,
                        uploaded_at: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        old = self.account_selectors.get_avatar(uid)
        old_key = old.key if old else None
        old_thumb = old.thumb_key if old else None

        service = self.avatar_service
        key = service.build_media_key(uid, processed.extension)
        try:
            service.put_bytes(key, processed.main_bytes, processed.content_type)
        except Exception as e:
            logger.error(f"Error pujant l'avatar processat: {str(e)}")
            return None, REASON_PROCESSING_ERROR

        metadata = {
            'key': key,
            'uploaded_at': uploaded_at or get_madrid_now().isoformat(),
            'width': processed.width,
            'height': processed.height,
            'blurhash': processed.blurhash,
            'size': processed.size,
            'content_type': processed.content_type,
        }
        if not self.accounts.update_avatar_metadata(uid, metadata):
            self._rollback_files([key], service)
            return None, REASON_PROCESSING_ERROR

        # L'avatar antic s'esborra NOMÉS després que el nou s'hagi desat bé
        for stale in (old_key, old_thumb):
            if stale and stale != key and not service.delete_file(stale):
                logger.warning(f"Avatar antic orfe a R2 (no s'ha pogut esborrar): {stale}")

        audit.audit_log_service.log(uid, audit.ACTION_AVATAR_UPLOAD, 'avatar', key)
        item = service.generate_media_metadata_from_dict(metadata)
        item.creator_uid = uid
        return item.to_dict(), None

    def _rollback_files(self, keys: List[str], service=None) -> None:
        service = service or self.refugi_media_service
        for key in keys:
            if not service.delete_file(key):
                logger.error(f"Rollback incomplet: fitxer orfe a R2 {key}")

    def _rollback_media(self, refuge_id: str, key: str, files: List[str]) -> None:
        success, _ = self.refugi_dao.delete_media_metadata(refuge_id, key)
        if not success:
            logger.error(f"Rollback incomplet: no s'ha pogut esborrar media_metadata {key} del refugi {refuge_id}")
        self._rollback_files(files)

    # ------------------------------------------------------------------
    # Moderació automàtica: coincidència amb la blocklist
    # ------------------------------------------------------------------

    def _handle_moderation_block(self, uid: str, data: bytes, declared_content_type: Optional[str],
                                 target: str, refuge_id: Optional[str], quarantine_key: Optional[str],
                                 moderation, upload_id: Optional[str]) -> None:
        """
        No es publica res. L'evidència es conserva a moderation-hold/ (accés restringit),
        es bloqueja l'usuari, es crea una denúncia child_sexual_abuse d'alta prioritat,
        s'envia l'avís de moderació i es registra a l'auditoria.
        """
        now = get_madrid_now().isoformat()
        hold_key = r2_media_service.moderation_hold_key(f"{uid}/{upload_id or uuid.uuid4()}")
        service = self.refugi_media_service
        try:
            if quarantine_key:
                if not service.move_object(quarantine_key, hold_key):
                    logger.error(f"No s'ha pogut moure l'evidència {quarantine_key} a {hold_key}")
            else:
                service.put_bytes(hold_key, data, normalize_content_type(declared_content_type) or 'application/octet-stream')
        except Exception as e:
            logger.error(f"Error desant l'evidència de moderació: {str(e)}")

        self.accounts.set_blocked(uid, True, reason='moderation_hash_match', blocked_at=now)

        report_refuge = refuge_id or target
        try:
            report = MediaReport(
                id=build_report_id(report_refuge, hold_key, SYSTEM_REPORTER_UID),
                refuge_id=report_refuge,
                media_key=hold_key,
                reporter_uid=SYSTEM_REPORTER_UID,
                reason='child_sexual_abuse',
                details=f"Coincidència automàtica ({moderation.provider}/{moderation.match_type}, categoria {moderation.category})",
                media_creator_uid=uid,
                priority=REPORT_PRIORITY_HIGH,
                created_at=now,
                source='automatic',
            )
            self.report_dao.create_report(report)
        except Exception as e:
            logger.error(f"Error creant la denúncia automàtica: {str(e)}")

        self.notice_dao.create_notice({
            'uid': uid,
            'type': NOTICE_ACCOUNT_BLOCKED,
            'statement': ("Un fitxer que has intentat pujar coincideix amb una llista de contingut "
                          "il·legal conegut. No s'ha publicat i el compte s'ha bloquejat."),
            'created_at': now,
            'refuge_id': refuge_id,
            'reason': 'child_sexual_abuse',
            'action': 'upload_blocked',
            'automated': True,
        })

        audit.audit_log_service.log(SYSTEM_REPORTER_UID, audit.ACTION_MODERATION_HASH_BLOCK, 'upload', hold_key,
                                    {'uid': uid, 'provider': moderation.provider,
                                     'match_type': moderation.match_type, 'upload_id': upload_id})
        audit.audit_log_service.log(SYSTEM_REPORTER_UID, audit.ACTION_USER_BLOCKED, 'user', uid,
                                    {'reason': 'moderation_hash_match'})
