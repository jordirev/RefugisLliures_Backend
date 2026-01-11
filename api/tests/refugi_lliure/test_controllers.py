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
        refugi, error = controller.get_refugi_by_id('refugi_001', is_authenticated=True)
        
        assert refugi is not None
        assert error is None
        assert isinstance(refugi, Refugi)
        # Verificar propietats del refugi
        assert refugi.id == sample_refugi.id
        assert refugi.name == sample_refugi.name
        mock_dao_instance.get_by_id.assert_called_once_with('refugi_001')
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_authenticated_includes_visitors(self, mock_dao_class, sample_refugi):
        """Test obtenció de refugi per ID amb usuari autenticat - inclou visitants"""
        sample_refugi.visitors = ['uid_001', 'uid_002', 'uid_003']
        
        mock_dao_instance = MagicMock()
        mock_dao_instance.get_by_id.return_value = sample_refugi
        mock_dao_class.return_value = mock_dao_instance
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001', is_authenticated=True)
        
        assert refugi is not None
        assert error is None
        assert len(refugi.visitors) == 3
        assert refugi.visitors == ['uid_001', 'uid_002', 'uid_003']
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_unauthenticated_excludes_visitors(self, mock_dao_class, sample_refugi):
        """Test obtenció de refugi per ID sense autenticació - exclou visitants"""
        sample_refugi.visitors = ['uid_001', 'uid_002', 'uid_003']
        sample_refugi.images_metadata = [{'key': 'test'}]
        
        mock_dao_instance = MagicMock()
        mock_dao_instance.get_by_id.return_value = sample_refugi
        mock_dao_class.return_value = mock_dao_instance
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001', is_authenticated=False)
        
        assert refugi is not None
        assert error is None
        # Verificar que els visitants estan buits
        assert len(refugi.visitors) == 0
        assert refugi.visitors == []
        # Verificar que les images_metadata estan buides
        assert refugi.images_metadata == []
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_not_found(self, mock_dao_class):
        """Test obtenció de refugi no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = None
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('nonexistent', is_authenticated=True)
        
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
        result, error = controller.search_refugis({}, is_authenticated=True)
        
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
        result, error = controller.search_refugis(query_params, is_authenticated=True)
        
        assert result is not None
        assert error is None
        assert result['count'] == len(multiple_refugis_data)
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_authenticated_includes_visitors(self, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres i usuari autenticat - inclou visitants"""
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
        result, error = controller.search_refugis(query_params, is_authenticated=True)
        
        assert result is not None
        assert error is None
        # Verificar que els visitants estan presents
        assert all('visitors' in refugi for refugi in result['results'])
        assert all(len(refugi['visitors']) == 2 for refugi in result['results'])
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_unauthenticated_excludes_visitors(self, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres però sense autenticació - exclou visitants"""
        mock_dao = mock_dao_class.return_value
        mock_refugis = [Refugi.from_dict(d) for d in multiple_refugis_data]
        # Afegir visitants als refugis
        for refugi in mock_refugis:
            refugi.visitors = ['uid_001', 'uid_002']
            refugi.images_metadata = [{'key': 'test'}]
        
        mock_dao.search_refugis.return_value = {
            'results': mock_refugis,
            'has_filters': True
        }
        
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params, is_authenticated=False)
        
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
        refugi, error = controller.get_refugi_by_id('refugi_001', is_authenticated=True)
        
        assert refugi is None
        assert error is not None
        assert 'Internal server error' in error
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refugis_exception(self, mock_dao_class):
        """Test excepció durant la cerca de refugis"""
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.side_effect = Exception('Search error')
        
        controller = RefugiLliureController()
        result, error = controller.search_refugis({}, is_authenticated=True)
        
        assert result is None
        assert error is not None
        assert 'Internal server error' in error


    @patch('api.controllers.refugi_lliure_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_media_success(self, mock_dao_class, mock_get_service):
        """Test obtenció de mitjans d'un refugi exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_r2_service = mock_get_service.return_value
        
        mock_dao.get_media_metadata.return_value = [
            {'key': 'key1', 'url': 'url1', 'uploaded_at': '2024-01-01'},
            {'key': 'key2', 'url': 'url2', 'uploaded_at': '2024-01-02'}
        ]
        
        # Mock generació URL prefirmada - NO s'utilitza en aquest mètode segons el codi actual
        # mock_r2_service.generate_presigned_url.side_effect = lambda key, exp: f"presigned_{key}"
        
        controller = RefugiLliureController()
        media_list, error = controller.get_refugi_media('refugi_123', 3600)
        
        assert error is None
        assert len(media_list) == 2
        assert any(m['key'] == 'key1' and m['url'] == 'url1' for m in media_list)
        assert any(m['key'] == 'key2' and m['url'] == 'url2' for m in media_list)

    @patch('api.controllers.refugi_lliure_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_media_not_found(self, mock_dao_class, mock_get_service):
        """Test obtenció de mitjans de refugi no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_media_metadata.return_value = None
        
        controller = RefugiLliureController()
        media_list, error = controller.get_refugi_media('nonexistent', 3600)
        
        assert media_list is None
        assert "not found" in error.lower()

    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_upload_refugi_media_success(self, mock_dao_class, mock_get_service, mock_user_dao_class):
        """Test pujada de mitjans exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_r2_service = mock_get_service.return_value
        mock_user_dao = mock_user_dao_class.return_value
        
        # Mock refugi existent
        mock_dao.get_by_id.return_value = MagicMock()
        
        # Mock pujada R2
        mock_r2_service.upload_file.return_value = {'key': "path/to/file.jpg"}
        mock_r2_service.generate_presigned_url.return_value = "http://presigned"
        
        # Mock generació objecte metadata
        mock_metadata_obj = MagicMock()
        mock_metadata_obj.to_dict.return_value = {'key': "path/to/file.jpg", 'url': "http://presigned"}
        mock_r2_service.generate_media_metadata_from_dict.return_value = mock_metadata_obj
        
        # Mock actualització metadades
        mock_dao.add_media_metadata.return_value = True
        
        # Mock increment usuari
        mock_user_dao.increment_uploaded_photos.return_value = True
        
        controller = RefugiLliureController()
        files = [MagicMock(name='file1.jpg')]
        result, error = controller.upload_refugi_media('refugi_123', files, 'user_123')
        
        assert error is None
        assert len(result['uploaded']) == 1
        assert result['uploaded'][0]['key'] == "path/to/file.jpg"
        mock_r2_service.upload_file.assert_called()
        mock_dao.add_media_metadata.assert_called()

    @patch('api.daos.experience_dao.ExperienceDAO')
    @patch('api.controllers.refugi_lliure_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_delete_refugi_media_success(self, mock_dao_class, mock_get_service, mock_exp_dao_class):
        """Test eliminació de mitjà exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_r2_service = mock_get_service.return_value
        
        # Mock refugi amb metadades
        refugi_mock = MagicMock()
        refugi_mock.media_metadata = {
            'key1': {'key': 'key1', 'creator_uid': 'user_123'}
        }
        mock_dao.get_by_id.return_value = refugi_mock
        
        # Mock eliminació R2
        mock_r2_service.delete_file.return_value = True
        
        # Mock eliminació metadades (retorna success, backup)
        mock_dao.delete_media_metadata.return_value = (True, {'key': 'key1', 'creator_uid': 'user_123'})
        
        # Mock actualització metadades (per si de cas, tot i que delete usa delete_media_metadata)
        mock_dao.update_media_metadata.return_value = True
        
        controller = RefugiLliureController()
        success, error = controller.delete_refugi_media('refugi_123', 'key1')
        
        assert success is True
        assert error is None
        mock_r2_service.delete_file.assert_called_with('key1')
        mock_dao.delete_media_metadata.assert_called()

class TestRefugiLliureControllerExtended:
    """Tests per a RefugiLliureController cobrint casos d'error i lògica d'autenticació"""

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    def test_get_refugi_by_id_logic(self, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test get_refugi_by_id amb i sense autenticació"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        
        # Not found
        mock_ref_dao.get_by_id.return_value = None
        res, error = ctrl.get_refugi_by_id("r1", True)
        assert res is None
        assert "not found" in error
        
        # Authenticated
        mock_refugi = MagicMock(spec=Refugi)
        mock_refugi.visitors = ["u1"]
        mock_refugi.images_metadata = ["m1"]
        mock_ref_dao.get_by_id.return_value = mock_refugi
        res, error = ctrl.get_refugi_by_id("r1", True)
        assert res.visitors == ["u1"]
        assert res.images_metadata == ["m1"]
        
        # Unauthenticated
        res, error = ctrl.get_refugi_by_id("r1", False)
        assert res.visitors == []
        assert res.images_metadata == []
        
        # Exception
        mock_ref_dao.get_by_id.side_effect = Exception("Error")
        res, error = ctrl.get_refugi_by_id("r1", True)
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    def test_search_refugis_logic(self, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test search_refugis amb i sense autenticació"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        
        # Case with filters and authenticated
        mock_refugi = MagicMock(spec=Refugi)
        mock_refugi.visitors = ["u1"]
        mock_ref_dao.search_refugis.return_value = {'results': [mock_refugi], 'has_filters': True}
        
        with patch('api.mappers.refugi_lliure_mapper.RefugiLliureMapper.format_search_response', return_value={'results': []}):
            res, error = ctrl.search_refugis({'name': 'Test'}, True)
            assert error is None
            assert mock_refugi.visitors == ["u1"]
            
            # Unauthenticated
            res, error = ctrl.search_refugis({'name': 'Test'}, False)
            assert mock_refugi.visitors == []
            
        # Case without filters
        mock_ref_dao.search_refugis.return_value = {'results': [], 'has_filters': False}
        with patch('api.mappers.refugi_lliure_mapper.RefugiLliureMapper.format_search_response_from_raw_data', return_value={'results': []}):
            res, error = ctrl.search_refugis({}, True)
            assert error is None
            
        # Exception
        mock_ref_dao.search_refugis.side_effect = Exception("Error")
        res, error = ctrl.search_refugis({}, True)
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    def test_health_check_errors(self, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test health_check errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        
        mock_ref_dao.health_check.side_effect = Exception("Health Error")
        res, error = ctrl.health_check()
        assert res['status'] == 'unhealthy'
        assert "Health Error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    def test_get_refugi_media_errors(self, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test get_refugi_media errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        
        # Not found
        mock_ref_dao.get_media_metadata.return_value = None
        res, error = ctrl.get_refugi_media("r1")
        assert res is None
        assert "not found" in error
        
        # Exception
        mock_ref_dao.get_media_metadata.side_effect = Exception("Error")
        res, error = ctrl.get_refugi_media("r1")
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.get_madrid_now')
    def test_upload_refugi_media_errors(self, mock_now, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test upload_refugi_media errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        # Refugi not found
        mock_ref_dao.refugi_exists.return_value = False
        res, error = ctrl.upload_refugi_media("r1", [], "u1")
        assert res is None
        assert "not found" in error
        
        # File upload failure (ValueError)
        mock_ref_dao.refugi_exists.return_value = True
        mock_file = MagicMock()
        mock_file.name = "f1.jpg"
        mock_media_service.upload_file.side_effect = ValueError("Invalid file")
        res, error = ctrl.upload_refugi_media("r1", [mock_file], "u1")
        assert len(res['failed']) == 1
        assert "Invalid file" in res['failed'][0]['error']
        
        # File upload failure (General Exception)
        mock_media_service.upload_file.side_effect = Exception("Upload Error")
        res, error = ctrl.upload_refugi_media("r1", [mock_file], "u1")
        assert len(res['failed']) == 1
        assert "Error intern" in res['failed'][0]['error']
        
        # Firestore save failure
        mock_media_service.upload_file.side_effect = None
        mock_media_service.upload_file.return_value = {'key': 'k1'}
        mock_ref_dao.add_media_metadata.return_value = False
        res, error = ctrl.upload_refugi_media("r1", [mock_file], "u1")
        assert res is None
        assert "Error intern guardant les metadades" in error
        
        # General exception
        mock_ref_dao.refugi_exists.side_effect = Exception("Fatal Error")
        res, error = ctrl.upload_refugi_media("r1", [], "u1")
        assert res is None
        assert "Fatal Error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_refugi_media_errors(self, mock_exp_dao_class, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test delete_refugi_media errors"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        # Not found
        mock_ref_dao.delete_media_metadata.return_value = (False, None)
        res, error = ctrl.delete_refugi_media("r1", "k1")
        assert res is False
        assert "not found" in error
        
        # R2 delete failure (Rollback)
        mock_ref_dao.delete_media_metadata.return_value = (True, {'experience_id': 'e1'})
        mock_media_service.delete_file.side_effect = Exception("R2 Error")
        res, error = ctrl.delete_refugi_media("r1", "k1")
        print(f"DEBUG FULL ERROR: {error}")
        assert res is False
        assert "Error deleting file from storage" in error
        mock_ref_dao.add_media_metadata.assert_called()
        
        # General exception
        mock_ref_dao.delete_media_metadata.side_effect = Exception("Fatal Error")
        res, error = ctrl.delete_refugi_media("r1", "k1")
        assert res is False
        assert "Fatal Error" in error

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_multiple_refugi_media_errors(self, mock_exp_dao_class, mock_user_dao_class, mock_ref_dao_class, mock_r2):
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
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    def test_upload_refugi_media_success(self, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test upload_refugi_media èxit"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        mock_ref_dao.refugi_exists.return_value = True
        mock_file = MagicMock()
        mock_file.name = "f1.jpg"
        mock_file.content_type = "image/jpeg"
        mock_media_service.upload_file.return_value = {'key': 'k1'}
        
        mock_meta = MagicMock()
        mock_meta.to_dict.return_value = {'key': 'k1'}
        mock_media_service.generate_media_metadata_from_dict.return_value = mock_meta
        mock_ref_dao.add_media_metadata.return_value = True
        
        res, error = ctrl.upload_refugi_media("r1", [mock_file], "u1")
        assert error is None
        assert len(res['uploaded']) == 1
        mock_user_dao.add_uploaded_photos_keys.assert_called()

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_refugi_media_success(self, mock_exp_dao_class, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test delete_refugi_media èxit"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        mock_ref_dao.delete_media_metadata.return_value = (True, {'creator_uid': 'u1', 'experience_id': 'e1'})
        
        res, error = ctrl.delete_refugi_media("r1", "k1")
        assert res is True
        assert error is None
        mock_media_service.delete_file.assert_called_with("k1")
        mock_user_dao.remove_uploaded_photos_keys.assert_called()

    @patch('api.controllers.refugi_lliure_controller.r2_media_service')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.UserDAO')
    @patch('api.controllers.refugi_lliure_controller.ExperienceDAO', create=True)
    def test_delete_multiple_refugi_media_success(self, mock_exp_dao_class, mock_user_dao_class, mock_ref_dao_class, mock_r2):
        """Test delete_multiple_refugi_media èxit"""
        ctrl = RefugiLliureController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        mock_media_service = mock_r2.get_refugi_media_service.return_value
        
        mock_ref_dao.delete_multiple_media_metadata.return_value = (True, [{'key': 'k1', 'creator_uid': 'u1', 'experience_id': 'e1'}])
        mock_media_service.delete_files.return_value = {'deleted': ['k1'], 'failed': []}
        
        res, error = ctrl.delete_multiple_refugi_media("r1", ["k1"])
        assert res is True
        assert error is None
        mock_user_dao.remove_uploaded_photos_keys.assert_called()

