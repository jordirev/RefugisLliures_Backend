"""
DAO per als intents de pujada directa (col·lecció `upload_intents`)
"""
import logging
from typing import List, Optional

from ..services.firestore_service import FirestoreService
from ..models.upload_intent import (
    UploadIntent, INTENT_STATUS_CONFIRMED, INTENT_STATUS_FAILED,
)

logger = logging.getLogger(__name__)


class UploadIntentDAO:
    """Data Access Object per a upload_intents (sense cache: són d'un sol ús)"""

    COLLECTION_NAME = 'upload_intents'

    def __init__(self):
        self.firestore_service = FirestoreService()

    def new_id(self) -> str:
        """Genera un auto-ID de Firestore per a un nou intent"""
        db = self.firestore_service.get_db()
        return db.collection(self.COLLECTION_NAME).document().id

    def create_intents(self, intents: List[UploadIntent]) -> bool:
        """Desa diversos intents en un sol batch"""
        try:
            db = self.firestore_service.get_db()
            batch = db.batch()
            for intent in intents:
                doc_ref = db.collection(self.COLLECTION_NAME).document(intent.id)
                batch.set(doc_ref, intent.to_dict())
            logger.log(23, f"Firestore WRITE (batch): collection={self.COLLECTION_NAME} count={len(intents)}")
            batch.commit()
            return True
        except Exception as e:
            logger.error(f"Error creant upload_intents: {str(e)}")
            return False

    def get_intent(self, intent_id: str) -> Optional[UploadIntent]:
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={intent_id}")
            doc = db.collection(self.COLLECTION_NAME).document(intent_id).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            data['id'] = doc.id
            return UploadIntent.from_dict(data)
        except Exception as e:
            logger.error(f"Error obtenint upload_intent {intent_id}: {str(e)}")
            return None

    def _update(self, intent_id: str, data: dict) -> bool:
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore UPDATE: collection={self.COLLECTION_NAME} document={intent_id}")
            db.collection(self.COLLECTION_NAME).document(intent_id).update(data)
            return True
        except Exception as e:
            logger.error(f"Error actualitzant upload_intent {intent_id}: {str(e)}")
            return False

    def mark_confirmed(self, intent_id: str, result_key: str) -> bool:
        return self._update(intent_id, {'status': INTENT_STATUS_CONFIRMED, 'result_key': result_key})

    def mark_failed(self, intent_id: str, reason: str) -> bool:
        return self._update(intent_id, {'status': INTENT_STATUS_FAILED, 'failure_reason': reason})
