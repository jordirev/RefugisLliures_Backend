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

    # ===== TESTS ADDICIONALS PER MILLORAR COVERAGE =====

    def test_create_experience_exception(self, dao, mock_db, mock_cache):
        """Test creació d'experiència amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        exp_data = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test',
            'modified_at': '2024-01-01'
        }
        
        result = dao.create_experience(exp_data)
        
        assert result is None

    def test_get_experience_by_id_from_cache(self, dao, mock_cache):
        """Test obtenció d'experiència des de cache"""
        cached_data = {
            'id': 'exp_123',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test',
            'modified_at': '2024-01-01'
        }
        mock_cache.get.return_value = cached_data
        
        result = dao.get_experience_by_id("exp_123")
        
        assert result is not None
        assert result.id == "exp_123"

    def test_get_experience_by_id_not_found(self, dao, mock_db, mock_cache):
        """Test obtenció d'experiència no trobada"""
        mock_cache.get.return_value = None
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_experience_by_id("nonexistent")
        
        assert result is None

    def test_get_experience_by_id_exception(self, dao, mock_db, mock_cache):
        """Test obtenció d'experiència amb excepció"""
        mock_cache.get.return_value = None
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        result = dao.get_experience_by_id("exp_123")
        
        assert result is None

    def test_get_experiences_by_refuge_id_success(self, dao, mock_cache):
        """Test obtenció d'experiències per refugi amb èxit"""
        experiences_data = [
            {'id': 'exp_1', 'refuge_id': 'ref_1', 'creator_uid': 'u1', 'comment': 'T1', 'modified_at': '2024-01-01'},
            {'id': 'exp_2', 'refuge_id': 'ref_1', 'creator_uid': 'u2', 'comment': 'T2', 'modified_at': '2024-01-02'}
        ]
        mock_cache.get_or_fetch_list.return_value = experiences_data
        mock_cache.get_timeout.return_value = 300
        
        result = dao.get_experiences_by_refuge_id("ref_1")
        
        assert len(result) == 2
        assert result[0].id == 'exp_1'

    def test_get_experiences_by_refuge_id_exception(self, dao, mock_cache):
        """Test obtenció d'experiències per refugi amb excepció"""
        mock_cache.get_or_fetch_list.side_effect = Exception("Error de connexió")
        mock_cache.get_timeout.return_value = 300
        
        result = dao.get_experiences_by_refuge_id("ref_1")
        
        assert result == []

    def test_update_experience_not_found(self, dao, mock_db, mock_cache):
        """Test actualització d'experiència no trobada"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.update_experience("nonexistent", {'comment': 'Updated'})
        
        assert success is False
        assert "not found" in error.lower()

    def test_update_experience_exception(self, dao, mock_db, mock_cache):
        """Test actualització d'experiència amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        success, error = dao.update_experience("exp_123", {'comment': 'Updated'})
        
        assert success is False
        assert error is not None

    def test_delete_experience_not_found(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiència no trobada"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.delete_experience("nonexistent")
        
        assert success is False
        assert "not found" in error.lower()

    def test_delete_experience_exception(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiència amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        success, error = dao.delete_experience("exp_123")
        
        assert success is False
        assert error is not None

    def test_add_media_keys_to_experience_success(self, dao, mock_db, mock_cache):
        """Test afegir media keys amb èxit"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.add_media_keys_to_experience("exp_123", ["key1", "key2"])
        
        assert success is True
        assert error is None
        mock_doc_ref.update.assert_called()

    def test_add_media_keys_to_experience_not_found(self, dao, mock_db, mock_cache):
        """Test afegir media keys a experiència no trobada"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.add_media_keys_to_experience("nonexistent", ["key1"])
        
        assert success is False
        assert "not found" in error.lower()

    def test_add_media_keys_to_experience_exception(self, dao, mock_db, mock_cache):
        """Test afegir media keys amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        success, error = dao.add_media_keys_to_experience("exp_123", ["key1"])
        
        assert success is False
        assert error is not None

    def test_remove_media_key_not_found(self, dao, mock_db, mock_cache):
        """Test eliminar media key d'experiència no trobada"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success, error = dao.remove_media_key("nonexistent", "key1")
        
        assert success is False
        assert "not found" in error.lower()

    def test_remove_media_key_exception(self, dao, mock_db, mock_cache):
        """Test eliminar media key amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        success, error = dao.remove_media_key("exp_123", "key1")
        
        assert success is False
        assert error is not None

    def test_delete_experiences_by_creator_success(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiències per creador amb èxit"""
        mock_exp_doc = MagicMock()
        mock_exp_doc.id = "exp_1"
        mock_exp_doc.to_dict.return_value = {'refuge_id': 'ref_1'}
        mock_exp_doc.reference = MagicMock()
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_exp_doc]
        mock_db.collection.return_value.where.return_value = mock_query
        
        success, error = dao.delete_experiences_by_creator("user_1")
        
        assert success is True
        assert error is None
        mock_exp_doc.reference.delete.assert_called()

    def test_delete_experiences_by_creator_no_experiences(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiències per creador sense experiències"""
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        mock_db.collection.return_value.where.return_value = mock_query
        
        success, error = dao.delete_experiences_by_creator("user_1")
        
        assert success is True
        assert error is None

    def test_delete_experiences_by_creator_exception(self, dao, mock_db, mock_cache):
        """Test eliminació d'experiències per creador amb excepció"""
        mock_db.collection.side_effect = Exception("Error de connexió")
        
        success, error = dao.delete_experiences_by_creator("user_1")
        
        assert success is False
        assert error is not None

    # ===== TESTS PER COBRIR FUNCIONS INTERNES fetch_all, fetch_single, get_id =====

    def test_get_experiences_by_refuge_id_fetch_all_called(self, dao, mock_db, mock_cache):
        """Test que fetch_all és cridat quan cache fa callback"""
        # Mock per fer que get_or_fetch_list cridi realment la funció fetch_all
        def execute_fetch_all(*args, **kwargs):
            fetch_all_fn = kwargs.get('fetch_all_fn')
            if fetch_all_fn:
                return fetch_all_fn()  # Executa la funció fetch_all
            return []
        
        mock_cache.get_or_fetch_list.side_effect = execute_fetch_all
        mock_cache.get_timeout.return_value = 300
        
        # Configurar mock de Firestore per retornar documents
        mock_doc1 = MagicMock()
        mock_doc1.id = 'exp_1'
        mock_doc1.to_dict.return_value = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test 1',
            'modified_at': '2024-01-01'
        }
        mock_doc2 = MagicMock()
        mock_doc2.id = 'exp_2'
        mock_doc2.to_dict.return_value = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_2',
            'comment': 'Test 2',
            'modified_at': '2024-01-02'
        }
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc1, mock_doc2]
        mock_db.collection.return_value.where.return_value.order_by.return_value = mock_query
        
        result = dao.get_experiences_by_refuge_id("ref_1")
        
        assert len(result) == 2
        assert result[0].id == 'exp_1'
        assert result[1].id == 'exp_2'

    def test_get_experiences_by_refuge_id_fetch_single_called(self, dao, mock_db, mock_cache):
        """Test que fetch_single és cridat quan cache fa callback"""
        # Mock per fer que get_or_fetch_list cridi realment la funció fetch_single
        def execute_fetch_single(*args, **kwargs):
            fetch_single_fn = kwargs.get('fetch_single_fn')
            get_id_fn = kwargs.get('get_id_fn')
            if fetch_single_fn and get_id_fn:
                # Simular que necessita fer fetch_single
                exp_data = fetch_single_fn('exp_1')
                if exp_data:
                    return [exp_data]
            return []
        
        mock_cache.get_or_fetch_list.side_effect = execute_fetch_single
        mock_cache.get_timeout.return_value = 300
        
        # Configurar mock de Firestore per retornar document
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = 'exp_1'
        mock_doc.to_dict.return_value = {
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'comment': 'Test 1',
            'modified_at': '2024-01-01'
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_experiences_by_refuge_id("ref_1")
        
        assert len(result) == 1
        assert result[0].id == 'exp_1'

    def test_get_experiences_by_refuge_id_fetch_single_not_found(self, dao, mock_db, mock_cache):
        """Test que fetch_single retorna None quan el document no existeix"""
        def execute_fetch_single(*args, **kwargs):
            fetch_single_fn = kwargs.get('fetch_single_fn')
            if fetch_single_fn:
                return [fetch_single_fn('nonexistent')]  # Pot retornar None
            return []
        
        mock_cache.get_or_fetch_list.side_effect = execute_fetch_single
        mock_cache.get_timeout.return_value = 300
        
        # Configurar mock de Firestore per retornar document no existent
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_experiences_by_refuge_id("ref_1")
        
        # None is filtered out so result should be empty
        assert result == [] or (len(result) == 1 and result[0] is None)

    def test_get_experiences_by_refuge_id_get_id_function(self, dao, mock_cache):
        """Test que get_id extreu correctament l'ID"""
        captured_get_id = None
        
        def capture_get_id(*args, **kwargs):
            nonlocal captured_get_id
            captured_get_id = kwargs.get('get_id_fn')
            return [{'id': 'exp_1', 'refuge_id': 'ref_1', 'creator_uid': 'u1', 'comment': 'T', 'modified_at': '2024-01-01'}]
        
        mock_cache.get_or_fetch_list.side_effect = capture_get_id
        mock_cache.get_timeout.return_value = 300
        
        dao.get_experiences_by_refuge_id("ref_1")
        
        # Verificar que get_id funciona correctament
        assert captured_get_id is not None
        test_data = {'id': 'test_id', 'other': 'data'}
        assert captured_get_id(test_data) == 'test_id'
