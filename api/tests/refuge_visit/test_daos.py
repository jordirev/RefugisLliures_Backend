"""
Tests per al DAO de visites a refugi
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import date
from api.daos.refuge_visit_dao import RefugeVisitDAO
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.daos
class TestRefugeVisitDAO:
    """Tests per a RefugeVisitDAO"""
    
    @pytest.fixture
    def mock_firestore_class(self):
        with patch('api.daos.refuge_visit_dao.FirestoreService') as mock:
            yield mock

    @pytest.fixture
    def mock_db(self, mock_firestore_class):
        mock_db = MagicMock()
        mock_firestore_class.return_value.get_db.return_value = mock_db
        return mock_db

    @pytest.fixture
    def mock_cache(self):
        with patch('api.daos.refuge_visit_dao.cache_service') as mock:
            yield mock

    @pytest.fixture
    def dao(self, mock_firestore_class, mock_cache):
        return RefugeVisitDAO()
    
    def test_create_visit_success(self, dao, mock_db, mock_cache):
        """Test creació de visita exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "visit_123"
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        data = {'refuge_id': 'ref_1', 'date': '2024-01-01', 'total_visitors': 2}
        success, visit_id, error = dao.create_visit(data)
        
        assert success is True
        assert visit_id == "visit_123"
        mock_doc_ref.set.assert_called_with(data)
        mock_cache.delete_pattern.assert_called()

    def test_get_visit_by_id_found(self, dao, mock_db, mock_cache):
        """Test obtenció de visita per ID existent"""
        mock_cache.get.return_value = None
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refuge_id': 'ref_1', 'date': '2024-01-01'}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        result = dao.get_visit_by_id("visit_123")
        
        assert result is not None
        assert result.refuge_id == 'ref_1'
        mock_cache.set.assert_called()

    @patch('api.daos.refuge_visit_dao.firestore.FieldFilter')
    def test_get_visit_by_refuge_and_date_found(self, mock_filter, dao, mock_db, mock_cache):
        """Test obtenció de visita per refugi i data"""
        mock_doc = MagicMock()
        mock_doc.id = "visit_123"
        mock_doc.to_dict.return_value = {'refuge_id': 'ref_1', 'date': '2024-01-01'}
        mock_db.collection.return_value.where.return_value.where.return_value.limit.return_value.get.return_value = [mock_doc]
        
        result = dao.get_visit_by_refuge_and_date("ref_1", "2024-01-01")
        
        assert result is not None
        assert result[0] == "visit_123"
        assert result[1].refuge_id == "ref_1"

    def test_delete_visit_success(self, dao, mock_db, mock_cache):
        """Test eliminació de visita exitosa"""
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'refuge_id': 'ref_1'}
        mock_doc_ref.get.return_value = mock_doc
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        
        success = dao.delete_visit("visit_123")
        
        assert success is True
        mock_doc_ref.delete.assert_called()
        mock_cache.delete.assert_called()
        mock_cache.delete_pattern.assert_called()
