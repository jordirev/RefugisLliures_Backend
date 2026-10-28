"""
Registre d'auditoria (art. 32 RGPD / DSA) a PostgreSQL: `audit.audit_logs` (docs/design/postgres-schema.md §2.24).

Substitueix `api/services/audit_log_service.py` (Firestore) amb la mateixa signatura: `audit_log_service.log(actor_uid,
action, target_type=None, target_id=None, metadata=None) -> bool`.

- **Mai trenca el flux de negoci**: l'`INSERT` va dins un *savepoint* i qualsevol error (CHECK, FK, RLS, BD caiguda)
  es registra al log i retorna `False`; la transacció del cridant continua viva. Les FK són diferides: dins el
  *savepoint* es fan immediates perquè la violació surti allà i no al `COMMIT` de la petició.
- Actor `'system'`/`None`/`''` -> `actor_uid` NULL, escrit amb un `system_context()` acotat a aquesta sentència (la RLS
  només deixa escriure com a «sistema» amb `{SYS}`). Un actor que no és el del context de RLS no es pot falsificar.
- L'usuari afectat (`target_type == 'user'`) va a `subject_uid` (FK `CASCADE`), no a `target_id` ni a `metadata`.
- `legal_hold` (CSAM) es deriva de l'acció i les metadades: la fila no cau amb l'usuari (es desvincula) i es conserva
  5 anys en lloc de 365 dies. El registre és immutable (`app` no té `UPDATE`): el `legal_hold` no és retroactiu.
- No s'hi han de posar dades personals innecessàries (ni UID a `metadata`, ni bytes, ni URLs, ni dates de naixement).
"""
import json
import logging
from contextlib import nullcontext
from typing import Any, Dict, Optional

from django.db import connection, transaction

from apps.core.rls import system_context

logger = logging.getLogger(__name__)

AUDIT_RETENTION_DAYS = 365
LEGAL_HOLD_RETENTION_DAYS = 1826        # 5 anys (decisió N2, pendent d'assessorament legal)
SYSTEM_ACTOR = 'system'

TARGET_TYPE_MAX = 32
TARGET_ID_MAX = 500
UID_MAX = 128

# Accions registrades
ACTION_UPLOAD_INTENT = 'media.upload_intent'
ACTION_UPLOAD_CONFIRM = 'media.upload_confirm'
ACTION_MEDIA_DELETE = 'media.delete'
ACTION_MEDIA_LIST = 'media.list'
ACTION_REPORT_CREATE = 'media.report'
ACTION_MODERATION_RESOLVE = 'moderation.resolve'
ACTION_MODERATION_AUTO_HIDE = 'moderation.auto_hide'
ACTION_MODERATION_HASH_BLOCK = 'moderation.hash_block'
ACTION_USER_BLOCKED = 'moderation.user_blocked'
ACTION_REPORTS_LIST = 'moderation.reports_list'
ACTION_AVATAR_UPLOAD = 'avatar.upload'
ACTION_AGE_CONFIRMED = 'user.age_confirmed'
ACTION_USER_DELETED = 'user.deleted'

_CSAM_BLOCK_REASONS = ('csam_confirmed', 'moderation_hash_match')

# Les FK són `DEFERRABLE INITIALLY DEFERRED`: aquí es fan immediates (només les d'aquesta taula).
_IMMEDIATE_SQL = 'SET CONSTRAINTS audit.audit_logs_actor_uid_fk, audit.audit_logs_subject_uid_fk IMMEDIATE'
# `SET CONSTRAINTS` no es desfà en sortir del savepoint: es retorna l'estat diferit perquè el `log` no canviï la
# semàntica de les FK d'aquesta taula per a la resta de la transacció del cridant.
_DEFERRED_SQL = _IMMEDIATE_SQL.replace(' IMMEDIATE', ' DEFERRED')
_INSERT_SQL = (
    'INSERT INTO audit.audit_logs (actor_uid, subject_uid, action, target_type, target_id, metadata, legal_hold, '
    'expire_at) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, now() + make_interval(days => %s))')
# `expire_at < now()` de les files normals va per l'índex parcial `(expire_at) WHERE NOT legal_hold`; les `legal_hold`
# (poques) caduquen als 5 anys amb una segona passada. Sense `FOR UPDATE`: `app` no té `UPDATE` sobre la taula. Dues
# sentències per lot (ids + `DELETE ... = ANY`) perquè el planificador no triï un pla quadràtic amb estadístiques velles.
_SELECT_SQL = 'SELECT id FROM audit.audit_logs WHERE expire_at < now() AND {hold} ORDER BY expire_at LIMIT %s'
_DELETE_SQL = 'DELETE FROM audit.audit_logs WHERE id = ANY(%s)'


def is_legal_hold(action: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Si l'entrada és evidència CSAM (conservació de 5 anys i desvinculació en esborrar l'usuari)."""
    meta = metadata if isinstance(metadata, dict) else {}
    if action == ACTION_MODERATION_HASH_BLOCK:
        return True
    if action == ACTION_USER_BLOCKED:
        return meta.get('reason') in _CSAM_BLOCK_REASONS
    if action == ACTION_MODERATION_RESOLVE:
        return meta.get('csam') is True
    if action == ACTION_REPORT_CREATE:
        return meta.get('reason') == 'child_sexual_abuse'
    return False


class AuditLogService:
    """Servei d'escriptura del registre d'auditoria"""

    def log(self, actor_uid: Optional[str], action: str, target_type: Optional[str] = None,
            target_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Escriu una entrada d'auditoria. Retorna `True` si s'ha escrit; mai llança ni avorta la transacció del cridant.
        """
        try:
            is_system = actor_uid in (None, '', SYSTEM_ACTOR)
            legal_hold = is_legal_hold(action, metadata)
            subject_uid = None
            if target_type == 'user':
                subject_uid, target_id = (str(target_id)[:UID_MAX] if target_id else None), None
            params = [
                None if is_system else actor_uid, subject_uid, action,
                target_type[:TARGET_TYPE_MAX] if target_type else None,
                str(target_id)[:TARGET_ID_MAX] if target_id is not None else None,
                json.dumps({} if metadata is None else metadata, default=str), legal_hold,
                LEGAL_HOLD_RETENTION_DAYS if legal_hold else AUDIT_RETENTION_DAYS]
            with system_context() if is_system else nullcontext():
                with transaction.atomic():
                    with connection.cursor() as cur:
                        cur.execute(_IMMEDIATE_SQL)
                        cur.execute(_INSERT_SQL, params)
                        cur.execute(_DEFERRED_SQL)
            return True
        except Exception:
            logger.exception("No s'ha pogut escriure l'entrada d'auditoria %s", action)
            return False


audit_log_service = AuditLogService()


def purge_expired(batch_size: int = 5000) -> int:
    """
    Esborra les entrades caducades (`expire_at < now()`) en lots de `batch_size`; retorna quantes. És un job: obre el
    seu `system_context()` (un per lot, perquè cada lot sigui una transacció curta). Les files `legal_hold` porten
    `expire_at = created_at + 5 anys`, de manera que no caduquen abans.
    """
    total = 0
    for hold in ('NOT legal_hold', 'legal_hold'):
        select_sql = _SELECT_SQL.format(hold=hold)
        while True:
            with system_context():
                with connection.cursor() as cur:
                    cur.execute(select_sql, [batch_size])
                    ids = [row[0] for row in cur.fetchall()]
                    if ids:
                        cur.execute(_DELETE_SQL, [ids])
            total += len(ids)
            if len(ids) < batch_size:
                break
    return total
