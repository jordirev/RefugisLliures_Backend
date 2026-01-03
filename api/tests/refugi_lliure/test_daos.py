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


# ==================== TESTS DE CONTROLLERS ====================
