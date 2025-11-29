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
from api.controllers.refugi_lliure_controller import RefugiLliureController
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


@pytest.mark.controllers
class TestRefugiController:
    """Tests per al RefugiLliureController"""
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_success(self, mock_dao_class, sample_refugi):
        """Test obtenció de refugi per ID exitosa"""
        # Configurar el mock correctament
        mock_dao_instance = MagicMock()
        mock_dao_instance.get_by_id.return_value = sample_refugi
        mock_dao_class.return_value = mock_dao_instance
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001')
        
        assert refugi is not None
        assert error is None
        assert isinstance(refugi, Refugi)
        # Verificar propietats del refugi
        assert refugi.id == sample_refugi.id
        assert refugi.name == sample_refugi.name
        mock_dao_instance.get_by_id.assert_called_once_with('refugi_001')
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_with_visitors(self, mock_dao_class, sample_refugi):
        """Test obtenció de refugi per ID amb visitants inclosos"""
        sample_refugi.visitors = ['uid_001', 'uid_002', 'uid_003']
        
        mock_dao_instance = MagicMock()
        mock_dao_instance.get_by_id.return_value = sample_refugi
        mock_dao_class.return_value = mock_dao_instance
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001', include_visitors=True)
        
        assert refugi is not None
        assert error is None
        assert len(refugi.visitors) == 3
        assert refugi.visitors == ['uid_001', 'uid_002', 'uid_003']
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_without_visitors(self, mock_dao_class, sample_refugi):
        """Test obtenció de refugi per ID sense visitants"""
        sample_refugi.visitors = ['uid_001', 'uid_002', 'uid_003']
        
        mock_dao_instance = MagicMock()
        mock_dao_instance.get_by_id.return_value = sample_refugi
        mock_dao_class.return_value = mock_dao_instance
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001', include_visitors=False)
        
        assert refugi is not None
        assert error is None
        # Verificar que els visitants estan buits
        assert len(refugi.visitors) == 0
        assert refugi.visitors == []
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_not_found(self, mock_dao_class):
        """Test obtenció de refugi no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = None
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('nonexistent')
        
        assert refugi is None
        assert error is not None
        assert 'not found' in error.lower()
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_no_filters(self, mock_dao_class):
        """Test cerca sense filtres"""
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.return_value = {
            'results': [
                {'id': 'ref_001', 'name': 'Test 1'},
                {'id': 'ref_002', 'name': 'Test 2'}
            ],
            'has_filters': False
        }
        
        controller = RefugiLliureController()
        result, error = controller.search_refugis({})
        
        assert result is not None
        assert error is None
        assert 'count' in result
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_with_filters(self, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres"""
        mock_dao = mock_dao_class.return_value
        mock_refugis = [Refugi.from_dict(d) for d in multiple_refugis_data]
        mock_dao.search_refugis.return_value = {
            'results': mock_refugis,
            'has_filters': True
        }
        
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params)
        
        assert result is not None
        assert error is None
        assert result['count'] == len(multiple_refugis_data)
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_with_visitors_included(self, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres i visitants inclosos"""
        mock_dao = mock_dao_class.return_value
        mock_refugis = [Refugi.from_dict(d) for d in multiple_refugis_data]
        # Afegir visitants als refugis
        for refugi in mock_refugis:
            refugi.visitors = ['uid_001', 'uid_002']
        
        mock_dao.search_refugis.return_value = {
            'results': mock_refugis,
            'has_filters': True
        }
        
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params, include_visitors=True)
        
        assert result is not None
        assert error is None
        # Verificar que els visitants estan presents
        assert all('visitors' in refugi for refugi in result['results'])
        assert all(len(refugi['visitors']) == 2 for refugi in result['results'])
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_without_visitors(self, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres però sense visitants"""
        mock_dao = mock_dao_class.return_value
        mock_refugis = [Refugi.from_dict(d) for d in multiple_refugis_data]
        # Afegir visitants als refugis
        for refugi in mock_refugis:
            refugi.visitors = ['uid_001', 'uid_002']
        
        mock_dao.search_refugis.return_value = {
            'results': mock_refugis,
            'has_filters': True
        }
        
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params, include_visitors=False)
        
        assert result is not None
        assert error is None
        # Verificar que els visitants NO estan presents o estan buits
        for refugi in result['results']:
            assert 'visitors' not in refugi or refugi.get('visitors') == []
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_success(self, mock_dao_class):
        """Test health check exitós"""
        mock_dao = mock_dao_class.return_value
        mock_dao.health_check.return_value = {
            'firebase': True,
            'firestore': True,
            'collections_count': 5
        }
        
        controller = RefugiLliureController()
        result, error = controller.health_check()
        
        assert result is not None
        assert error is None
        assert result['status'] == 'healthy'
        assert result['firebase'] is True
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_failure(self, mock_dao_class):
        """Test health check amb error"""
        mock_dao = mock_dao_class.return_value
        mock_dao.health_check.side_effect = Exception('Connection error')
        
        controller = RefugiLliureController()
        result, error = controller.health_check()
        
        assert result is not None
        assert error is not None
        assert result['status'] == 'unhealthy'
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS =====
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció de refugi"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.side_effect = Exception('Database error')
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001')
        
        assert refugi is None
        assert error is not None
        assert 'Internal server error' in error
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_exception(self, mock_dao_class):
        """Test excepció durant la cerca de refugis"""
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.side_effect = Exception('Search error')
        
        controller = RefugiLliureController()
        result, error = controller.search_refugis({})
        
        assert result is None
        assert error is not None
        assert 'Internal server error' in error


# ==================== TESTS DE VIEWS ====================
