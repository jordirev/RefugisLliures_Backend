"""
Tests per refugis lliures
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import math
from api.models.refugi_lliure import (
    Refugi,
    Coordinates,
    InfoComplementaria,
    RefugiSearchFilters
)
from api.daos.refugi_lliure_dao import RefugiLliureDAO
from api.models.renovation import Renovation
def floats_are_close(a, b):
    """Comprova si dos floats són gairebé iguals"""
    return math.isclose(a, b, rel_tol=1e-9)
@pytest.fixture
def sample_renovation():
    """Fixture per crear una renovation de mostra"""
    today = date.today()
    return Renovation(
        id='test_renovation',
        creator_uid='test_user',
        refuge_id='refugi_001',
        ini_date=datetime(today.year, today.month, today.day, tzinfo=ZoneInfo('UTC')),
        fin_date=datetime(today.year, today.month, today.day, tzinfo=ZoneInfo('UTC')) + timedelta(days=14),
        description='Test renovation',
        materials_needed='Test materials',
        group_link='https://test.com',
        participants_uids=[]
    )
# ==================== TESTS DE MODELS ====================


@pytest.mark.daos
class TestRefugiDAO:
    """Tests per al RefugiLliureDAO"""
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_found(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test obtenció de refugi per ID (trobat)"""
        # Cache miss
        mock_cache.get.return_value = None
        
        # Configurar Firestore mock
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Executar
        dao = RefugiLliureDAO()
        result = dao.get_by_id('refugi_001')
        
        # Verificacions
        assert result is not None
        assert result.id == sample_refugi_data['id']
        assert result.name == sample_refugi_data['name']
        mock_cache.set.assert_called_once()
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_not_found(self, mock_cache, mock_firestore):
        """Test obtenció de refugi per ID (no trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.get_by_id('nonexistent')
        
        assert result is None
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_from_cache(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test obtenció de refugi des de cache"""
        # Cache hit
        mock_cache.get.return_value = sample_refugi_data
        
        dao = RefugiLliureDAO()
        result = dao.get_by_id('refugi_001')
        
        assert result is not None
        assert result.id == sample_refugi_data['id']
        assert result.name == sample_refugi_data['name']
        # No hauria de cridar Firestore
        mock_firestore.get_db.assert_not_called()
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_no_filters(self, mock_cache, mock_firestore):
        """Test cerca de refugis sense filtres (retorna coordenades)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        coords_data = {
            'refugis_coordinates': [
                {
                    'refuge_id': 'ref_001',
                    'refugi_name': 'Refugi A',
                    'coord': {'long': 1.5, 'lat': 42.5},
                    'geohash': 'abc'
                }
            ]
        }
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = coords_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        results = dao.search_refugis(filters)
        
        assert isinstance(results, dict)
        assert 'results' in results
        assert 'has_filters' in results
        assert results['has_filters'] == False
        assert isinstance(results['results'], list)
        assert len(results['results']) > 0
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_with_name_filter(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test cerca de refugis amb filtre de nom"""
        mock_cache.get_or_fetch_list.return_value = [sample_refugi_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(name='Refugi Test')
        results = dao.search_refugis(filters)
        
        assert isinstance(results, dict)
        assert 'results' in results
        assert 'has_filters' in results
        assert results['has_filters'] == True
        assert isinstance(results['results'], list)
        assert len(results['results']) > 0
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_with_region_filter(self, mock_cache, mock_firestore):
        """Test cerca amb filtre de regió"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(type='garde', condition='bon')
        results = dao.search_refugis(filters)
        
        assert isinstance(results, dict)
        assert 'results' in results
        assert 'has_filters' in results
        assert isinstance(results['results'], list)
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_health_check_success(self, mock_cache, mock_firestore):
        """Test health check exitós"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_collection = MagicMock()
        mock_db.collections.return_value = [mock_collection, mock_collection]
        
        dao = RefugiLliureDAO()
        result = dao.health_check()
        
        assert result['firebase'] is True
        assert result['firestore'] is True
        assert result['collections_count'] == 2
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_health_check_failure(self, mock_firestore):
        """Test health check amb error"""
        mock_firestore.get_db.side_effect = Exception('Connection error')
        
        dao = RefugiLliureDAO()
        
        with pytest.raises(Exception):
            dao.health_check()
    
    def test_has_active_filters_true(self):
        """Test comprovació de filtres actius (true)"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(name='Test', type='garde')
        
        result = dao._has_active_filters(filters)
        
        assert result is True
    
    def test_has_active_filters_false(self):
        """Test comprovació de filtres actius (false)"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        
        result = dao._has_active_filters(filters)
        
        assert result is False
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_refugi_exists_true(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test comprovar existència de refugi (existeix)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.refugi_exists('refugi_001')
        assert result is True
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_refugi_exists_false(self, mock_cache, mock_firestore):
        """Test comprovar existència de refugi (no existeix)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.refugi_exists('nonexistent')
        assert result is False
    
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_refugi_exists_from_cache(self, mock_cache):
        """Test existència des de cache"""
        mock_cache.get.return_value = {'id': 'refugi_001', 'name': 'Test'}
        
        dao = RefugiLliureDAO()
        result = dao.refugi_exists('refugi_001')
        assert result is True
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_visitor_to_refugi_success(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test afegir visitant amb èxit"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Mock per get_by_id
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.add_visitor_to_refugi('refugi_001', 'user_123')
        assert result is True
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_visitor_refugi_not_found(self, mock_cache, mock_firestore):
        """Test afegir visitant a refugi inexistent"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.add_visitor_to_refugi('nonexistent', 'user_123')
        assert result is False
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_add_visitor_already_exists(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test afegir visitant que ja està a la llista"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Refugi amb visitant ja existent
        refugi_with_visitor = sample_refugi_data.copy()
        refugi_with_visitor['visitors'] = ['user_123']
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = refugi_with_visitor
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.add_visitor_to_refugi('refugi_001', 'user_123')
        assert result is True
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_from_refugi_success(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test eliminar visitant amb èxit"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        # Refugi amb visitant
        refugi_with_visitor = sample_refugi_data.copy()
        refugi_with_visitor['visitors'] = ['user_123']
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = refugi_with_visitor
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.remove_visitor_from_refugi('refugi_001', 'user_123')
        assert result is True
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_refugi_not_found(self, mock_cache, mock_firestore):
        """Test eliminar visitant de refugi inexistent"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.remove_visitor_from_refugi('nonexistent', 'user_123')
        assert result is False
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_remove_visitor_not_in_list(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test eliminar visitant que no està a la llista"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.remove_visitor_from_refugi('refugi_001', 'user_999')
        assert result is True

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

