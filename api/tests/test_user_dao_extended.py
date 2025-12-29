"""
Tests extensos per a UserDAO
"""
import pytest
from unittest.mock import MagicMock, patch
from api.daos.user_dao import UserDAO
from api.models.user import User

class TestUserDAOExtended:
    """Tests per a UserDAO cobrint casos d'error i mètodes restants"""

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_create_user_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a create_user"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = UserDAO()
        res = dao.create_user({}, "u1")
        assert res is None

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_success(self, mock_cache, mock_firestore_class):
        """Test get_user_by_uid èxit"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = 'u1'
        mock_doc.to_dict.return_value = {
            'uid': 'u1', 'email': 'test@test.com', 'username': 'test'
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        res = dao.get_user_by_uid("u1")
        assert res.uid == 'u1'
        mock_cache.set.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_exception(self, mock_cache, mock_firestore_class):
        """Test excepció a get_user_by_uid"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = UserDAO()
        res = dao.get_user_by_uid("u1")
        assert res is None

    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_email_success(self, mock_firestore_class):
        """Test get_user_by_email èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.id = 'u1'
        mock_doc.to_dict.return_value = {
            'uid': 'u1', 'email': 'test@test.com', 'username': 'test'
        }
        mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = [mock_doc]
        
        dao = UserDAO()
        res = dao.get_user_by_email("test@test.com")
        assert res.uid == 'u1'

    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_email_exception(self, mock_firestore_class):
        """Test excepció a get_user_by_email"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("DB Error")
        
        dao = UserDAO()
        res = dao.get_user_by_email("test@test.com")
        assert res is None

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_user_success(self, mock_cache, mock_firestore_class):
        """Test update_user èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.update_user("u1", {'email': 'new@test.com'}) is True
        mock_db.collection.return_value.document.return_value.update.assert_called()
        mock_cache.delete.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_user_errors(self, mock_cache, mock_firestore_class):
        """Test errors a update_user"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.update_user("u1", {}) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.update_user("u1", {}) is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_user_success(self, mock_cache, mock_firestore_class):
        """Test delete_user èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'email': 'test@test.com'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.delete_user("u1") is True
        mock_db.collection.return_value.document.return_value.delete.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_user_errors(self, mock_cache, mock_firestore_class):
        """Test errors a delete_user"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.delete_user("u1") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.delete_user("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_shared_experiences_success(self, mock_cache, mock_firestore_class):
        """Test increment_shared_experiences èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.increment_shared_experiences("u1") is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_uploaded_photos_keys_success(self, mock_cache, mock_firestore_class):
        """Test add_uploaded_photos_keys èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'uploaded_photos_keys': ['k1']}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.add_uploaded_photos_keys("u1", ["k2"]) is True
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'uploaded_photos_keys': ['k1', 'k2']})

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_uploaded_photos_keys_success(self, mock_cache, mock_firestore_class):
        """Test remove_uploaded_photos_keys èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'uploaded_photos_keys': ['k1', 'k2']}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.remove_uploaded_photos_keys("u1", ["k1"]) is True
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'uploaded_photos_keys': ['k2']})

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_renovated_refuges_success(self, mock_cache, mock_firestore_class):
        """Test decrement_renovated_refuges èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'num_renovated_refuges': 1}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.decrement_renovated_refuges("u1") is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_avatar_metadata_success(self, mock_cache, mock_firestore_class):
        """Test update_avatar_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.update_avatar_metadata("u1", {'key': 'k1'}) is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_avatar_metadata_success(self, mock_cache, mock_firestore_class):
        """Test delete_avatar_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {'key': 'k1'}}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        success, meta = dao.delete_avatar_metadata("u1")
        assert success is True
        assert meta == {'key': 'k1'}
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'media_metadata': None})

    @patch('api.daos.user_dao.FirestoreService')
    def test_user_exists_errors(self, mock_firestore_class):
        """Test errors a user_exists"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        dao = UserDAO()
        assert dao.user_exists("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_refugi_to_list_errors(self, mock_cache, mock_firestore_class):
        """Test errors a add_refugi_to_list"""
        dao = UserDAO()
        
        # User not found
        with patch.object(dao, 'get_user_by_uid', return_value=None):
            success, res = dao.add_refugi_to_list("u1", "r1", "favourite_refuges")
            assert success is False
            
        # Exception
        with patch.object(dao, 'get_user_by_uid', side_effect=Exception("Error")):
            success, res = dao.add_refugi_to_list("u1", "r1", "favourite_refuges")
            assert success is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_refugi_from_list_errors(self, mock_cache, mock_firestore_class):
        """Test errors a remove_refugi_from_list"""
        dao = UserDAO()
        
        # User not found
        with patch.object(dao, 'get_user_by_uid', return_value=None):
            success, res = dao.remove_refugi_from_list("u1", "r1", "favourite_refuges")
            assert success is False
            
        # Exception
        with patch.object(dao, 'get_user_by_uid', side_effect=Exception("Error")):
            success, res = dao.remove_refugi_from_list("u1", "r1", "favourite_refuges")
            assert success is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_errors(self, mock_cache, mock_firestore_class):
        """Test errors a get_refugis_info"""
        dao = UserDAO()
        mock_cache.get.return_value = None
        
        # User not found
        with patch.object(dao, 'get_user_by_uid', return_value=None):
            assert dao.get_refugis_info("u1", "favourite_refuges") == []
            
        # Exception
        with patch.object(dao, 'get_user_by_uid', side_effect=Exception("Error")):
            assert dao.get_refugis_info("u1", "favourite_refuges") == []

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_renovated_refuges_errors(self, mock_cache, mock_firestore_class):
        """Test errors a increment_renovated_refuges"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.increment_renovated_refuges("u1") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.increment_renovated_refuges("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_uploaded_photos_keys_errors(self, mock_cache, mock_firestore_class):
        """Test errors a add_uploaded_photos_keys"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.add_uploaded_photos_keys("u1", []) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.add_uploaded_photos_keys("u1", []) is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_shared_experiences_errors(self, mock_cache, mock_firestore_class):
        """Test errors a increment_shared_experiences"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.increment_shared_experiences("u1") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.increment_shared_experiences("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_shared_experiences_errors(self, mock_cache, mock_firestore_class):
        """Test errors a decrement_shared_experiences"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.decrement_shared_experiences("u1") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.decrement_shared_experiences("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_uploaded_photos_keys_errors(self, mock_cache, mock_firestore_class):
        """Test errors a remove_uploaded_photos_keys"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.remove_uploaded_photos_keys("u1", []) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.remove_uploaded_photos_keys("u1", []) is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_renovated_refuges_errors(self, mock_cache, mock_firestore_class):
        """Test errors a decrement_renovated_refuges"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.decrement_renovated_refuges("u1") is False
        
        # Value is 0
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'num_renovated_refuges': 0}
        assert dao.decrement_renovated_refuges("u1") is True # Returns True but logs warning
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.decrement_renovated_refuges("u1") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_avatar_metadata_errors(self, mock_cache, mock_firestore_class):
        """Test errors a update_avatar_metadata"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        assert dao.update_avatar_metadata("u1", {}) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        assert dao.update_avatar_metadata("u1", {}) is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_delete_avatar_metadata_errors(self, mock_cache, mock_firestore_class):
        """Test errors a delete_avatar_metadata"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Not found
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = UserDAO()
        success, meta = dao.delete_avatar_metadata("u1")
        assert success is False
        
        # Exception
        mock_db.collection.side_effect = Exception("DB Error")
        success, meta = dao.delete_avatar_metadata("u1")
        assert success is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_refugi_to_list_success(self, mock_cache, mock_firestore_class):
        """Test add_refugi_to_list èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = UserDAO()
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = []
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.add_refugi_to_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert "r1" in res
            mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_refugi_from_list_success(self, mock_cache, mock_firestore_class):
        """Test remove_refugi_from_list èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = UserDAO()
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = ["r1"]
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.remove_refugi_from_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert "r1" not in res
            mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_success(self, mock_cache, mock_firestore_class):
        """Test get_refugis_info èxit"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = UserDAO()
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = ["r1"]
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'name': 'Refugi 1'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            res = dao.get_refugis_info("u1", "favourite_refuges")
            assert len(res) == 1
            assert res[0]['name'] == 'Refugi 1'

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_increment_renovated_refuges_success(self, mock_cache, mock_firestore_class):
        """Test increment_renovated_refuges èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.increment_renovated_refuges("u1") is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_shared_experiences_success(self, mock_cache, mock_firestore_class):
        """Test decrement_shared_experiences èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'num_shared_experiences': 1}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.decrement_shared_experiences("u1") is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.user_dao.FirestoreService')
    def test_user_exists_success(self, mock_firestore_class):
        """Test user_exists èxit"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.user_exists("u1") is True

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_refugi_to_list_edge_cases(self, mock_cache, mock_firestore_class):
        """Test add_refugi_to_list casos límit"""
        dao = UserDAO()
        
        # Already exists
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = ["r1"]
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.add_refugi_to_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert res == ["r1"]
            
        # current_list is None
        mock_user.favourite_refuges = None
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.add_refugi_to_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert res == ["r1"]

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_refugi_from_list_edge_cases(self, mock_cache, mock_firestore_class):
        """Test remove_refugi_from_list casos límit"""
        dao = UserDAO()
        
        # Not in list
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = ["r2"]
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.remove_refugi_from_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert res == ["r2"]
            
        # current_list is None
        mock_user.favourite_refuges = None
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            success, res = dao.remove_refugi_from_list("u1", "r1", "favourite_refuges")
            assert success is True
            assert res == []

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_edge_cases(self, mock_cache, mock_firestore_class):
        """Test get_refugis_info casos límit"""
        dao = UserDAO()
        
        # Cache hit
        mock_cache.get.return_value = [{'id': 'r1'}]
        assert dao.get_refugis_info("u1", "favourite_refuges") == [{'id': 'r1'}]
        
        # Empty list
        mock_cache.get.return_value = None
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = []
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            assert dao.get_refugis_info("u1", "favourite_refuges") == []

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_add_uploaded_photos_keys_none(self, mock_cache, mock_firestore_class):
        """Test add_uploaded_photos_keys quan current_keys és None"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'uploaded_photos_keys': None}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.add_uploaded_photos_keys("u1", ["k1"]) is True
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'uploaded_photos_keys': ['k1']})

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_remove_uploaded_photos_keys_none(self, mock_cache, mock_firestore_class):
        """Test remove_uploaded_photos_keys quan current_keys és None"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'uploaded_photos_keys': None}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.remove_uploaded_photos_keys("u1", ["k1"]) is True
        mock_db.collection.return_value.document.return_value.update.assert_called_with({'uploaded_photos_keys': []})

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_not_found(self, mock_cache, mock_firestore_class):
        """Test get_user_by_uid no trobat"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.get_user_by_uid("u1") is None

    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_email_not_found(self, mock_firestore_class):
        """Test get_user_by_email no trobat"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
        
        dao = UserDAO()
        assert dao.get_user_by_email("test@test.com") is None

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_by_email(self, mock_cache, mock_firestore_class):
        """Test user_exists_by_email"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        # Exists
        mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = [MagicMock()]
        dao = UserDAO()
        assert dao.user_exists_by_email("test@test.com") is True
        
        # Not exists
        mock_db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
        assert dao.user_exists_by_email("other@test.com") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.user_exists_by_email("error@test.com") is False

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_decrement_shared_experiences_zero(self, mock_cache, mock_firestore_class):
        """Test decrement_shared_experiences quan el valor és 0"""
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'num_shared_experiences': 0}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = UserDAO()
        assert dao.decrement_shared_experiences("u1") is True
        mock_db.collection.return_value.document.return_value.update.assert_not_called()

    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_refugis_info_no_cache(self, mock_cache, mock_firestore_class):
        """Test get_refugis_info quan el refugi no està a cache"""
        mock_cache.get.side_effect = [None, None, None] # user_refugis_info, user_detail (in get_user_by_uid), refugi_detail
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        
        dao = UserDAO()
        mock_user = MagicMock(spec=User)
        mock_user.favourite_refuges = ["r1"]
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'name': 'Refugi 1'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        with patch.object(dao, 'get_user_by_uid', return_value=mock_user):
            res = dao.get_refugis_info("u1", "favourite_refuges")
            assert len(res) == 1
            assert res[0]['name'] == 'Refugi 1'
            assert mock_cache.set.call_count >= 2 # refugi_detail and user_refugis_info
