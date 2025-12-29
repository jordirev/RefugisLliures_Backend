"""
Tests per al controlador de dubtes
"""
import pytest
from unittest.mock import MagicMock, patch
from api.controllers.doubt_controller import DoubtController
from api.models.doubt import Doubt, Answer

@pytest.mark.controllers
class TestDoubtController:
    """Tests per a DoubtController"""
    
    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_get_doubts_by_refuge_success(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test obtenció de dubtes per refugi exitosa"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        mock_refugi_dao.refugi_exists.return_value = True
        mock_doubt_dao.get_doubts_by_refuge_id.return_value = [MagicMock(spec=Doubt)]
        
        controller = DoubtController()
        doubts, error = controller.get_doubts_by_refuge("ref_1")
        
        assert error is None
        assert len(doubts) == 1
        mock_refugi_dao.refugi_exists.assert_called_with("ref_1")
        mock_doubt_dao.get_doubts_by_refuge_id.assert_called_with("ref_1")

    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_get_doubts_by_refuge_not_found(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test obtenció de dubtes de refugi no existent"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_refugi_dao.refugi_exists.return_value = False
        
        controller = DoubtController()
        doubts, error = controller.get_doubts_by_refuge("ref_1")
        
        assert doubts is None
        assert error == "Refuge not found"

    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_create_doubt_success(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test creació de dubte exitosa"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        mock_refugi_dao.refugi_exists.return_value = True
        mock_time.return_value.isoformat.return_value = "2024-01-01"
        mock_doubt_dao.create_doubt.return_value = MagicMock(spec=Doubt, id="doubt_1")
        
        controller = DoubtController()
        doubt, error = controller.create_doubt("ref_1", "user_1", "Test")
        
        assert error is None
        assert doubt.id == "doubt_1"
        mock_doubt_dao.create_doubt.assert_called()

    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_create_answer_success(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test creació de resposta exitosa"""
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock(spec=Doubt)
        mock_time.return_value.isoformat.return_value = "2024-01-01"
        mock_doubt_dao.create_answer.return_value = MagicMock(spec=Answer, id="ans_1")
        
        controller = DoubtController()
        answer, error = controller.create_answer("doubt_1", "user_1", "Reply")
        
        assert error is None
        assert answer.id == "ans_1"
        mock_doubt_dao.create_answer.assert_called()

    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_delete_doubt_success(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test eliminació de dubte exitosa"""
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock(spec=Doubt)
        mock_doubt_dao.delete_doubt.return_value = True
        
        controller = DoubtController()
        success, error = controller.delete_doubt("doubt_1")
        
        assert success is True
        assert error is None
        mock_doubt_dao.delete_doubt.assert_called_with("doubt_1")

    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_delete_answer_success(self, mock_time, mock_refugi_dao_class, mock_doubt_dao_class):
        """Test eliminació de resposta exitosa"""
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock(spec=Doubt)
        mock_doubt_dao.get_answer_by_id.return_value = MagicMock(spec=Answer)
        mock_doubt_dao.delete_answer.return_value = True
        
        controller = DoubtController()
        success, error = controller.delete_answer("doubt_1", "ans_1")
        
        assert success is True
        assert error is None
        mock_doubt_dao.delete_answer.assert_called_with("doubt_1", "ans_1")
