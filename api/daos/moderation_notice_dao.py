"""
DAO per als avisos de moderació (col·lecció `moderation_notices`)
"""
import logging
from typing import Any, Dict, List, Optional

from ..services.firestore_service import FirestoreService
from ..models.moderation_notice import ModerationNotice

logger = logging.getLogger(__name__)


class ModerationNoticeDAO:
    """Data Access Object per a moderation_notices"""

    COLLECTION_NAME = 'moderation_notices'

    def __init__(self):
        self.firestore_service = FirestoreService()

    def create_notice(self, notice_data: Dict[str, Any]) -> Optional[ModerationNotice]:
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document()
            notice_data = dict(notice_data)
            notice_data['id'] = doc_ref.id
            notice = ModerationNotice.from_dict(notice_data)
            data = notice.to_dict()
            data.pop('redress', None)
            logger.log(23, f"Firestore WRITE: collection={self.COLLECTION_NAME} document={doc_ref.id}")
            doc_ref.set(data)
            return notice
        except Exception as e:
            logger.error(f"Error creant moderation_notice: {str(e)}")
            return None

    def list_by_uid(self, uid: str) -> List[ModerationNotice]:
        """Avisos d'un usuari, més recents primer (ordenació en Python, sense índex compost)"""
        db = self.firestore_service.get_db()
        logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where uid=={uid}")
        notices = []
        for doc in db.collection(self.COLLECTION_NAME).where('uid', '==', uid).stream():
            data = doc.to_dict() or {}
            data['id'] = doc.id
            try:
                notices.append(ModerationNotice.from_dict(data))
            except ValueError:
                continue
        notices.sort(key=lambda n: n.created_at or '', reverse=True)
        return notices
