"""
Tests extensos per a RefugiLliureController
"""
import pytest
from unittest.mock import MagicMock, patch
from api.controllers.refugi_lliure_controller import RefugiLliureController
from api.models.refugi_lliure import Refugi

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
