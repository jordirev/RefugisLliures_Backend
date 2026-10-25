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
    
    
    
    
    
    
    
    
    
    @patch('api.controllers.refugi_lliure_controller.check_database', return_value=True)
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_success(self, mock_dao_class, mock_check_db):
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
        assert result['database'] is True
    
    @patch('api.controllers.refugi_lliure_controller.check_database', return_value=True)
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_failure(self, mock_dao_class, mock_check_db):
        """Test health check amb error"""
        mock_dao = mock_dao_class.return_value
        mock_dao.health_check.side_effect = Exception('Connection error')
        
        controller = RefugiLliureController()
        result, error = controller.health_check()
        
        assert result is not None
        assert error is not None
        assert result['status'] == 'unhealthy'
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS =====
    
    


class TestRefugiLliureControllerExtended:
    """Tests per a RefugiLliureController cobrint casos d'error i lògica d'autenticació"""


    @patch('api.controllers.refugi_lliure_controller.check_database', return_value=True)
    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_errors(self, mock_ref_dao_class, mock_r2, mock_check_db):
        """Test health_check errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        
        mock_ref_dao.health_check.side_effect = Exception("Health Error")
        res, error = ctrl.health_check()
        assert res['status'] == 'unhealthy'
        assert "Health Error" not in error and "Health Error" not in res['message']


    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_multiple_refugi_media_errors(self, mock_exp_dao_class, mock_ref_dao_class, mock_r2):
        """Test delete_multiple_refugi_media errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        # Not found
        mock_ref_dao.delete_multiple_media_metadata.return_value = (False, [])
        res, error = ctrl.delete_multiple_refugi_media("r1", ["k1"])
        assert res is False
        assert "not found" in error
        
        # R2 delete partial failure (Rollback)
        mock_ref_dao.delete_multiple_media_metadata.return_value = (True, [{'key': 'k1', 'experience_id': 'e1'}])
        mock_media_service.delete_files.return_value = {'deleted': [], 'failed': ['k1']}
        res, error = ctrl.delete_multiple_refugi_media("r1", ["k1"])
        assert res is False
        assert "Error deleting files from storage" in error
        mock_ref_dao.add_media_metadata.assert_called()
        
        # General exception
        mock_ref_dao.delete_multiple_media_metadata.side_effect = Exception("Fatal Error")
        res, error = ctrl.delete_multiple_refugi_media("r1", ["k1"])
        assert res is False
        assert "Fatal Error" in error


    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_multiple_refugi_media_success(self, mock_exp_dao_class, mock_ref_dao_class, mock_r2):
        """Test delete_multiple_refugi_media èxit"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        mock_ref_dao.delete_multiple_media_metadata.return_value = (True, [{'key': 'k1', 'creator_uid': 'u1', 'experience_id': 'e1'}])
        mock_media_service.delete_files.return_value = {'deleted': ['k1'], 'failed': []}
        
        res, error = ctrl.delete_multiple_refugi_media("r1", ["k1"])
        assert res is True
        assert error is None

