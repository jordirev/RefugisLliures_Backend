"""
Tests per al controlador d'experiències
"""
import pytest
from unittest.mock import MagicMock, patch
from api.controllers.experience_controller import ExperienceController
from api.models.experience import Experience


@pytest.mark.controllers
class TestExperienceController:
    """Tests per a ExperienceController"""
    
    @patch('api.controllers.experience_controller.ExperienceDAO')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.experience_controller.get_madrid_now')
    def test_get_experiences_by_refuge_success(self, mock_time, mock_r2, mock_user_dao, mock_refugi_controller, mock_refugi_dao_class, mock_exp_dao_class):
        """Test obtenció d'experiències per refugi exitosa"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_exp_dao = mock_exp_dao_class.return_value
        
        mock_refugi_dao.refugi_exists.return_value = True
        mock_exp_dao.get_experiences_by_refuge_id.return_value = [MagicMock(spec=Experience)]
        
        controller = ExperienceController()
        experiences, error = controller.get_experiences_by_refuge("ref_1")
        
        assert error is None
        assert len(experiences) == 1
        mock_refugi_dao.refugi_exists.assert_called_with("ref_1")

    @patch('api.controllers.experience_controller.ExperienceDAO')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.experience_controller.get_madrid_now')
    def test_create_experience_success(self, mock_time, mock_r2, mock_user_dao_class, mock_refugi_controller_class, mock_refugi_dao_class, mock_exp_dao_class):
        """Test creació d'experiència exitosa sense fitxers"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        
        mock_refugi_dao.refugi_exists.return_value = True
        mock_time.return_value.isoformat.return_value = "2024-01-01"
        
        mock_exp = MagicMock(spec=Experience, id="exp_1")
        mock_exp_dao.create_experience.return_value = mock_exp
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        
        controller = ExperienceController()
        experience, upload_result, error = controller.create_experience("ref_1", "user_1", "Comment")
        
        assert error is None
        assert experience.id == "exp_1"
        mock_user_dao.increment_shared_experiences.assert_called_with("user_1")

    @patch('api.controllers.experience_controller.ExperienceDAO')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.r2_media_service.get_refugi_media_service')
    @patch('api.controllers.experience_controller.get_madrid_now')
    def test_delete_experience_success(self, mock_time, mock_r2, mock_user_dao_class, mock_refugi_controller_class, mock_refugi_dao_class, mock_exp_dao_class):
        """Test eliminació d'experiència exitosa"""
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_refugi_controller = mock_refugi_controller_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        
        mock_exp = MagicMock(spec=Experience, id="exp_1", refuge_id="ref_1", creator_uid="user_1", media_keys=["key1"])
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        mock_refugi_controller.delete_multiple_refugi_media.return_value = (True, None)
        mock_exp_dao.delete_experience.return_value = (True, None)
        
        controller = ExperienceController()
        success, error = controller.delete_experience("exp_1")
        
        assert success is True
        assert error is None
        mock_refugi_controller.delete_multiple_refugi_media.assert_called()
        mock_user_dao.decrement_shared_experiences.assert_called_with("user_1")


class TestExperienceControllerExtended:
    """Tests per a ExperienceController cobrint casos d'error i excepcions"""

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_get_experiences_by_refuge_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                             mock_ref_ctrl_class, mock_user_dao_class, 
                                             mock_r2, mock_now):
        """Test get_experiences_by_refuge errors"""
        mock_refuge_dao = mock_ref_dao_class.return_value
        ctrl = ExperienceController()
        
        # Refuge not found
        mock_refuge_dao.refugi_exists.return_value = False
        res, error = ctrl.get_experiences_by_refuge("r1")
        assert res is None
        assert "not found" in error
        
        # Exception
        mock_refuge_dao.refugi_exists.side_effect = Exception("Error")
        res, error = ctrl.get_experiences_by_refuge("r1")
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_create_experience_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                     mock_ref_ctrl_class, mock_user_dao_class, 
                                     mock_r2, mock_now):
        """Test create_experience errors"""
        mock_now.return_value.isoformat.return_value = "2024-01-01T00:00:00"
        mock_refuge_dao = mock_ref_dao_class.return_value
        mock_exp_dao = mock_exp_dao_class.return_value
        
        ctrl = ExperienceController()
        
        # Refuge not found
        mock_refuge_dao.refugi_exists.return_value = False
        exp, upload, error = ctrl.create_experience("r1", "u1", "comment")
        assert exp is None
        assert "not found" in error
        
        # DAO failure
        mock_refuge_dao.refugi_exists.return_value = True
        mock_exp_dao.create_experience.return_value = None
        exp, upload, error = ctrl.create_experience("r1", "u1", "comment")
        assert exp is None
        assert "Error creating experience" in error
        
        # Media upload failure
        mock_exp = MagicMock(spec=Experience)
        mock_exp.id = "e1"
        mock_exp_dao.create_experience.return_value = mock_exp
        
        with patch.object(ctrl, '_upload_experience_media_to_refuge', return_value=(None, "Upload Error")):
            exp, upload, error = ctrl.create_experience("r1", "u1", "comment", files=[MagicMock()])
            assert error == "Upload Error"
            
        # add_media_keys failure
        with patch.object(ctrl, '_upload_experience_media_to_refuge', return_value=({'uploaded': [{'key': 'k1'}]}, None)):
            mock_exp_dao.add_media_keys_to_experience.return_value = (False, "Add Keys Error")
            exp, upload, error = ctrl.create_experience("r1", "u1", "comment", files=[MagicMock()])
            assert "Error actualitzant media_keys" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_update_experience_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                     mock_ref_ctrl_class, mock_user_dao_class, 
                                     mock_r2, mock_now):
        """Test update_experience errors"""
        mock_now.return_value.isoformat.return_value = "2024-01-01T00:00:00"
        mock_exp_dao = mock_exp_dao_class.return_value
        
        ctrl = ExperienceController()
        
        # Experience not found
        mock_exp_dao.get_experience_by_id.return_value = None
        exp, upload, error = ctrl.update_experience("e1", "new comment")
        assert exp is None
        assert "not found" in error
        
        # Media upload failure
        mock_exp = MagicMock(spec=Experience)
        mock_exp.refuge_id = "r1"
        mock_exp.creator_uid = "u1"
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        
        with patch.object(ctrl, '_upload_experience_media_to_refuge', return_value=(None, "Upload Error")):
            exp, upload, error = ctrl.update_experience("e1", files=[MagicMock()])
            assert error == "Upload Error"
            
        # update_experience failure
        mock_exp_dao.update_experience.return_value = (None, "Update Error")
        exp, upload, error = ctrl.update_experience("e1", "new comment")
        assert exp is None
        assert "Update Error" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_delete_experience_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                     mock_ref_ctrl_class, mock_user_dao_class, 
                                     mock_r2, mock_now):
        """Test delete_experience errors"""
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_ref_ctrl = mock_ref_ctrl_class.return_value
        
        ctrl = ExperienceController()
        
        # Experience not found
        mock_exp_dao.get_experience_by_id.return_value = None
        success, error = ctrl.delete_experience("e1")
        assert success is False
        assert "not found" in error
        
        # Media delete failure
        mock_exp = MagicMock(spec=Experience)
        mock_exp.refuge_id = "r1"
        mock_exp.media_keys = ["k1"]
        mock_exp.creator_uid = "u1"
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        mock_ref_ctrl.delete_multiple_refugi_media.return_value = (False, "Delete Error")
        success, error = ctrl.delete_experience("e1")
        assert success is False
        assert "Error deleting some refuge media" in error
        
        # DAO failure
        mock_ref_ctrl.delete_multiple_refugi_media.return_value = (True, None)
        mock_exp_dao.delete_experience.return_value = (False, "DAO Error")
        success, error = ctrl.delete_experience("e1")
        assert success is False
        assert "DAO Error" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_upload_experience_media_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                           mock_ref_ctrl_class, mock_user_dao_class, 
                                           mock_r2, mock_now):
        """Test _upload_experience_media_to_refuge errors"""
        ctrl = ExperienceController()
        
        # Upload failure
        with patch('api.controllers.experience_controller.RefugiLliureController') as mock_ref_ctrl_local:
            mock_ref_ctrl_local.return_value.upload_refugi_media.return_value = (None, "Upload Error")
            res, error = ctrl._upload_experience_media_to_refuge("e1", "r1", [], "u1", "now")
            assert res is None
            assert "Upload Error" in error
            
            # Exception
            mock_ref_ctrl_local.return_value.upload_refugi_media.side_effect = Exception("Error")
            res, error = ctrl._upload_experience_media_to_refuge("e1", "r1", [], "u1", "now")
            assert res is None

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_delete_experiences_by_creator_errors(self, mock_exp_dao_class, mock_ref_dao_class, 
                                                 mock_ref_ctrl_class, mock_user_dao_class, 
                                                 mock_r2, mock_now):
        """Test delete_experiences_by_creator errors"""
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_exp_dao.delete_experiences_by_creator.return_value = (False, "DAO Error")
        
        ctrl = ExperienceController()
        
        # DAO failure
        success, error = ctrl.delete_experiences_by_creator("u1")
        assert success is False
        assert "DAO Error" in error
        
        # Exception
        mock_exp_dao.delete_experiences_by_creator.side_effect = Exception("Error")
        success, error = ctrl.delete_experiences_by_creator("u1")
        assert success is False
        assert "Internal server error" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_create_experience_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                      mock_ref_ctrl_class, mock_user_dao_class, 
                                      mock_r2, mock_now):
        """Test create_experience èxit"""
        mock_now.return_value.isoformat.return_value = "2024-01-01T00:00:00"
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        
        mock_ref_dao.refugi_exists.return_value = True
        mock_exp = MagicMock(spec=Experience)
        mock_exp.id = "e1"
        mock_exp_dao.create_experience.return_value = mock_exp
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        
        ctrl = ExperienceController()
        exp, upload, error = ctrl.create_experience("r1", "u1", "comment")
        
        assert exp == mock_exp
        assert error is None
        mock_user_dao.increment_shared_experiences.assert_called_with("u1")

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_update_experience_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                      mock_ref_ctrl_class, mock_user_dao_class, 
                                      mock_r2, mock_now):
        """Test update_experience èxit"""
        mock_now.return_value.isoformat.return_value = "2024-01-01T00:00:00"
        mock_exp_dao = mock_exp_dao_class.return_value
        
        mock_exp = MagicMock(spec=Experience)
        mock_exp.refuge_id = "r1"
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        mock_exp_dao.update_experience.return_value = (True, None)
        
        ctrl = ExperienceController()
        exp, upload, error = ctrl.update_experience("e1", "new comment")
        
        assert exp == mock_exp
        assert error is None

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_delete_experience_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                      mock_ref_ctrl_class, mock_user_dao_class, 
                                      mock_r2, mock_now):
        """Test delete_experience èxit"""
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_user_dao = mock_user_dao_class.return_value
        
        mock_exp = MagicMock(spec=Experience)
        mock_exp.creator_uid = "u1"
        mock_exp.media_keys = []
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        mock_exp_dao.delete_experience.return_value = (True, None)
        
        ctrl = ExperienceController()
        success, error = ctrl.delete_experience("e1")
        
        assert success is True
        mock_user_dao.decrement_shared_experiences.assert_called_with("u1")

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_controller_exceptions(self, mock_exp_dao_class, mock_ref_dao_class, 
                                  mock_ref_ctrl_class, mock_user_dao_class, 
                                  mock_r2, mock_now):
        """Test excepcions en mètodes del controlador"""
        ctrl = ExperienceController()
        mock_refuge_dao = mock_ref_dao_class.return_value
        mock_exp_dao = mock_exp_dao_class.return_value
        
        # create_experience exception
        mock_refuge_dao.refugi_exists.side_effect = Exception("Create Error")
        exp, upload, error = ctrl.create_experience("r1", "u1", "comment")
        assert exp is None
        assert "Create Error" in error
        
        # update_experience exception
        mock_exp_dao.get_experience_by_id.side_effect = Exception("Update Error")
        exp, upload, error = ctrl.update_experience("e1", "comment")
        assert exp is None
        assert "Update Error" in error
        
        # delete_experience exception
        mock_exp_dao.get_experience_by_id.side_effect = Exception("Delete Error")
        success, error = ctrl.delete_experience("e1")
        assert success is False
        assert "Delete Error" in error
        
        # delete_experience inner exception (media delete)
        mock_exp = MagicMock(spec=Experience)
        mock_exp.media_keys = ["k1"]
        mock_exp_dao.get_experience_by_id.side_effect = None
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        with patch.object(ctrl.refugi_controller, 'delete_multiple_refugi_media', side_effect=Exception("Inner Error")):
            success, error = ctrl.delete_experience("e1")
            assert success is False
            assert "Error deleting experience media" in error

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_delete_experiences_by_creator_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                                  mock_ref_ctrl_class, mock_user_dao_class, 
                                                  mock_r2, mock_now):
        """Test delete_experiences_by_creator èxit"""
        mock_exp_dao = mock_exp_dao_class.return_value
        mock_exp_dao.delete_experiences_by_creator.return_value = (True, None)
        
        ctrl = ExperienceController()
        success, error = ctrl.delete_experiences_by_creator("u1")
        
        assert success is True
        assert error is None

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_update_experience_with_files_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                                 mock_ref_ctrl_class, mock_user_dao_class, 
                                                 mock_r2, mock_now):
        """Test update_experience amb fitxers èxit"""
        mock_now.return_value.isoformat.return_value = "2024-01-01T00:00:00"
        mock_exp_dao = mock_exp_dao_class.return_value
        
        mock_exp = MagicMock(spec=Experience)
        mock_exp.refuge_id = "r1"
        mock_exp.creator_uid = "u1"
        mock_exp_dao.get_experience_by_id.return_value = mock_exp
        mock_exp_dao.update_experience.return_value = (True, None)
        
        ctrl = ExperienceController()
        with patch.object(ctrl, '_upload_experience_media_to_refuge', return_value=({'uploaded': [{'key': 'k1'}]}, None)):
            exp, upload, error = ctrl.update_experience("e1", files=[MagicMock()])
            assert error is None
            assert upload['uploaded'][0]['key'] == 'k1'

    @patch('api.controllers.experience_controller.get_madrid_now')
    @patch('api.controllers.experience_controller.r2_media_service')
    @patch('api.controllers.experience_controller.UserDAO')
    @patch('api.controllers.experience_controller.RefugiLliureController')
    @patch('api.controllers.experience_controller.RefugiLliureDAO')
    @patch('api.controllers.experience_controller.ExperienceDAO')
    def test_upload_experience_media_success(self, mock_exp_dao_class, mock_ref_dao_class, 
                                            mock_ref_ctrl_class, mock_user_dao_class, 
                                            mock_r2, mock_now):
        """Test _upload_experience_media_to_refuge èxit"""
        ctrl = ExperienceController()
        with patch('api.controllers.experience_controller.RefugiLliureController') as mock_ref_ctrl_local:
            mock_ref_ctrl_local.return_value.upload_refugi_media.return_value = ({'uploaded': []}, None)
            res, error = ctrl._upload_experience_media_to_refuge("e1", "r1", [], "u1", "now")
            assert res == {'uploaded': []}
            assert error is None
