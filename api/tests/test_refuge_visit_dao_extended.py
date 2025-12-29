"""
Tests extensos per a RefugeVisitDAO
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from api.daos.refuge_visit_dao import RefugeVisitDAO
from api.models.refuge_visit import RefugeVisit, UserVisit

class TestRefugeVisitDAOExtended:
    """Tests per a RefugeVisitDAO cobrint casos d'error i excepcions"""

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_create_visit_exception(self, mock_cache, mock_firestore_service):
        """Test create_visit amb excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_db.collection.side_effect = Exception("DB Error")
        
        success, visit_id, error = dao.create_visit({'refuge_id': 'r1'})
        assert success is False
        assert "DB Error" in error

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_get_visit_by_id_not_found_and_exception(self, mock_cache, mock_firestore_service):
        """Test get_visit_by_id cas no trobat i excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_cache.get.return_value = None
        
        # Not found
        mock_doc = mock_db.collection.return_value.document.return_value.get.return_value
        mock_doc.exists = False
        assert dao.get_visit_by_id("v1") is None
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.get_visit_by_id("v1") is None

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_get_visit_by_refuge_and_date_not_found_and_exception(self, mock_cache, mock_firestore_service):
        """Test get_visit_by_refuge_and_date cas no trobat i excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        # Not found
        mock_db.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = []
        assert dao.get_visit_by_refuge_and_date("r1", "2024-01-01") is None
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.get_visit_by_refuge_and_date("r1", "2024-01-01") is None

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_get_visits_by_refuge_exception(self, mock_cache, mock_firestore_service):
        """Test get_visits_by_refuge amb excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_cache.get.return_value = None
        mock_db.collection.side_effect = Exception("Error")
        
        assert dao.get_visits_by_refuge("r1", date.today()) == []

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_get_visits_by_user_exception(self, mock_firestore_service):
        """Test get_visits_by_user amb excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_db.collection.side_effect = Exception("Error")
        
        assert dao.get_visits_by_user("u1") == []

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_add_update_visitor_not_found_and_exception(self, mock_firestore_service):
        """Test add/update visitor cas no trobat i excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        # Add - Not found
        mock_db.collection.return_value.document.return_value.get.return_value.exists = False
        assert dao.add_visitor_to_visit("v1", {}) is False
        
        # Update - Not found
        assert dao.update_visitor_in_visit("v1", {}) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.add_visitor_to_visit("v1", {}) is False
        assert dao.update_visitor_in_visit("v1", {}) is False

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_remove_visitor_from_visit_errors(self, mock_firestore_service):
        """Test remove_visitor_from_visit errors"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_doc = MagicMock()
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        # Not found
        mock_doc.exists = False
        assert dao.remove_visitor_from_visit("v1", "u1") is False
        
        # User not in visit
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'visitors': [{'uid': 'u2'}]}
        result = dao.remove_visitor_from_visit("v1", "u1")
        print(f"RESULT: {result}")
        assert result is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.remove_visitor_from_visit("v1", "u1") is False

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_get_visits_by_date_exception(self, mock_firestore_service):
        """Test get_visits_by_date amb excepció"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_db.collection.side_effect = Exception("Error")
        
        assert dao.get_visits_by_date("2024-01-01") == []

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_delete_visit_errors(self, mock_firestore_service):
        """Test delete_visit errors"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        # Not found
        mock_db.collection.return_value.document.return_value.get.return_value.exists = False
        assert dao.delete_visit("v1") is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Error")
        assert dao.delete_visit("v1") is False

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_get_visits_by_refuge_success(self, mock_cache, mock_firestore_service):
        """Test get_visits_by_refuge èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_cache.get.return_value = None
        
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {'refuge_id': 'r1', 'date': '2024-01-01'}
        mock_db.collection.return_value.where.return_value.where.return_value.order_by.return_value.get.return_value = [mock_doc]
        
        results = dao.get_visits_by_refuge("r1", date.today())
        assert len(results) == 1
        assert results[0].refuge_id == "r1"

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_get_visits_by_user_success(self, mock_firestore_service):
        """Test get_visits_by_user èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        mock_doc = MagicMock()
        mock_doc.id = "v1"
        mock_doc.to_dict.return_value = {
            'refuge_id': 'r1', 
            'date': '2024-01-01',
            'visitors': [{'uid': 'u1', 'num_visitors': 2}]
        }
        mock_db.collection.return_value.order_by.return_value.get.return_value = [mock_doc]
        
        results = dao.get_visits_by_user("u1")
        assert len(results) == 1
        assert results[0][0] == "v1"

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_add_update_visitor_success(self, mock_cache, mock_firestore_service):
        """Test add/update visitor èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_doc_ref = mock_db.collection.return_value.document.return_value
        mock_doc_ref.get.return_value.exists = True
        
        data = {'visitors': [{'uid': 'u1'}], 'total_visitors': 1, 'refuge_id': 'r1'}
        
        assert dao.add_visitor_to_visit("v1", data) is True
        assert dao.update_visitor_in_visit("v1", data) is True
        assert mock_doc_ref.update.call_count == 2

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_remove_visitor_from_visit_success(self, mock_cache, mock_firestore_service):
        """Test remove_visitor_from_visit èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_doc_ref = mock_db.collection.return_value.document.return_value
        mock_doc = mock_doc_ref.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'refuge_id': 'r1',
            'total_visitors': 5,
            'visitors': [{'uid': 'u1', 'num_visitors': 2}, {'uid': 'u2', 'num_visitors': 3}]
        }
        
        assert dao.remove_visitor_from_visit("v1", "u1") is True
        mock_doc_ref.update.assert_called_once()
        # total_visitors should be 5 - 2 = 3
        args, kwargs = mock_doc_ref.update.call_args
        assert args[0]['total_visitors'] == 3

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_get_visits_by_date_success(self, mock_firestore_service):
        """Test get_visits_by_date èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        mock_doc = MagicMock()
        mock_doc.id = "v1"
        mock_doc.to_dict.return_value = {'refuge_id': 'r1', 'date': '2024-01-01'}
        mock_db.collection.return_value.where.return_value.get.return_value = [mock_doc]
        
        results = dao.get_visits_by_date("2024-01-01")
        assert len(results) == 1
        assert results[0][0] == "v1"

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    @patch('api.daos.refuge_visit_dao.cache_service')
    def test_remove_user_from_all_visits_success(self, mock_cache, mock_firestore_service):
        """Test remove_user_from_all_visits èxit"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        mock_doc_ref = mock_db.collection.return_value.document.return_value
        mock_doc = mock_doc_ref.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'refuge_id': 'r1',
            'total_visitors': 2,
            'visitors': [{'uid': 'u1', 'num_visitors': 1}, {'uid': 'u2', 'num_visitors': 1}]
        }
        
        visit = MagicMock(spec=RefugeVisit)
        success, error = dao.remove_user_from_all_visits("u1", [("v1", visit)])
        
        assert success is True
        mock_doc_ref.update.assert_called_once()
        args, kwargs = mock_doc_ref.update.call_args
        assert len(args[0]['visitors']) == 1
        assert args[0]['total_visitors'] == 1

    @patch('api.daos.refuge_visit_dao.FirestoreService')
    def test_remove_user_from_all_visits_errors(self, mock_firestore_service):
        """Test remove_user_from_all_visits errors"""
        dao = RefugeVisitDAO()
        mock_db = mock_firestore_service.return_value.get_db.return_value
        
        # Empty list
        success, error = dao.remove_user_from_all_visits("u1", [])
        assert success is True
        
        # Visit not found (inner exception/warning)
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        visit = MagicMock(spec=RefugeVisit)
        success, error = dao.remove_user_from_all_visits("u1", [("v1", visit)])
        assert success is True # It continues
        
        # Outer exception
        mock_firestore_service.return_value.get_db.side_effect = Exception("Outer Error")
        success, error = dao.remove_user_from_all_visits("u1", [("v1", visit)])
        assert success is False
        assert "Outer Error" in error
