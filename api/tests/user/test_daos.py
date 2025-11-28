"""
Tests per usuaris
"""

import pytest
from unittest.mock import MagicMock, patch
from api.daos.user_dao import UserDAO
# ==================== TESTS DE MODELS ====================


@pytest.mark.daos
class TestUserDAO:
    """Tests per al UserDAO"""
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_create_user_success(self, mock_cache, mock_firestore_service, sample_user_data):
        """Test creació d'usuari exitosa"""
        # Configurar mocks
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_collection = MagicMock()
        mock_db.collection.return_value = mock_collection
        
        mock_doc_ref = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        
        # Crear DAO i executar
        dao = UserDAO()
        user = dao.create_user(sample_user_data, 'test_uid')
        
        # Verificacions
        assert user is not None
        assert user.uid == sample_user_data['uid']
        assert user.email == sample_user_data['email']
        mock_db.collection.assert_called_once_with('users')
        mock_collection.document.assert_called_once_with('test_uid')
        mock_doc_ref.set.assert_called_once_with(sample_user_data)
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_uid_found(self, mock_firestore_service, mock_cache, sample_user_data):
        """Test obtenció d'usuari per UID (trobat)"""
        # Cache miss
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        # Configurar Firestore mock
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.id = 'test_uid'
        mock_doc_snapshot.to_dict.return_value = sample_user_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Executar
        dao = UserDAO()
        result = dao.get_user_by_uid('test_uid')
        
        # Verificacions
        assert result is not None
        assert result.uid == 'test_uid'
        assert result.email == sample_user_data['email']
        mock_cache.set.assert_called_once()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_not_found(self, mock_cache, mock_firestore_service):
        """Test obtenció d'usuari per UID (no trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_user_by_uid('nonexistent_uid')
        
        assert result is None
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_uid_from_cache(self, mock_firestore_service, mock_cache, sample_user_data):
        """Test obtenció d'usuari des de cache"""
        # Cache hit
        mock_cache.get.return_value = sample_user_data
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = UserDAO()
        result = dao.get_user_by_uid('test_uid')
        
        assert result is not None
        assert result.uid == sample_user_data['uid']
        assert result.email == sample_user_data['email']
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_email_found(self, mock_cache, mock_firestore_service, sample_user_data):
        """Test obtenció d'usuari per email (trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'test_uid'
        mock_doc.to_dict.return_value = sample_user_data
        
        mock_query = MagicMock()
        mock_query.get.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_user_by_email('test@example.com')
        
        assert result is not None
        assert result.uid == 'test_uid'
        assert result.email == sample_user_data['email']
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_by_email_found_cached(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència per email (amb cache)"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get.return_value = True  # Existeix a cache
        
        dao = UserDAO()
        result = dao.user_exists_by_email('test@example.com')
        
        assert result is True
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_by_email_found(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència per email (trobat)"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_query = MagicMock()
        mock_query.get.return_value = [mock_doc]  # Existeix
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.user_exists_by_email('test@example.com')
        
        assert result is True
        # Hauria de guardar a cache
        mock_cache.set.assert_called_once_with('test_cache_key', True, 300)
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_by_email_not_found(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència per email (no trobat)"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.get.return_value = []  # No existeix
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.user_exists_by_email('test@example.com')
        
        assert result is False
        # Hauria de guardar a cache
        mock_cache.set.assert_called_once_with('test_cache_key', False, 300)
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_update_user_success(self, mock_firestore_service, mock_cache):
        """Test actualització d'usuari exitosa"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        update_data = {'username': 'updated_username'}
        success = dao.update_user('test_uid', update_data)
        
        assert success is True
        mock_doc_ref.update.assert_called_once_with(update_data)
        mock_cache.delete.assert_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_user_not_found(self, mock_cache, mock_firestore_service):
        """Test actualització d'usuari no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success = dao.update_user('nonexistent_uid', {'username': 'test'})
        
        assert success is False
        mock_doc_ref.update.assert_not_called()
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_update_user_with_email(self, mock_firestore_service, mock_cache):
        """Test actualització d'usuari amb canvi d'email"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        update_data = {'email': 'newemail@test.com'}
        success = dao.update_user('test_uid', update_data)
        
        assert success is True
        # Hauria d'invalidar cache d'email
        assert mock_cache.delete.call_count == 2  # user_detail + user_email_exists
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_refugi_to_list_none_list(self, mock_cache, mock_firestore_service, mock_get_user, sample_user):
        """Test afegir refugi quan la llista és None"""
        sample_user.favourite_refuges = None
        mock_get_user.return_value = sample_user
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success, updated_list = dao.add_refugi_to_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert 'refugi_123' in updated_list
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_refugi_from_list_none_list(self, mock_cache, mock_firestore_service, mock_get_user, sample_user):
        """Test eliminar refugi quan la llista és None"""
        sample_user.favourite_refuges = None
        mock_get_user.return_value = sample_user
        
        dao = UserDAO()
        success, updated_list = dao.remove_refugi_from_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert updated_list is not None
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_delete_user_success(self, mock_firestore_service, mock_cache):
        """Test eliminació d'usuari exitosa"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success = dao.delete_user('test_uid')
        
        assert success is True
        mock_doc_ref.delete.assert_called_once()
        mock_cache.delete.assert_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_true(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència d'usuari (existeix)"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        exists = dao.user_exists('test_uid')
        
        assert exists is True
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_false(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència d'usuari (no existeix)"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        exists = dao.user_exists('nonexistent_uid')
        
        assert exists is False
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_create_user_exception(self, mock_cache, mock_firestore_service):
        """Test creació d'usuari amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.create_user({'email': 'test@test.com'}, 'test_uid')
        
        assert result is None
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_exception(self, mock_cache, mock_firestore_service):
        """Test obtenció d'usuari per UID amb excepció"""
        mock_cache.get.return_value = None
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.get_user_by_uid('test_uid')
        
        assert result is None
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_email_not_found(self, mock_cache, mock_firestore_service):
        """Test obtenció d'usuari per email (no trobat)"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.get.return_value = []  # No trobat
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_user_by_email('notfound@test.com')
        
        assert result is None
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_email_exception(self, mock_cache, mock_firestore_service):
        """Test obtenció d'usuari per email amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.get_user_by_email('test@test.com')
        
        assert result is None
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_by_email_exception(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència per email amb excepció"""
        mock_cache.get.return_value = None
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.user_exists_by_email('test@test.com')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_user_exception(self, mock_cache, mock_firestore_service):
        """Test actualització d'usuari amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.update_user('test_uid', {'name': 'New Name'})
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_user_not_found(self, mock_cache, mock_firestore_service):
        """Test eliminació d'usuari no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.delete_user('nonexistent_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_user_exception(self, mock_cache, mock_firestore_service):
        """Test eliminació d'usuari amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.delete_user('test_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_exception(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.user_exists('test_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_refugi_to_list_success(self, mock_cache, mock_firestore_service, mock_get_user, sample_user):
        """Test afegir refugi a llista exitós"""
        mock_get_user.return_value = sample_user
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success, updated_list = dao.add_refugi_to_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert updated_list is not None
        assert 'refugi_123' in updated_list
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_add_refugi_to_list_user_not_found(self, mock_get_user):
        """Test afegir refugi quan l'usuari no existeix"""
        mock_get_user.return_value = None
        
        dao = UserDAO()
        success, updated_list = dao.add_refugi_to_list('nonexistent_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is False
        assert updated_list is None
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_add_refugi_to_list_already_exists(self, mock_get_user, sample_user):
        """Test afegir refugi que ja està a la llista"""
        sample_user.favourite_refuges = ['refugi_123']
        mock_get_user.return_value = sample_user
        
        dao = UserDAO()
        success, updated_list = dao.add_refugi_to_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert 'refugi_123' in updated_list
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_add_refugi_to_list_exception(self, mock_get_user, sample_user):
        """Test afegir refugi amb excepció"""
        mock_get_user.side_effect = Exception('Database error')
        
        dao = UserDAO()
        success, updated_list = dao.add_refugi_to_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is False
        assert updated_list is None
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_refugi_from_list_success(self, mock_cache, mock_firestore_service, mock_get_user, sample_user):
        """Test eliminar refugi de llista exitós"""
        sample_user.favourite_refuges = ['refugi_123', 'refugi_456']
        mock_get_user.return_value = sample_user
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success, updated_list = dao.remove_refugi_from_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert updated_list is not None
        assert 'refugi_123' not in updated_list
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_remove_refugi_from_list_user_not_found(self, mock_get_user):
        """Test eliminar refugi quan l'usuari no existeix"""
        mock_get_user.return_value = None
        
        dao = UserDAO()
        success, updated_list = dao.remove_refugi_from_list('nonexistent_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is False
        assert updated_list is None
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_remove_refugi_from_list_not_in_list(self, mock_get_user, sample_user):
        """Test eliminar refugi que no està a la llista"""
        sample_user.favourite_refuges = ['refugi_456']
        mock_get_user.return_value = sample_user
        
        dao = UserDAO()
        success, updated_list = dao.remove_refugi_from_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is True
        assert 'refugi_123' not in updated_list
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    def test_remove_refugi_from_list_exception(self, mock_get_user, sample_user):
        """Test eliminar refugi amb excepció"""
        mock_get_user.side_effect = Exception('Database error')
        
        dao = UserDAO()
        success, updated_list = dao.remove_refugi_from_list('test_uid', 'refugi_123', 'favourite_refuges')
        
        assert success is False
        assert updated_list is None
    
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_from_cache(self, mock_cache):
        """Test obtenció d'info de refugis des de cache"""
        cached_data = [{'id': 'refugi_123', 'name': 'Test Refugi'}]
        mock_cache.get.return_value = cached_data
        
        dao = UserDAO()
        result = dao.get_refugis_info('test_uid', 'favourite_refuges')
        
        assert result == cached_data
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_user_not_found(self, mock_cache, mock_get_user):
        """Test obtenció d'info de refugis quan l'usuari no existeix"""
        mock_cache.get.return_value = None
        mock_get_user.return_value = None
        
        dao = UserDAO()
        result = dao.get_refugis_info('nonexistent_uid', 'favourite_refuges')
        
        assert result == []
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_empty_list(self, mock_cache, mock_get_user, sample_user):
        """Test obtenció d'info de refugis amb llista buida"""
        mock_cache.get.return_value = None
        sample_user.favourite_refuges = []
        mock_get_user.return_value = sample_user
        
        dao = UserDAO()
        result = dao.get_refugis_info('test_uid', 'favourite_refuges')
        
        assert result == []
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_with_ids_provided(self, mock_cache, mock_firestore_service):
        """Test obtenció d'info de refugis amb IDs proporcionats"""
        mock_cache.get.side_effect = [None, None]  # Cache miss per result i refugi
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = {
            'name': 'Test Refugi',
            'region': 'Pirineus',
            'places': 20,
            'coord': {'lat': 42.0, 'long': 1.0}
        }
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_refugis_info('test_uid', 'favourite_refuges', ['refugi_123'])
        
        assert len(result) == 1
        assert result[0]['id'] == 'refugi_123'
    
    @patch('api.daos.user_dao.UserDAO.get_user_by_uid')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_exception(self, mock_cache, mock_get_user):
        """Test obtenció d'info de refugis amb excepció"""
        mock_cache.get.return_value = None
        mock_get_user.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.get_refugis_info('test_uid', 'favourite_refuges')
        
        assert result == []
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_renovated_refuges_success(self, mock_cache, mock_firestore_service):
        """Test increment comptador exitós"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.increment_renovated_refuges('test_uid')
        
        assert result is True
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_renovated_refuges_user_not_found(self, mock_cache, mock_firestore_service):
        """Test increment comptador usuari no trobat"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.increment_renovated_refuges('nonexistent_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_renovated_refuges_exception(self, mock_cache, mock_firestore_service):
        """Test increment comptador amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.increment_renovated_refuges('test_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_renovated_refuges_success(self, mock_cache, mock_firestore_service):
        """Test decrement comptador exitós"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.decrement_renovated_refuges('test_uid')
        
        assert result is True
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_renovated_refuges_user_not_found(self, mock_cache, mock_firestore_service):
        """Test decrement comptador usuari no trobat"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.decrement_renovated_refuges('nonexistent_uid')
        
        assert result is False
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_renovated_refuges_exception(self, mock_cache, mock_firestore_service):
        """Test decrement comptador amb excepció"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception('Database error')
        
        dao = UserDAO()
        result = dao.decrement_renovated_refuges('test_uid')
        
        assert result is False


# ==================== TESTS DE CONTROLLERS ====================
