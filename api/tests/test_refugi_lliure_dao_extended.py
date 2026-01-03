"""
Tests extensos per a RefugiLliureDAO
"""
import pytest
from unittest.mock import MagicMock, patch
from api.daos.refugi_lliure_dao import RefugiLliureDAO
from api.models.refugi_lliure import RefugiSearchFilters

class TestRefugiLliureDAOExtended:
    """Tests per a RefugiLliureDAO cobrint casos d'error i mètodes restants"""

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_exception(self, mock_cache, mock_firestore):
        """Test excepció a get_by_id"""
        mock_cache.get.return_value = None
        mock_firestore.get_db.side_effect = Exception("DB Error")
        dao = RefugiLliureDAO()
        with pytest.raises(Exception, match="DB Error"):
            dao.get_by_id("r1")

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_exception(self, mock_cache, mock_firestore):
        """Test excepció a search_refugis"""
        # Mock get_or_fetch_list to raise an exception
        mock_cache.get_or_fetch_list.side_effect = Exception("Search Error")
        mock_cache.generate_key.return_value = 'test_cache_key'
        dao = RefugiLliureDAO()
        # Use filters to trigger the path that uses get_or_fetch_list
        filters = RefugiSearchFilters(name="test")
        with pytest.raises(Exception, match="Search Error"):
            dao.search_refugis(filters)

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_coordinates_errors(self, mock_cache, mock_firestore):
        """Test errors a _get_coordinates_as_refugi_list"""
        mock_cache.get.return_value = None
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        assert dao._get_coordinates_as_refugi_list() == []
        
        # Exception
        mock_db.collection.side_effect = Exception("Coords Error")
        assert dao._get_coordinates_as_refugi_list() == []

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_search_by_name_exception(self, mock_firestore):
        """Test excepció a _search_by_name"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_db.collection.side_effect = Exception("Name Error")
        dao = RefugiLliureDAO()
        assert dao._search_by_name(mock_db, "Refugi") == []

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_refugi_exists_exception(self, mock_cache, mock_firestore):
        """Test excepció a refugi_exists"""
        mock_cache.get.return_value = None
        mock_firestore.get_db.side_effect = Exception("Exists Error")
        dao = RefugiLliureDAO()
        with pytest.raises(Exception, match="Exists Error"):
            dao.refugi_exists("r1")

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_visitor_exception(self, mock_cache, mock_firestore):
        """Test excepció a add_visitor_to_refugi"""
        mock_cache.get.return_value = None
        # Provoquem excepció a get_by_id (que és cridat internament)
        mock_firestore.get_db.side_effect = Exception("Add Visitor Error")
        dao = RefugiLliureDAO()
        assert dao.add_visitor_to_refugi("r1", "u1") is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_exception(self, mock_cache, mock_firestore):
        """Test excepció a remove_visitor_from_refugi"""
        mock_cache.get.return_value = None
        mock_firestore.get_db.side_effect = Exception("Remove Visitor Error")
        dao = RefugiLliureDAO()
        assert dao.remove_visitor_from_refugi("r1", "u1") is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.r2_media_service')
    def test_get_media_metadata_errors(self, mock_r2, mock_firestore):
        """Test errors a get_media_metadata"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        assert dao.get_media_metadata("r1") is None
        
        # Exception
        mock_db.collection.side_effect = Exception("Media Error")
        with pytest.raises(Exception, match="Media Error"):
            dao.get_media_metadata("r1")

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_media_metadata_errors(self, mock_cache, mock_firestore):
        """Test errors a add_media_metadata"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        assert dao.add_media_metadata("r1", {}) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Add Media Error")
        assert dao.add_media_metadata("r1", {}) is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_media_metadata_errors(self, mock_cache, mock_firestore):
        """Test errors a delete_media_metadata"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        success, backup = dao.delete_media_metadata("r1", "k1")
        assert success is False
        
        # Key not found
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {}}
        success, backup = dao.delete_media_metadata("r1", "k1")
        assert success is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Delete Media Error")
        success, backup = dao.delete_media_metadata("r1", "k1")
        assert success is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_multiple_media_metadata_errors(self, mock_cache, mock_firestore):
        """Test errors a delete_multiple_media_metadata"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        success, backups = dao.delete_multiple_media_metadata("r1", ["k1"])
        assert success is False
        
        # Keys not found
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {}}
        success, backups = dao.delete_multiple_media_metadata("r1", ["k1"])
        assert success is False
        assert backups == []
        
        # Exception
        mock_db.collection.side_effect = Exception("Delete Multi Error")
        success, backups = dao.delete_multiple_media_metadata("r1", ["k1"])
        assert success is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_update_refugi_visitors_errors(self, mock_cache, mock_firestore):
        """Test errors a update_refugi_visitors"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Doc not exists
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        dao = RefugiLliureDAO()
        assert dao.update_refugi_visitors("r1", []) is False
        
        # Exception
        mock_db.collection.side_effect = Exception("Update Visitors Error")
        assert dao.update_refugi_visitors("r1", []) is False

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_from_all_refuges_errors(self, mock_cache, mock_firestore):
        """Test errors a remove_visitor_from_all_refuges"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Empty list
        dao = RefugiLliureDAO()
        success, error = dao.remove_visitor_from_all_refuges("u1", [])
        assert success is True
        
        # Inner exception
        mock_db.collection.side_effect = Exception("Inner Error")
        success, error = dao.remove_visitor_from_all_refuges("u1", ["r1"])
        assert success is True # Returns True but logs error
        
        # Outer exception
        with patch('api.daos.refugi_lliure_dao.firestore_service.get_db', side_effect=Exception("Outer Error")):
            success, error = dao.remove_visitor_from_all_refuges("u1", ["r1"])
            assert success is False
            assert "Outer Error" in error

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.r2_media_service')
    def test_get_media_metadata_success(self, mock_r2, mock_firestore):
        """Test get_media_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {'k1': {}}}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        mock_meta = MagicMock()
        mock_meta.to_dict.return_value = {'key': 'k1'}
        mock_media_service.generate_media_metadata_list.return_value = [mock_meta]
        
        dao = RefugiLliureDAO()
        result = dao.get_media_metadata("r1")
        assert result == [{'key': 'k1'}]

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_media_metadata_success(self, mock_cache, mock_firestore):
        """Test add_media_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {}}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = RefugiLliureDAO()
        assert dao.add_media_metadata("r1", {'k1': {}}) is True
        mock_db.collection.return_value.document.return_value.update.assert_called()

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_media_metadata_success(self, mock_cache, mock_firestore):
        """Test delete_media_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {'k1': {'data': 'v1'}}}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = RefugiLliureDAO()
        success, backup = dao.delete_media_metadata("r1", "k1")
        assert success is True
        assert backup == {'data': 'v1'}

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_delete_multiple_media_metadata_success(self, mock_cache, mock_firestore):
        """Test delete_multiple_media_metadata èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'media_metadata': {'k1': {'d': 1}, 'k2': {'d': 2}}}
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = RefugiLliureDAO()
        success, backups = dao.delete_multiple_media_metadata("r1", ["k1", "k2"])
        assert success is True
        assert len(backups) == 2

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_update_refugi_visitors_success(self, mock_cache, mock_firestore):
        """Test update_refugi_visitors èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = RefugiLliureDAO()
        assert dao.update_refugi_visitors("r1", ["u1"]) is True

    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_from_all_refuges_success(self, mock_cache, mock_firestore):
        """Test remove_visitor_from_all_refuges èxit"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        
        dao = RefugiLliureDAO()
        success, error = dao.remove_visitor_from_all_refuges("u1", ["r1"])
        assert success is True
        mock_db.collection.return_value.document.return_value.update.assert_called()
