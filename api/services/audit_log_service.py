"""
AuditLogService - Registre d'auditoria (art. 32 RGPD / DSA).

Escriu a la col·lecció `audit_logs`:
    {actor_uid, action, target_type, target_id, metadata, timestamp (ISO), expire_at (datetime)}

`expire_at` és un Timestamp (no string) perquè la política TTL de Firestore el pugui
usar: cal crear la política TTL sobre `audit_logs.expire_at` a la consola (12 mesos).

El registre MAI ha de trencar el flux de negoci: qualsevol error es registra al log i
s'ignora.
"""
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from .firestore_service import FirestoreService
from ..utils.timezone_utils import get_madrid_now

logger = logging.getLogger(__name__)

AUDIT_RETENTION_DAYS = 365

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


class AuditLogService:
    """Servei d'escriptura del registre d'auditoria"""

    COLLECTION_NAME = 'audit_logs'

    def __init__(self):
        self.firestore_service = FirestoreService()

    def log(self, actor_uid: Optional[str], action: str, target_type: Optional[str] = None,
            target_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Escriu una entrada d'auditoria. Retorna True si s'ha escrit; mai llança.
        No s'hi han de posar dades personals innecessàries (ni bytes, ni URLs, ni dates de naixement).
        """
        try:
            now = get_madrid_now()
            entry = {
                'actor_uid': actor_uid or 'system',
                'action': action,
                'target_type': target_type,
                'target_id': target_id,
                'metadata': metadata or {},
                'timestamp': now.isoformat(),
                'expire_at': now + timedelta(days=AUDIT_RETENTION_DAYS),
            }
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore WRITE: collection={self.COLLECTION_NAME} action={action}")
            db.collection(self.COLLECTION_NAME).add(entry)
            return True
        except Exception as e:
            logger.error(f"No s'ha pogut escriure l'entrada d'auditoria {action}: {str(e)}")
            return False


audit_log_service = AuditLogService()
