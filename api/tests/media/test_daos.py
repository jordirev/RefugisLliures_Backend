"""
Tests dels DAOs nous (upload_intents, media_reports, moderation_notices) i de les escriptures
atòmiques de media_metadata a RefugiLliureDAO.
"""
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as gcloud_exceptions
from google.cloud.firestore import DELETE_FIELD

from api.daos.media_report_dao import MediaReportDAO, DUPLICATE_REPORT_ERROR
from api.daos.moderation_notice_dao import ModerationNoticeDAO
from api.daos.refugi_lliure_dao import RefugiLliureDAO
from api.models.media_report import MediaReport

KEY = 'refugis-lliures/ref_1/abc-1.webp'
FIELD = 'media_metadata.`refugis-lliures/ref_1/abc-1.webp`'


def doc(data, exists=True, doc_id='d'):
    d = MagicMock()
    d.exists = exists
    d.id = doc_id
    d.to_dict.return_value = data
    return d


@pytest.mark.daos
class TestMediaReportDAO:
    def report(self, **kw):
        data = dict(id='r1', refuge_id='ref_1', media_key=KEY, reporter_uid='u1', reason='hate_speech',
                    created_at='2025-01-02')
        data.update(kw)
        return MediaReport(**data)

    @patch('api.daos.media_report_dao.FirestoreService')
    def test_create_and_duplicate(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        dao = MediaReportDAO()
        assert dao.create_report(self.report()) == (True, None)
        db.collection.return_value.document.return_value.create.assert_called_once()

        db.collection.return_value.document.return_value.create.side_effect = gcloud_exceptions.AlreadyExists('x')
        assert dao.create_report(self.report()) == (False, DUPLICATE_REPORT_ERROR)
        db.collection.return_value.document.return_value.create.side_effect = Exception('boom')
        assert dao.create_report(self.report())[0] is False

    @patch('api.daos.media_report_dao.FirestoreService')
    def test_list_sorted_by_priority_then_date(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        docs = [
            doc(self.report(id='a', created_at='2025-01-03').to_dict(), doc_id='a'),
            doc(self.report(id='b', created_at='2025-01-05', priority='high').to_dict(), doc_id='b'),
            doc(self.report(id='c', created_at='2025-01-01').to_dict(), doc_id='c'),
            doc({'reason': 'invalid'}, doc_id='bad'),
        ]
        db.collection.return_value.where.return_value.stream.return_value = docs
        assert [r.id for r in MediaReportDAO().list_reports('pending')] == ['b', 'c', 'a']

    @patch('api.daos.media_report_dao.FirestoreService')
    def test_count_distinct_reporters(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        query = db.collection.return_value.where.return_value.where.return_value.where.return_value
        query.stream.return_value = [
            doc(self.report(id='a', reporter_uid='u1').to_dict(), doc_id='a'),
            doc(self.report(id='b', reporter_uid='u2').to_dict(), doc_id='b'),
            doc(self.report(id='c', reporter_uid='u2').to_dict(), doc_id='c'),
        ]
        assert MediaReportDAO().count_distinct_pending_reporters('ref_1', KEY) == 2

    @patch('api.daos.media_report_dao.FirestoreService')
    def test_get_and_resolve(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        dao = MediaReportDAO()
        db.collection.return_value.document.return_value.get.return_value = doc(self.report().to_dict(), doc_id='r1')
        assert dao.get_report('r1').id == 'r1'
        db.collection.return_value.document.return_value.get.return_value = doc(None, exists=False)
        assert dao.get_report('r1') is None
        assert dao.resolve_reports(['a', 'b'], {'status': 'resolved'}) is True
        assert db.batch.return_value.update.call_count == 2
        db.batch.return_value.commit.side_effect = Exception('x')
        assert dao.resolve_reports(['a'], {}) is False


@pytest.mark.daos
class TestModerationNoticeDAO:
    @patch('api.daos.moderation_notice_dao.FirestoreService')
    def test_create_and_list(self, mock_fs):
        db = mock_fs.return_value.get_db.return_value
        db.collection.return_value.document.return_value.id = 'n1'
        dao = ModerationNoticeDAO()
        notice = dao.create_notice({'uid': 'u', 'type': 'strike', 'statement': 's', 'created_at': '2025'})
        assert notice.id == 'n1'
        saved = db.collection.return_value.document.return_value.set.call_args.args[0]
        assert 'redress' not in saved and saved['uid'] == 'u'

        db.collection.return_value.where.return_value.stream.return_value = [
            doc({'uid': 'u', 'type': 'strike', 'statement': 'a', 'created_at': '2025-01-01'}, doc_id='old'),
            doc({'uid': 'u', 'type': 'content_removed', 'statement': 'b', 'created_at': '2025-02-01'}, doc_id='new'),
        ]
        assert [n.id for n in dao.list_by_uid('u')] == ['new', 'old']

    @patch('api.daos.moderation_notice_dao.FirestoreService')
    def test_create_invalid(self, mock_fs):
        assert ModerationNoticeDAO().create_notice({'uid': 'u', 'type': 'nope', 'statement': 's'}) is None


@pytest.mark.daos
class TestRefugiMediaAtomicWrites:
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_uses_field_path_not_whole_map(self, mock_cache, mock_fs):
        db = mock_fs.get_db.return_value
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc({'media_metadata': {'other': {}}})
        assert RefugiLliureDAO().add_media_metadata('ref_1', {KEY: {'creator_uid': 'u'}}) is True
        doc_ref.update.assert_called_once_with({FIELD: {'creator_uid': 'u'}})

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_uses_delete_field(self, mock_cache, mock_fs):
        db = mock_fs.get_db.return_value
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc({'media_metadata': {KEY: {'creator_uid': 'u'}, 'other': {}}})
        success, backup = RefugiLliureDAO().delete_media_metadata('ref_1', KEY)
        assert success and backup == {'creator_uid': 'u'}
        doc_ref.update.assert_called_once_with({FIELD: DELETE_FIELD})

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_multiple_uses_delete_field(self, mock_cache, mock_fs):
        db = mock_fs.get_db.return_value
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc({'media_metadata': {KEY: {'creator_uid': 'u'}}})
        success, backup = RefugiLliureDAO().delete_multiple_media_metadata('ref_1', [KEY, 'missing'])
        assert success and backup == [{'creator_uid': 'u', 'key': KEY}]
        doc_ref.update.assert_called_once_with({FIELD: DELETE_FIELD})

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_update_status(self, mock_cache, mock_fs):
        db = mock_fs.get_db.return_value
        doc_ref = db.collection.return_value.document.return_value
        doc_ref.get.return_value = doc({'media_metadata': {KEY: {'creator_uid': 'u'}}})
        dao = RefugiLliureDAO()
        assert dao.update_media_status('ref_1', KEY, 'hidden_pending_review', only_if_status=['visible']) is True
        doc_ref.update.assert_called_once_with({FIELD + '.status': 'hidden_pending_review'})
        mock_cache.delete.assert_called()

        doc_ref.get.return_value = doc({'media_metadata': {KEY: {'status': 'removed'}}})
        assert dao.update_media_status('ref_1', KEY, 'hidden_pending_review', only_if_status=['visible']) is False
        assert dao.update_media_status('ref_1', KEY, 'removed') is False  # ja ho està
        assert dao.update_media_status('ref_1', 'missing', 'removed') is False
        doc_ref.get.return_value = doc(None, exists=False)
        assert dao.update_media_status('ref_1', KEY, 'removed') is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_raw_metadata_cache_first(self, mock_cache, mock_fs):
        mock_cache.get.return_value = {'media_metadata': {KEY: {}}}
        assert RefugiLliureDAO().get_raw_media_metadata('ref_1') == {KEY: {}}
        mock_fs.get_db.assert_not_called()
        mock_cache.get.return_value = None
        mock_fs.get_db.return_value.collection.return_value.document.return_value.get.return_value = doc(None, exists=False)
        assert RefugiLliureDAO().get_raw_media_metadata('ref_1') is None
