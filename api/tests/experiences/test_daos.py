"""
Tests per al DAO d'experiències
"""
import pytest
from unittest.mock import MagicMock, patch, call
from api.daos.experience_dao import ExperienceDAO
from api.models.experience import Experience

@pytest.mark.daos
class TestExperienceDAO:
    """Tests per a ExperienceDAO"""
    
    @pytest.fixture
    def mock_firestore_class(self):
        with patch('api.daos.experience_dao.FirestoreService') as mock:
            yield mock

    @pytest.fixture
    def mock_db(self, mock_firestore_class):
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        return mock_db

    @pytest.fixture
    def mock_cache(self):
        with patch('api.daos.experience_dao.cache_service') as mock:
            yield mock
            
    @pytest.fixture
    def mock_r2(self):
        with patch('api.models.experience.r2_media_service.get_refugi_media_service') as mock:
            yield mock

    @pytest.fixture
    def dao(self, mock_firestore_class, mock_cache, mock_r2):
        return ExperienceDAO()
    
    def test_create_experience_success(self, dao, mock_db, mock_cache):
        """Test creació d'experiència exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "exp_123"
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        exp_data = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test',
            'modified_at': '2024-01-01'
        }
        
        result = dao.create_experience(exp_data)
        
        assert result is not None
        assert result.id == "exp_123"
        mock_doc_ref.set.assert_called()
        mock_cache.delete_pattern.assert_called()

    def test_get_experience_by_id_found(self, dao, mock_db, mock_cache):
        """Test obtenció d'experiència existent"""
        mock_cache.get.return_value = None
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = "exp_123"
        mock_doc.to_dict.return_value = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test',
            'modified_at': '2024-01-01'
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_experience_by_id("exp_123")
        
        assert result is not None
        assert result.id == "exp_123"
        mock_cache.set.assert_called()

    def test_update_experience_success(self, dao, mock_db, mock_cache):
        """Test actualització d'experiència exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.update_experience("exp_123", {'comment': 'Updated'})
        
        assert success is True
        assert error is None
        mock_doc_ref.update.assert_called_with({'comment': 'Updated'})

    @patch('api.daos.experience_dao.ArrayUnion')
    def test_update_experience_with_media_keys(self, mock_union, dao, mock_db):
        """Test actualització d'experiència amb media_keys (ArrayUnion)"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        dao.update_experience("exp_123", {'media_keys': ['key1']})
        
        mock_union.assert_called_with(['key1'])
        mock_doc_ref.update.assert_called()

    def test_delete_experience_success(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiència exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refuge_id': 'ref_1'}
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.delete_experience("exp_123")
        
        assert success is True
        mock_doc_ref.delete.assert_called()
        mock_cache.delete_pattern.assert_called()

    def test_remove_media_key_success(self, dao, mock_db):
        """Test eliminació de media key d'experiència"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        with patch('google.cloud.firestore.ArrayRemove') as mock_remove:
            success, error = dao.remove_media_key("exp_123", "key1")
            assert success is True
            mock_doc_ref.update.assert_called()
            mock_remove.assert_called()
