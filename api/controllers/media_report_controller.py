"""
Controller de denúncies i moderació de mitjans (DSA art. 16, 17 i 20).

- Denúncia per usuaris (POST /api/media/reports/) amb autoocultació.
- Revisió per admins (GET/PATCH /api/admin/media-reports/) amb strikes i bloqueig.
- Avisos de moderació a l'usuari afectat (GET /api/users/{uid}/moderation-notices/).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..daos.media_report_dao import MediaReportDAO, DUPLICATE_REPORT_ERROR
from ..daos.moderation_notice_dao import ModerationNoticeDAO
from ..daos.refugi_lliure_dao import RefugiLliureDAO
from ..daos.user_dao import UserDAO
from ..daos.experience_dao import ExperienceDAO
from ..models.media_metadata import MEDIA_STATUS_HIDDEN, MEDIA_STATUS_REMOVED, MEDIA_STATUS_VISIBLE
from ..models.media_report import (
    MediaReport, build_report_id, AUTO_HIDE_REASONS, AUTO_HIDE_DISTINCT_REPORTERS,
    REPORT_PRIORITY_HIGH, REPORT_PRIORITY_NORMAL, REPORT_STATUS_PENDING, REPORT_STATUS_RESOLVED,
    REPORT_ACTION_DISMISS, REPORT_ACTION_REMOVE_AND_STRIKE,
)
from ..models.moderation_notice import (
    NOTICE_CONTENT_HIDDEN, NOTICE_CONTENT_RESTORED, NOTICE_CONTENT_REMOVED, NOTICE_STRIKE,
    NOTICE_ACCOUNT_BLOCKED,
)
from ..services import r2_media_service
from ..services import audit_log_service as audit
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)

ERROR_REFUGE_NOT_FOUND = "Refugi not found"
ERROR_MEDIA_NOT_FOUND = "Media not found"
ERROR_REPORT_NOT_FOUND = "Report not found"
ERROR_OWN_MEDIA = "own_media"
ERROR_ALREADY_REPORTED = "already_reported"
ERROR_ALREADY_RESOLVED = "already_resolved"

STRIKES_TO_BLOCK = 3
CSAM_REASON = 'child_sexual_abuse'


class MediaReportController:
    """Controller de denúncies, resolució i avisos de moderació"""

    def __init__(self):
        self.report_dao = MediaReportDAO()
        self.notice_dao = ModerationNoticeDAO()
        self.refugi_dao = RefugiLliureDAO()
        self.user_dao = UserDAO()
        self.experience_dao = ExperienceDAO()
        self.media_service = r2_media_service.get_refugi_media_service()

    # ------------------------------------------------------------------
    # Denúncia
    # ------------------------------------------------------------------

    def create_report(self, reporter_uid: str, refuge_id: str, media_key: str, reason: str,
                      details: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Returns:
            (report dict, None) o (None, error) amb error ∈
            {Refugi not found, Media not found, own_media, already_reported, ...}
        """
        try:
            exists, entry = self.refugi_dao.get_media_entry(refuge_id, media_key)
            if not exists:
                return None, ERROR_REFUGE_NOT_FOUND
            if entry is None:
                return None, ERROR_MEDIA_NOT_FOUND

            creator_uid = entry.get('creator_uid')
            if creator_uid and creator_uid == reporter_uid:
                return None, ERROR_OWN_MEDIA

            now = get_madrid_now().isoformat()
            report = MediaReport(
                id=build_report_id(refuge_id, media_key, reporter_uid),
                refuge_id=refuge_id,
                media_key=media_key,
                reporter_uid=reporter_uid,
                reason=reason,
                details=(details or '').strip() or None,
                media_creator_uid=creator_uid,
                priority=REPORT_PRIORITY_HIGH if reason in AUTO_HIDE_REASONS else REPORT_PRIORITY_NORMAL,
                created_at=now,
            )
            created, error = self.report_dao.create_report(report)
            if not created:
                if error == DUPLICATE_REPORT_ERROR:
                    return None, ERROR_ALREADY_REPORTED
                return None, f"Error intern creant la denúncia: {error}"

            audit.audit_log_service.log(reporter_uid, audit.ACTION_REPORT_CREATE, 'media', media_key,
                                        {'refuge_id': refuge_id, 'reason': reason, 'report_id': report.id})

            should_hide = reason in AUTO_HIDE_REASONS
            if not should_hide:
                distinct = self.report_dao.count_distinct_pending_reporters(refuge_id, media_key)
                should_hide = distinct >= AUTO_HIDE_DISTINCT_REPORTERS

            media_hidden = False
            if should_hide:
                media_hidden = self.refugi_dao.update_media_status(
                    refuge_id, media_key, MEDIA_STATUS_HIDDEN, only_if_status=[MEDIA_STATUS_VISIBLE]
                )
                if media_hidden:
                    audit.audit_log_service.log('system', audit.ACTION_MODERATION_AUTO_HIDE, 'media', media_key,
                                                {'refuge_id': refuge_id, 'trigger_reason': reason})
                    if creator_uid:
                        self.notice_dao.create_notice({
                            'uid': creator_uid,
                            'type': NOTICE_CONTENT_HIDDEN,
                            'statement': ("El teu contingut s'ha ocultat de manera cautelar perquè ha rebut "
                                          "una denúncia que requereix revisió. Un moderador el revisarà."),
                            'created_at': now,
                            'refuge_id': refuge_id,
                            'media_key': media_key,
                            'reason': reason,
                            'action': 'auto_hide',
                            'report_id': report.id,
                            'automated': True,
                        })

            data = {
                'id': report.id,
                'refuge_id': refuge_id,
                'media_key': media_key,
                'reason': reason,
                'details': report.details,
                'status': report.status,
                'priority': report.priority,
                'created_at': report.created_at,
                'media_hidden': bool(media_hidden),
            }
            return data, None

        except ValueError as e:
            return None, f"invalid: {str(e)}"
        except Exception as e:
            logger.error(f"Error creant denúncia: {str(e)}")
            return None, f"Error intern: {str(e)}"

    # ------------------------------------------------------------------
    # Admin: llistat
    # ------------------------------------------------------------------

    def list_reports(self, status: str, admin_uid: Optional[str] = None) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Llista de denúncies amb una previsualització del mitjà (si encara existeix i no és evidència retinguda)"""
        try:
            reports = self.report_dao.list_reports(status)
            raw_by_refuge: Dict[str, Optional[dict]] = {}
            result = []
            for report in reports:
                media = None
                if not report.media_key.startswith(r2_media_service.MODERATION_HOLD_PREFIX + '/'):
                    if report.refuge_id not in raw_by_refuge:
                        try:
                            raw_by_refuge[report.refuge_id] = self.refugi_dao.get_raw_media_metadata(report.refuge_id)
                        except Exception:
                            raw_by_refuge[report.refuge_id] = None
                    raw = raw_by_refuge.get(report.refuge_id) or {}
                    entry = raw.get(report.media_key) if isinstance(raw, dict) else None
                    if entry is not None:
                        item = self.media_service.generate_media_metadata_from_dict({report.media_key: entry})
                        media = item.to_dict()
                        media['status'] = entry.get('status') or MEDIA_STATUS_VISIBLE
                data = report.to_dict()
                data['media'] = media
                result.append(data)
            audit.audit_log_service.log(admin_uid, audit.ACTION_REPORTS_LIST, 'media_reports', status,
                                        {'count': len(result)})
            return result, None
        except Exception as e:
            logger.error(f"Error llistant denúncies: {str(e)}")
            return None, f"Error intern: {str(e)}"

    # ------------------------------------------------------------------
    # Admin: resolució
    # ------------------------------------------------------------------

    def resolve_report(self, report_id: str, action: str, statement: str,
                       admin_uid: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Resol la denúncia i TOTES les pendents del mateix mitjà (una decisió per mitjà).

        - dismiss: el mitjà torna a ser visible (si estava ocult cautelarment)
        - remove: status = removed (es conserva per a recursos; només el veuen autor i admins)
        - remove_and_strike: com remove + 1 strike; amb 3 strikes → is_blocked
        - CSAM confirmat (remove*): el fitxer es mou a moderation-hold/, es treu de l'app i
          es bloqueja l'usuari immediatament
        """
        try:
            report = self.report_dao.get_report(report_id)
            if report is None:
                return None, ERROR_REPORT_NOT_FOUND
            if report.status == REPORT_STATUS_RESOLVED:
                return None, ERROR_ALREADY_RESOLVED

            pending = self.report_dao.list_reports_for_media(report.refuge_id, report.media_key, REPORT_STATUS_PENDING)
            pending_by_id = {r.id: r for r in pending}
            pending_by_id[report.id] = report
            related = list(pending_by_id.values())

            now = get_madrid_now().isoformat()
            creator_uid = report.media_creator_uid
            if not creator_uid:
                _, entry = self.refugi_dao.get_media_entry(report.refuge_id, report.media_key)
                creator_uid = (entry or {}).get('creator_uid')

            is_csam = any(r.reason == CSAM_REASON for r in related)
            media_status = None
            strikes = None
            user_blocked = False

            if action == REPORT_ACTION_DISMISS:
                if self.refugi_dao.update_media_status(report.refuge_id, report.media_key, MEDIA_STATUS_VISIBLE,
                                                       only_if_status=[MEDIA_STATUS_HIDDEN]):
                    media_status = MEDIA_STATUS_VISIBLE
                    if creator_uid:
                        self._notify(creator_uid, NOTICE_CONTENT_RESTORED, statement, report, action, now)
            else:
                if is_csam:
                    self._hold_media(report.refuge_id, report.media_key)
                    media_status = 'held'
                else:
                    self.refugi_dao.update_media_status(report.refuge_id, report.media_key, MEDIA_STATUS_REMOVED)
                    media_status = MEDIA_STATUS_REMOVED

                if creator_uid:
                    if action == REPORT_ACTION_REMOVE_AND_STRIKE:
                        strikes = self.user_dao.increment_moderation_strikes(creator_uid)
                    self._notify(creator_uid,
                                 NOTICE_STRIKE if action == REPORT_ACTION_REMOVE_AND_STRIKE else NOTICE_CONTENT_REMOVED,
                                 statement, report, action, now, strikes=strikes)

                    if is_csam or (strikes is not None and strikes >= STRIKES_TO_BLOCK):
                        block_reason = 'csam_confirmed' if is_csam else 'strikes'
                        user_blocked = self.user_dao.set_blocked(creator_uid, True, reason=block_reason, blocked_at=now)
                        self._notify(creator_uid, NOTICE_ACCOUNT_BLOCKED,
                                     "El compte s'ha bloquejat: " + (
                                         "contingut d'abús sexual infantil confirmat." if is_csam
                                         else f"s'han acumulat {strikes} infraccions."),
                                     report, action, now, strikes=strikes)
                        audit.audit_log_service.log(admin_uid, audit.ACTION_USER_BLOCKED, 'user', creator_uid,
                                                    {'reason': block_reason, 'report_id': report.id})

            resolved_ids = [r.id for r in related]
            updates = {
                'status': REPORT_STATUS_RESOLVED,
                'resolved_at': now,
                'resolved_by': admin_uid,
                'action': action,
                'statement': statement,
            }
            if not self.report_dao.resolve_reports(resolved_ids, updates):
                return None, "Error intern resolent la denúncia"

            audit.audit_log_service.log(admin_uid, audit.ACTION_MODERATION_RESOLVE, 'media', report.media_key,
                                        {'refuge_id': report.refuge_id, 'action': action,
                                         'report_ids': resolved_ids, 'csam': is_csam})

            data = report.to_dict()
            data.update(updates)
            return {
                'report': data,
                'resolved_report_ids': resolved_ids,
                'media_status': media_status,
                'strikes': strikes,
                'user_blocked': bool(user_blocked),
            }, None

        except Exception as e:
            logger.error(f"Error resolent la denúncia {report_id}: {str(e)}")
            return None, f"Error intern: {str(e)}"

    def _notify(self, uid: str, notice_type: str, statement: str, report: MediaReport, action: str,
                now: str, strikes: Optional[int] = None) -> None:
        self.notice_dao.create_notice({
            'uid': uid,
            'type': notice_type,
            'statement': statement,
            'created_at': now,
            'refuge_id': report.refuge_id,
            'media_key': report.media_key,
            'reason': report.reason,
            'action': action,
            'report_id': report.id,
            'automated': False,
            'strikes': strikes,
        })

    def _hold_media(self, refuge_id: str, media_key: str) -> None:
        """Mou el fitxer (i la miniatura) a moderation-hold/ i el treu de l'app"""
        success, backup = self.refugi_dao.delete_media_metadata(refuge_id, media_key)
        backup = backup or {}
        for key in (media_key, backup.get('thumb_key')):
            if key and not self.media_service.move_object(key, r2_media_service.moderation_hold_key(key)):
                logger.error(f"No s'ha pogut retenir {key} a moderation-hold/")
        if backup.get('experience_id'):
            self.experience_dao.remove_media_key(backup['experience_id'], media_key)
        if backup.get('creator_uid'):
            self.user_dao.remove_uploaded_photos_keys(backup['creator_uid'], [media_key])

    # ------------------------------------------------------------------
    # Avisos a l'usuari
    # ------------------------------------------------------------------

    def get_user_notices(self, uid: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        try:
            return [n.to_dict() for n in self.notice_dao.list_by_uid(uid)], None
        except Exception as e:
            logger.error(f"Error obtenint avisos de moderació de {uid}: {str(e)}")
            return None, f"Error intern: {str(e)}"
