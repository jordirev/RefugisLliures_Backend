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

class TestDoubtDAOExtended:
    """Tests per a DoubtDAO cobrint casos d'error i mètodes restants"""

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_create_doubt_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a create_doubt"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        res = dao.create_doubt({'refuge_id': 'r1'})
        assert res is None

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubt_by_id_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a get_doubt_by_id"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        res = dao.get_doubt_by_id("d1")
        assert res is None

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubts_by_refuge_id_cache_hit(self, mock_cache, mock_firestore_class):
        """Test get_doubts_by_refuge_id amb cache hit"""
        mock_cache.get_or_fetch_list.return_value = [
            {
                'id': 'd1', 
                'refuge_id': 'r1', 
                'creator_uid': 'u1', 
                'message': 'msg', 
                'created_at': '2024-01-01',
                'answers': [
                    {
                        'id': 'a1', 
                        'creator_uid': 'u2', 
                        'message': 'ans', 
                        'created_at': '2024-01-02'
                    }
                ]
            }
        ]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        dao = DoubtDAO()
        res = dao.get_doubts_by_refuge_id("r1")
        assert len(res) == 1
        assert res[0].id == 'd1'
        assert len(res[0].answers) == 1

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubts_by_refuge_id_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a get_doubts_by_refuge_id"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        res = dao.get_doubts_by_refuge_id("r1")
        assert res == []

    @patch('api.daos.doubt_dao.FirestoreService')
    def test_get_answers_by_doubt_id_exception(self, mock_firestore_class):
        """Test excepció a _get_answers_by_doubt_id"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        res = dao._get_answers_by_doubt_id("d1")
        assert res == []

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_create_answer_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a create_answer"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        res = dao.create_answer("d1", {})
        assert res is None

    @patch('api.daos.doubt_dao.FirestoreService')
    def test_get_answer_by_id_errors(self, mock_firestore_class):
        """Test errors a get_answer_by_id"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = DoubtDAO()
        assert dao.get_answer_by_id("d1", "a1") is None
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.get_answer_by_id("d1", "a1") is None

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answer_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a delete_answer"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        assert dao.delete_answer("d1", "a1") is False

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_doubt_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a delete_doubt"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        assert dao.delete_doubt("d1") is False

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_invalidate_doubt_cache_errors(self, mock_cache, mock_firestore_class):
        """Test errors a _invalidate_doubt_cache"""
        dao = DoubtDAO()
        
        # Doubt not found - should still invalidate detail cache
        with patch.object(dao, 'get_doubt_by_id', return_value=None):
            dao._invalidate_doubt_cache("d1")
            # Should have called delete for detail cache via _invalidate_doubt_detail_cache
            mock_cache.delete.assert_called()
            
        # Exception
        with patch.object(dao, 'get_doubt_by_id', side_effect=Exception("Error")):
            dao._invalidate_doubt_cache("d1")
            # Should log error and continue

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_doubts_by_creator_success(self, mock_cache, mock_firestore_class):
        """Test delete_doubts_by_creator èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_doubt = MagicMock()
        mock_doubt.to_dict.return_value = {'refuge_id': 'r1'}
        mock_doubt.id = 'd1'
        
        mock_answer = MagicMock()
        mock_answer.id = 'a1'
        
        mock_db.collection.return_value.where.return_value.stream.return_value = [mock_doubt]
        mock_doubt.reference.collection.return_value.stream.return_value = [mock_answer]
        
        dao = DoubtDAO()
        success, error = dao.delete_doubts_by_creator("u1")
        
        assert success is True
        assert error is None
        mock_doubt.reference.delete.assert_called()
        mock_answer.reference.delete.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_doubts_by_creator_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a delete_doubts_by_creator"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        success, error = dao.delete_doubts_by_creator("u1")
        assert success is False
        assert "DB Error" in error

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answers_by_creator_success(self, mock_cache, mock_firestore_class):
        """Test delete_answers_by_creator èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_answer = MagicMock()
        mock_answer.id = 'a1'
        mock_answer.reference.parent.parent.id = 'd1'
        
        mock_db.collection_group.return_value.where.return_value.stream.return_value = [mock_answer]
        
        mock_doubt_doc = MagicMock()
        mock_doubt_doc.exists = True
        mock_doubt_doc.to_dict.return_value = {'refuge_id': 'r1'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doubt_doc
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = []
        
        dao = DoubtDAO()
        success, error = dao.delete_answers_by_creator("u1")
        
        assert success is True
        assert error is None
        mock_answer.reference.delete.assert_called()
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'answers_count': 0})

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answers_by_creator_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a delete_answers_by_creator"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection_group.side_effect = Exception("DB Error")
        
        dao = DoubtDAO()
        success, error = dao.delete_answers_by_creator("u1")
        assert success is False
        assert "DB Error" in error

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubts_by_refuge_id_success(self, mock_cache, mock_firestore_class):
        """Test get_doubts_by_refuge_id èxit"""
        mock_cache.get_or_fetch_list.return_value = [
            {
                'id': 'd1', 
                'refuge_id': 'r1', 
                'creator_uid': 'u1', 
                'message': 'm', 
                'created_at': 'now',
                'answers': [
                    {
                        'id': 'a1', 
                        'creator_uid': 'u2', 
                        'message': 'ans', 
                        'created_at': 'now'
                    }
                ]
            }
        ]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        dao = DoubtDAO()
        res = dao.get_doubts_by_refuge_id("r1")
        assert len(res) == 1
        assert res[0].id == 'd1'
        assert len(res[0].answers) == 1

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_create_answer_success(self, mock_cache, mock_firestore_class):
        """Test create_answer èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = DoubtDAO()
        with patch.object(dao, 'get_doubt_by_id') as mock_get:
            mock_get.return_value = MagicMock(refuge_id='r1')
            res = dao.create_answer("d1", {
                'id': 'a1', 'creator_uid': 'u1', 'message': 'm', 'created_at': 'now'
            })
            assert res is not None
            mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    def test_get_answer_by_id_success(self, mock_firestore_class):
        """Test get_answer_by_id èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = 'a1'
        mock_doc.to_dict.return_value = {
            'id': 'a1', 'creator_uid': 'u1', 'message': 'm', 'created_at': 'now'
        }
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = DoubtDAO()
        res = dao.get_answer_by_id("d1", "a1")
        assert res.id == 'a1'

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answer_success(self, mock_cache, mock_firestore_class):
        """Test delete_answer èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = DoubtDAO()
        with patch.object(dao, 'get_doubt_by_id') as mock_get:
            mock_get.return_value = MagicMock(refuge_id='r1')
            assert dao.delete_answer("d1", "a1") is True
            mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_doubt_success(self, mock_cache, mock_firestore_class):
        """Test delete_doubt èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_answer_doc = MagicMock()
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = [mock_answer_doc]
        
        dao = DoubtDAO()
        with patch.object(dao, 'get_doubt_by_id') as mock_get:
            mock_get.return_value = MagicMock(refuge_id='r1')
            assert dao.delete_doubt("d1") is True
            mock_db.collection.return_value.document.return_value.delete.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubt_by_id_success(self, mock_cache, mock_firestore_class):
        """Test get_doubt_by_id èxit"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = 'd1'
        mock_doc.to_dict.return_value = {
            'id': 'd1', 'refuge_id': 'r1', 'creator_uid': 'u1', 'message': 'm', 'created_at': 'now'
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = DoubtDAO()
        res = dao.get_doubt_by_id("d1")
        assert res.id == 'd1'
        mock_cache.set.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_get_doubt_by_id_not_found(self, mock_cache, mock_firestore_class):
        """Test get_doubt_by_id no trobat"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = DoubtDAO()
        res = dao.get_doubt_by_id("d1")
        assert res is None

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answers_by_creator_doubt_not_found(self, mock_cache, mock_firestore_class):
        """Test delete_answers_by_creator quan el dubte no existeix"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_answer = MagicMock()
        mock_answer.id = 'a1'
        mock_answer.reference.parent.parent.id = 'd1'
        
        mock_db.collection_group.return_value.where.return_value.stream.return_value = [mock_answer]
        
        mock_doubt_doc = MagicMock()
        mock_doubt_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doubt_doc
        
        dao = DoubtDAO()
        success, error = dao.delete_answers_by_creator("u1")
        
        assert success is True
        assert error is None
        mock_answer.reference.delete.assert_called()
        # Should NOT update count if doubt not found
        mock_db.collection.return_value.document.return_value.update.assert_not_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_answers_by_creator_no_refuge_id(self, mock_cache, mock_firestore_class):
        """Test delete_answers_by_creator quan el dubte no té refuge_id"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_answer = MagicMock()
        mock_answer.id = 'a1'
        mock_answer.reference.parent.parent.id = 'd1'
        
        mock_db.collection_group.return_value.where.return_value.stream.return_value = [mock_answer]
        
        mock_doubt_doc = MagicMock()
        mock_doubt_doc.exists = True
        mock_doubt_doc.to_dict.return_value = {} # No refuge_id
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doubt_doc
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = []
        
        dao = DoubtDAO()
        success, error = dao.delete_answers_by_creator("u1")
        
        assert success is True
        assert error is None
        # Should call delete for doubt detail cache via _invalidate_doubt_detail_cache
        mock_cache.delete.assert_called()
        mock_cache.generate_key.assert_called()

    @patch('api.daos.doubt_dao.FirestoreService')
    @patch('api.daos.doubt_dao.cache_service')
    def test_delete_doubts_by_creator_no_refuge_id(self, mock_cache, mock_firestore_class):
        """Test delete_doubts_by_creator quan el dubte no té refuge_id"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        mock_doubt = MagicMock()
        mock_doubt.to_dict.return_value = {} # No refuge_id
        mock_doubt.id = 'd1'
        
        mock_db.collection.return_value.where.return_value.stream.return_value = [mock_doubt]
        mock_doubt.reference.collection.return_value.stream.return_value = []
        
        dao = DoubtDAO()
        success, error = dao.delete_doubts_by_creator("u1")
        
        assert success is True
        assert error is None
        # Should call delete for doubt detail cache via _invalidate_doubt_detail_cache
        mock_cache.delete.assert_called()
        mock_cache.generate_key.assert_called()
        # Should NOT call delete_pattern for refuge_id if not present
        assert mock_cache.delete_pattern.call_count == 0
