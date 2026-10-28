"""
Tests de les escriptures
atòmiques de media_metadata a RefugiLliureDAO.
"""
from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as gcloud_exceptions
from google.cloud.firestore import DELETE_FIELD

from api.daos.refugi_lliure_dao import RefugiLliureDAO

KEY = 'refugis-lliures/ref_1/abc-1.webp'
FIELD = 'media_metadata.`refugis-lliures/ref_1/abc-1.webp`'


def doc(data, exists=True, doc_id='d'):
    d = MagicMock()
    d.exists = exists
    d.id = doc_id
    d.to_dict.return_value = data
    return d


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
