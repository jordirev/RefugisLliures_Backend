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
