"""
DAO per a les denúncies de mitjans (col·lecció `media_reports`)
"""
import logging
from typing import List, Optional, Tuple

from google.api_core import exceptions as gcloud_exceptions

from ..services.firestore_service import FirestoreService
from ..models.media_report import MediaReport, REPORT_STATUS_PENDING, REPORT_PRIORITY_HIGH

logger = logging.getLogger(__name__)

DUPLICATE_REPORT_ERROR = 'duplicate'


class MediaReportDAO:
    """Data Access Object per a media_reports (sense cache: dades de moderació)"""

    COLLECTION_NAME = 'media_reports'

    def __init__(self):
        self.firestore_service = FirestoreService()

    def create_report(self, report: MediaReport) -> Tuple[bool, Optional[str]]:
        """
        Crea la denúncia amb `create()` (falla si ja existeix → duplicat atòmic).
        Returns: (creada, error) amb error == 'duplicate' si ja existia.
        """
        try:
            db = self.firestore_service.get_db()
            doc_ref = db.collection(self.COLLECTION_NAME).document(report.id)
            logger.log(23, f"Firestore CREATE: collection={self.COLLECTION_NAME} document={report.id}")
            doc_ref.create(report.to_dict())
            return True, None
        except gcloud_exceptions.AlreadyExists:
            return False, DUPLICATE_REPORT_ERROR
        except gcloud_exceptions.Conflict:
            return False, DUPLICATE_REPORT_ERROR
        except Exception as e:
            logger.error(f"Error creant media_report: {str(e)}")
            return False, str(e)

    def get_report(self, report_id: str) -> Optional[MediaReport]:
        try:
            db = self.firestore_service.get_db()
            logger.log(23, f"Firestore READ: collection={self.COLLECTION_NAME} document={report_id}")
            doc = db.collection(self.COLLECTION_NAME).document(report_id).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            data['id'] = doc.id
            return MediaReport.from_dict(data)
        except Exception as e:
            logger.error(f"Error obtenint media_report {report_id}: {str(e)}")
            return None

    def list_reports(self, status: str) -> List[MediaReport]:
        """
        Llista denúncies per status, ordenades per prioritat (high primer) i data.
        S'ordena en Python per evitar un índex compost.
        """
        db = self.firestore_service.get_db()
        logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where status=={status}")
        docs = db.collection(self.COLLECTION_NAME).where('status', '==', status).stream()
        reports = []
        for doc in docs:
            data = doc.to_dict() or {}
            data['id'] = doc.id
            try:
                reports.append(MediaReport.from_dict(data))
            except ValueError as e:
                logger.warning(f"Denúncia {doc.id} invàlida, s'ignora: {e}")
        reports.sort(key=lambda r: r.created_at or '')
        reports.sort(key=lambda r: 0 if r.priority == REPORT_PRIORITY_HIGH else 1)
        return reports

    def list_reports_for_media(self, refuge_id: str, media_key: str,
                               status: Optional[str] = None) -> List[MediaReport]:
        """Denúncies d'un mitjà (opcionalment filtrades per status). Només igualtats: sense índex compost."""
        db = self.firestore_service.get_db()
        query = db.collection(self.COLLECTION_NAME) \
            .where('refuge_id', '==', refuge_id) \
            .where('media_key', '==', media_key)
        if status:
            query = query.where('status', '==', status)
        logger.log(23, f"Firestore QUERY: collection={self.COLLECTION_NAME} where refuge_id,media_key")
        reports = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            data['id'] = doc.id
            try:
                reports.append(MediaReport.from_dict(data))
            except ValueError:
                continue
        return reports

    def count_distinct_pending_reporters(self, refuge_id: str, media_key: str) -> int:
        reports = self.list_reports_for_media(refuge_id, media_key, REPORT_STATUS_PENDING)
        return len({r.reporter_uid for r in reports})

    def resolve_reports(self, report_ids: List[str], updates: dict) -> bool:
        """Marca diverses denúncies com a resoltes en un batch"""
        try:
            db = self.firestore_service.get_db()
            batch = db.batch()
            for report_id in report_ids:
                batch.update(db.collection(self.COLLECTION_NAME).document(report_id), updates)
            logger.log(23, f"Firestore UPDATE (batch): collection={self.COLLECTION_NAME} count={len(report_ids)}")
            batch.commit()
            return True
        except Exception as e:
            logger.error(f"Error resolent media_reports: {str(e)}")
            return False
