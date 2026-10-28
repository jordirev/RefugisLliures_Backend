"""
Escriptures de `moderation` (substitueixen el `MediaReportController` i els DAOs de Firestore; docs/design/
postgres-schema.md §2.20–§2.22, §8.3; D40, D41): denunciar, resoldre i purgar.

- **Denunciar** (`create_report`): un únic bloc `system_context()` acotat (la RLS només deixa veure les denúncies pròpies,
  però cal comptar denunciants diferents, ocultar el mitjà i avisar-ne l'autor). El mitjà es llegeix amb `FOR UPDATE`:
  serialitza el recompte i l'ocultació (tres denunciants alhora = un sol avís). El 409 és la restricció `UNIQUE`
  (`media_reports_unique_reporter_uq`), traduïda per `constraint_name`.
- **Resoldre** (`resolve_report`): una transacció (`atomic`) que resol totes les denúncies pendents del mateix mitjà amb una
  sola decisió, un avís per decisió i un sol *strike*. Es bloquegen les denúncies pendents del mitjà per `id` (mai una
  de sola abans: dos admins sobre germanes no es poden interbloquejar). CSAM: primer es **copien** tots els fitxers a
  `moderation-hold/`, després s'esborren la fila i els originals; si R2 falla, tot es desfà (l'evidència no es pot perdre).
- **Purgar** (`purge_expired`): retenció de §8.3 (denúncies i avisos 24 mesos després de resoldre; `legal_hold` 5 anys).
"""
import logging
import uuid
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, connection, transaction
from django.db.models import Count
from django.db.models.functions import Now

from api.services import r2_media_service
from apps.accounts import services as account_services
from apps.audit import services as audit
from apps.core.rls import system_context
from apps.refuges import selectors as refuge_selectors
from apps.refuges.models import MediaStatus, RefugeMedia
from apps.refuges.serializers import isoformat_madrid

from . import hashing
from .models import (
    AUTO_HIDE_DISTINCT_REPORTERS, AUTO_HIDE_REASONS, CSAM_REASON, MediaReport, ModerationNotice, NoticeAction,
    NoticeType, ReportAction, ReportPriority, ReportSource, ReportStatus)
from .serializers import report_to_dict

logger = logging.getLogger(__name__)

phash_hex_to_signed = hashing.phash_hex_to_signed      # API pública del servei (conversió hex -> bigint amb signe)

STRIKES_TO_BLOCK = 3
UNIQUE_REPORTER_CONSTRAINT = 'media_reports_unique_reporter_uq'
HOLD_PREFIX = r2_media_service.MODERATION_HOLD_PREFIX + '/'

HIDDEN_NOTICE_STATEMENT = ("El teu contingut s'ha ocultat de manera cautelar perquè ha rebut una denúncia que "
                           "requereix revisió. Un moderador el revisarà.")

# Retenció (§8.3): mesos naturals aproximats en dies, com els 24 mesos de la decisió 9; 5 anys per a `legal_hold`.
RETENTION_DAYS = 730
LEGAL_HOLD_RETENTION_DAYS = 1826


class RefugeNotFound(Exception):
    """El refugi no existeix (o l'ID no és un UUID)."""


class MediaNotFound(Exception):
    """El mitjà no existeix en aquest refugi, està retirat o és evidència retinguda."""


class OwnMedia(Exception):
    """L'autor no pot denunciar el seu propi mitjà."""


class AlreadyReported(Exception):
    """El denunciant ja havia denunciat aquest mitjà."""


class ReportNotFound(Exception):
    """La denúncia no existeix (o l'ID no és un UUID)."""


class AlreadyResolved(Exception):
    """La denúncia ja està resolta."""


class EvidenceHoldError(Exception):
    """No s'ha pogut copiar l'evidència a `moderation-hold/` (R2): la resolució es desfà."""


def _constraint_name(exc: IntegrityError) -> Optional[str]:
    return getattr(getattr(exc.__cause__, 'diag', None), 'constraint_name', None)


def _parse_uuid(value) -> Optional[uuid.UUID]:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _opt_str(value) -> Optional[str]:
    return str(value) if value else None


# =============================================================================
# Denúncia
# =============================================================================

def create_report(*, reporter_uid: str, refuge_id, media_key: str, reason: str,
                  details: Optional[str] = None) -> Dict[str, Any]:
    """
    Crea la denúncia i, si toca, oculta el mitjà i en avisa l'autor. Retorna el diccionari de la resposta de l'API.

    Raises: `RefugeNotFound`, `MediaNotFound`, `OwnMedia`, `AlreadyReported`.
    """
    refuge_pk = refuge_selectors.parse_refuge_id(refuge_id)
    if refuge_pk is None or not refuge_selectors.refuge_exists(refuge_pk):
        raise RefugeNotFound()
    if media_key.startswith(HOLD_PREFIX):            # evidència retinguda: no és pública
        raise MediaNotFound()
    details = (details or '').strip() or None
    priority = ReportPriority.HIGH if reason in AUTO_HIDE_REASONS else ReportPriority.NORMAL

    with system_context():
        # `FOR UPDATE`: serialitza el recompte de denunciants i l'ocultació d'aquest mitjà (concurrència).
        found = list(RefugeMedia.objects.select_for_update()
                     .filter(key=media_key, refuge_id=refuge_pk).values_list('creator_id', 'status')[:1])
        if not found or found[0][1] == MediaStatus.REMOVED:
            raise MediaNotFound()
        creator_uid, media_status = found[0]
        if creator_uid == reporter_uid:
            raise OwnMedia()
        try:
            with transaction.atomic():
                report = MediaReport.objects.create(
                    refuge_id=refuge_pk, media_key=media_key, reporter_id=reporter_uid, reason=reason,
                    details=details, media_creator_id=creator_uid, priority=priority,
                    legal_hold=(reason == CSAM_REASON))
        except IntegrityError as exc:
            if _constraint_name(exc) == UNIQUE_REPORTER_CONSTRAINT:
                raise AlreadyReported() from None
            raise

        should_hide = reason in AUTO_HIDE_REASONS
        if not should_hide:
            distinct = (MediaReport.objects
                        .filter(refuge_id=refuge_pk, media_key=media_key, status=ReportStatus.PENDING,
                                reporter__isnull=False)
                        .aggregate(n=Count('reporter_id', distinct=True))['n'])
            should_hide = distinct >= AUTO_HIDE_DISTINCT_REPORTERS
        hidden = False
        if should_hide and media_status == MediaStatus.VISIBLE:
            hidden = bool(RefugeMedia.objects.filter(key=media_key, refuge_id=refuge_pk, status=MediaStatus.VISIBLE)
                          .update(status=MediaStatus.HIDDEN_PENDING_REVIEW))
            if hidden and creator_uid:
                ModerationNotice.objects.create(
                    user_id=creator_uid, type=NoticeType.CONTENT_HIDDEN, statement=HIDDEN_NOTICE_STATEMENT,
                    refuge_id=refuge_pk, media_key=media_key, reason=reason, action=NoticeAction.AUTO_HIDE,
                    report_id=report.pk, automated=True)

    audit.audit_log_service.log(reporter_uid, audit.ACTION_REPORT_CREATE, 'media', media_key,
                                {'refuge_id': str(refuge_pk), 'reason': reason, 'report_id': str(report.pk)})
    if hidden:
        audit.audit_log_service.log('system', audit.ACTION_MODERATION_AUTO_HIDE, 'media', media_key,
                                    {'refuge_id': str(refuge_pk), 'trigger_reason': reason})
    return {
        'id': str(report.pk), 'refuge_id': str(refuge_pk), 'media_key': media_key, 'reason': reason,
        'details': details, 'status': report.status, 'priority': report.priority,
        'created_at': isoformat_madrid(report.created_at), 'media_hidden': hidden,
    }


# =============================================================================
# Resolució
# =============================================================================

def _notify(creator_uid: Optional[str], notice_type: str, statement: str, report: MediaReport, action: str,
            strikes: Optional[int] = None) -> None:
    """Un avís de decisió per a l'autor del mitjà (cap si l'autor ja no existeix)."""
    if not creator_uid:
        return
    ModerationNotice.objects.create(
        user_id=creator_uid, type=notice_type, statement=statement, refuge_id=report.refuge_id,
        media_key=report.media_key, reason=report.reason, action=action, report_id=report.pk, automated=False,
        strikes=strikes)


def _lock_related(report: MediaReport) -> List[MediaReport]:
    """Denúncies pendents del mateix mitjà i refugi, bloquejades per `id` (ordre determinista)."""
    return list(MediaReport.objects.select_for_update()
                .filter(media_key=report.media_key, refuge_id=report.refuge_id, status=ReportStatus.PENDING)
                .order_by('id'))


def _hold_media(refuge_id, media_key: str) -> Optional[List[str]]:
    """
    Retenció CSAM: copia el fitxer i la miniatura a `moderation-hold/` (tots primer) i esborra la fila. Retorna les
    claus originals a esborrar d'R2 (`_delete_originals`, l'ÚLTIM pas de la transacció: si la BD falla després, es
    desfà i els originals hi són encara) o `None` si el mitjà ja no existeix. Si una còpia falla, `EvidenceHoldError`.
    """
    media = RefugeMedia.objects.filter(key=media_key, refuge_id=refuge_id).values('thumb_key').first()
    if media is None:
        return None
    keys = [k for k in (media_key, media['thumb_key']) if k]
    service = r2_media_service.get_refugi_media_service()
    for key in keys:
        if not service.copy_object(key, r2_media_service.moderation_hold_key(key)):
            raise EvidenceHoldError()
    RefugeMedia.objects.filter(key=media_key, refuge_id=refuge_id).delete()
    return keys


def _delete_originals(keys: List[str]) -> None:
    service = r2_media_service.get_refugi_media_service()
    for key in keys:
        if not service.delete_file(key):
            logger.warning("Evidència copiada a moderation-hold/ però no s'ha pogut esborrar l'original %s", key)


def resolve_report(*, report_id, action: str, statement: str, admin_uid: str) -> Dict[str, Any]:
    """
    Resol la denúncia i TOTES les pendents del mateix mitjà (una decisió per mitjà). Es fa dins d'una transacció pròpia:
    qualsevol error la desfà sencera.

    - dismiss: el mitjà ocult torna a ser visible (avís `content_restored`); si no estava ocult, no canvia res.
    - remove: `removed` (es conserva per a recursos; només el veuen l'autor i els admins) · remove_and_strike: + 1 strike;
      a 3, bloqueig `strikes`.
    - CSAM (alguna denúncia del mitjà amb `child_sexual_abuse`) amb remove/remove_and_strike: el fitxer passa a
      `moderation-hold/`, la fila s'esborra, l'usuari es bloqueja (`csam_confirmed`) i les denúncies passen a `legal_hold`.

    Raises: `ReportNotFound`, `AlreadyResolved`, `EvidenceHoldError`.
    """
    pk = _parse_uuid(report_id)
    report = MediaReport.objects.filter(pk=pk).first() if pk else None
    if report is None:
        raise ReportNotFound()
    if report.status == ReportStatus.RESOLVED:
        raise AlreadyResolved()

    with transaction.atomic():
        related = _lock_related(report)
        if report.pk not in {r.pk for r in related}:      # un altre admin l'ha resolta mentrestant
            raise AlreadyResolved()
        creator_uid = report.media_creator_id
        is_csam = any(r.reason == CSAM_REASON for r in related)
        media_status = None
        held_keys: Optional[List[str]] = None
        strikes = None
        user_blocked = False

        if action == ReportAction.DISMISS:
            if RefugeMedia.objects.filter(key=report.media_key, refuge_id=report.refuge_id,
                                          status=MediaStatus.HIDDEN_PENDING_REVIEW).update(status=MediaStatus.VISIBLE):
                media_status = MediaStatus.VISIBLE.value
                _notify(creator_uid, NoticeType.CONTENT_RESTORED, statement, report, action)
        else:
            if is_csam:
                held_keys = _hold_media(report.refuge_id, report.media_key)
                media_status = 'held' if held_keys is not None else None
            elif RefugeMedia.objects.filter(key=report.media_key, refuge_id=report.refuge_id).update(
                    status=MediaStatus.REMOVED):
                media_status = MediaStatus.REMOVED.value
            if creator_uid:
                if action == ReportAction.REMOVE_AND_STRIKE:
                    strikes = account_services.increment_moderation_strikes(creator_uid)
                _notify(creator_uid, NoticeType.STRIKE if action == ReportAction.REMOVE_AND_STRIKE
                        else NoticeType.CONTENT_REMOVED, statement, report, action, strikes=strikes)
                if is_csam or (strikes is not None and strikes >= STRIKES_TO_BLOCK):
                    block_reason = 'csam_confirmed' if is_csam else 'strikes'
                    user_blocked = account_services.set_blocked(creator_uid, True, reason=block_reason)
                    _notify(creator_uid, NoticeType.ACCOUNT_BLOCKED,
                            "El compte s'ha bloquejat: " + ("contingut d'abús sexual infantil confirmat." if is_csam
                                                            else f"s'han acumulat {strikes} infraccions."),
                            report, action, strikes=strikes)
                    audit.audit_log_service.log(admin_uid, audit.ACTION_USER_BLOCKED, 'user', creator_uid,
                                                {'reason': block_reason, 'report_id': str(report.pk)})

        resolved_ids = [r.pk for r in related]
        changes = dict(status=ReportStatus.RESOLVED, resolved_at=Now(), resolved_by_id=admin_uid, action=action,
                       statement=statement)
        if is_csam:
            changes['legal_hold'] = True
        MediaReport.objects.filter(pk__in=resolved_ids).update(**changes)
        resolved = MediaReport.objects.get(pk=report.pk)
        audit.audit_log_service.log(admin_uid, audit.ACTION_MODERATION_RESOLVE, 'media', report.media_key,
                                    {'refuge_id': _opt_str(report.refuge_id), 'action': action,
                                     'report_ids': [str(i) for i in resolved_ids], 'csam': is_csam})
        if held_keys:
            _delete_originals(held_keys)

    return {
        'report': report_to_dict(resolved),
        'resolved_report_ids': [str(i) for i in resolved_ids],
        'media_status': media_status,
        'strikes': strikes,
        'user_blocked': bool(user_blocked),
    }


# =============================================================================
# Pujada bloquejada per la llista de hashes
# =============================================================================

UPLOAD_BLOCKED_STATEMENT = ("Un fitxer que has intentat pujar coincideix amb una llista de contingut il·legal conegut. "
                            "No s'ha publicat i el compte s'ha bloquejat.")


def register_upload_block(*, uid: str, refuge_id, hold_key: str, upload_id: str, provider: str, match_type: str,
                          category: str) -> uuid.UUID:
    """
    Registra una pujada bloquejada per coincidència de hash: denúncia automàtica `child_sexual_abuse` (alta prioritat,
    `legal_hold`, `reporter_uid` NULL; `refuge_id` NULL per a un avatar), avís `account_blocked`/`upload_blocked` lligat
    a la denúncia i auditoria `legal_hold` (`hash_block` i `user_blocked`, actor sistema, sense l'UID a les metadades).
    El bloqueig de l'usuari i el moviment de l'evidència els fa qui crida. Retorna l'`id` de la denúncia.
    """
    refuge_pk = refuge_selectors.parse_refuge_id(refuge_id) if refuge_id else None
    with system_context():            # escriptura creuada: denúncia automàtica i avís per a un altre usuari (§2.20)
        report = MediaReport.objects.create(
            refuge_id=refuge_pk, media_key=hold_key, reason=CSAM_REASON, priority=ReportPriority.HIGH,
            source=ReportSource.AUTOMATIC, legal_hold=True, media_creator_id=uid,
            details=f'Coincidència automàtica ({provider}/{match_type}, categoria {category})')
        ModerationNotice.objects.create(
            user_id=uid, type=NoticeType.ACCOUNT_BLOCKED, statement=UPLOAD_BLOCKED_STATEMENT, refuge_id=refuge_pk,
            reason=CSAM_REASON, action=NoticeAction.UPLOAD_BLOCKED, report_id=report.pk, automated=True)
    audit.audit_log_service.log('system', audit.ACTION_MODERATION_HASH_BLOCK, 'upload', upload_id,
                                {'provider': provider, 'match_type': match_type, 'upload_id': upload_id})
    audit.audit_log_service.log('system', audit.ACTION_USER_BLOCKED, 'user', uid,
                                {'reason': 'moderation_hash_match'})
    return report.pk


# =============================================================================
# Purga (job; retenció §8.3)
# =============================================================================

# Denúncies caducades: no `legal_hold` 24 mesos després de resoldre's (les pendents no caduquen); `legal_hold` 5 anys
# després de resoldre's o, si no, de crear-se. (La data base és sempre «ara» de la BD: res al SQL depèn del dia.)
# Cada lot són dues sentències (`SELECT` dels ids i `DELETE ... id = ANY(...)`): un `DELETE ... IN (subconsulta amb LIMIT)`
# deixava el planificador triar un bucle niuat quadràtic amb estadístiques velles.
_SELECT_REPORTS_SQL = """
SELECT id FROM moderation.media_reports
 WHERE (NOT legal_hold AND status = 'resolved' AND resolved_at < now() - make_interval(days => %s))
    OR (legal_hold AND coalesce(resolved_at, created_at) < now() - make_interval(days => %s))
 ORDER BY id LIMIT %s"""
_DELETE_REPORTS_SQL = 'DELETE FROM moderation.media_reports WHERE id = ANY(%s)'
# Avisos: 24 mesos, tret dels lligats a una denúncia `legal_hold` encara vigent (cauen amb ella als 5 anys).
_SELECT_NOTICES_SQL = """
SELECT n.id FROM moderation.moderation_notices n
 WHERE (n.created_at < now() - make_interval(days => %s) AND NOT EXISTS (
            SELECT 1 FROM moderation.media_reports r WHERE r.id = n.report_id AND r.legal_hold))
    OR EXISTS (SELECT 1 FROM moderation.media_reports r
                WHERE r.id = n.report_id AND r.legal_hold
                  AND coalesce(r.resolved_at, r.created_at) < now() - make_interval(days => %s))
 ORDER BY n.id LIMIT %s"""
_DELETE_NOTICES_SQL = 'DELETE FROM moderation.moderation_notices WHERE id = ANY(%s)'


def _purge(select_sql: str, delete_sql: str, params: list, batch_size: int) -> int:
    total = 0
    while True:
        with system_context():
            with connection.cursor() as cur:
                cur.execute(select_sql, [*params, batch_size])
                ids = [row[0] for row in cur.fetchall()]
                if ids:
                    cur.execute(delete_sql, [ids])
        total += len(ids)
        if len(ids) < batch_size:
            return total


def purge_expired(batch_size: int = 5000) -> Dict[str, int]:
    """
    Esborra denúncies i avisos caducats en lots de `batch_size`, amb `system_context()` propi (és un job). Primer els
    avisos (cauen pel seu termini; els lligats a una denúncia `legal_hold` esperen que aquesta caduqui) i després les
    denúncies (els avisos que queden apuntant-hi passen a `report_id` NULL per la FK i cauen pel termini de 24 mesos).
    """
    notices = _purge(_SELECT_NOTICES_SQL, _DELETE_NOTICES_SQL, [RETENTION_DAYS, LEGAL_HOLD_RETENTION_DAYS], batch_size)
    reports = _purge(_SELECT_REPORTS_SQL, _DELETE_REPORTS_SQL, [RETENTION_DAYS, LEGAL_HOLD_RETENTION_DAYS], batch_size)
    return {'reports': reports, 'notices': notices}
