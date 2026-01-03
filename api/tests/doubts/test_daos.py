"""
Tests per al DAO de dubtes
"""
import pytest
from unittest.mock import MagicMock, patch, call
from api.daos.doubt_dao import DoubtDAO
from api.models.doubt import Doubt, Answer

@pytest.mark.daos
class TestDoubtDAO:
    """Tests per a DoubtDAO"""
    
    @pytest.fixture
    def mock_firestore_class(self):
        with patch('api.daos.doubt_dao.FirestoreService') as mock:
            yield mock

    @pytest.fixture
    def mock_db(self, mock_firestore_class):
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        return mock_db

    @pytest.fixture
    def mock_cache(self):
        with patch('api.daos.doubt_dao.cache_service') as mock:
            yield mock
            
    @pytest.fixture
    def mock_increment(self):
        with patch('api.daos.doubt_dao.Increment') as mock:
            yield mock

    @pytest.fixture
    def dao(self, mock_firestore_class, mock_cache, mock_increment):
        return DoubtDAO()
    
    def test_create_doubt_success(self, dao, mock_db, mock_cache):
        """Test creació de dubte exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "doubt_123"
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        doubt_data = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01'
        }
        
        result = dao.create_doubt(doubt_data)
        
        assert result is not None
        assert isinstance(result, Doubt)
        assert result.id == "doubt_123"
        mock_doc_ref.set.assert_called()
        mock_cache.delete_pattern.assert_called_with("doubt_list:refuge_id:ref_1")

    def test_get_doubt_by_id_found(self, dao, mock_db, mock_cache):
        """Test obtenció de dubte existent"""
        mock_cache.get.return_value = None
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = "doubt_123"
        mock_doc.to_dict.return_value = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'message': 'Test',
            'created_at': '2024-01-01',
            'answers_count': 0
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_doubt_by_id("doubt_123")
        
        assert result is not None
        assert result.id == "doubt_123"
        mock_cache.set.assert_called()

    def test_get_doubts_by_refuge_id(self, dao, mock_db, mock_cache):
        """Test obtenció de dubtes per refugi"""
        mock_cache.get_or_fetch_list.return_value = [
            {
                'id': 'doubt_1',
                'refuge_id': 'ref_1',
                'creator_uid': 'user_1',
                'message': 'Test',
                'created_at': '2024-01-01',
                'answers': [{'id': 'ans_1', 'creator_uid': 'user_2', 'message': 'Reply', 'created_at': '2024-01-02'}]
            }
        ]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        result = dao.get_doubts_by_refuge_id("ref_1")
        
        assert len(result) == 1
        assert result[0].id == "doubt_1"
        assert len(result[0].answers) == 1

    def test_create_answer_success(self, dao, mock_db, mock_cache, mock_increment):
        """Test creació de resposta exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "ans_1"
        
        # Mock subcollection document creation
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
        
        answer_data = {
            'creator_uid': 'user_2',
            'message': 'Reply',
            'created_at': '2024-01-02'
        }
        
        # Mock get_doubt_by_id per invalidar cache
        with patch.object(dao, 'get_doubt_by_id') as mock_get_doubt:
            mock_get_doubt.return_value = Doubt(id="doubt_1", refuge_id="ref_1", creator_uid="u", message="m", created_at="d")
            
            result = dao.create_answer("doubt_1", answer_data)
            
            assert result is not None
            assert result.id == "ans_1"
            mock_doc_ref.set.assert_called()
            # Verificar increment
            mock_db.collection.return_value.document.return_value.update.assert_called()

    def test_delete_doubt_success(self, dao, mock_db, mock_cache):
        """Test eliminació de dubte exitosa"""
        # Mock answers stream
        mock_answer_doc = MagicMock()
        mock_answer_doc.id = "ans_1"
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_answer_doc]
        
        # Mock get_doubt_by_id per invalidar cache
        with patch.object(dao, 'get_doubt_by_id') as mock_get_doubt:
            mock_get_doubt.return_value = Doubt(id="doubt_1", refuge_id="ref_1", creator_uid="u", message="m", created_at="d")
            
            result = dao.delete_doubt("doubt_1")
            
            assert result is True
            # Verificar eliminació de respostes
            mock_answer_doc.reference.delete.assert_called()
            # Verificar eliminació de dubte
            mock_db.collection.return_value.document.return_value.delete.assert_called()
