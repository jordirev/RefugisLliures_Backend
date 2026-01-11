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

class TestDoubtControllerExtended:
    """Tests per a DoubtController cobrint casos d'error i lògica de negocis"""

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    def test_get_doubts_by_refuge_errors(self, mock_doubt_dao_class, mock_ref_dao_class):
        """Test get_doubts_by_refuge errors"""
        ctrl = DoubtController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Refuge not found
        mock_ref_dao.refugi_exists.return_value = False
        res, error = ctrl.get_doubts_by_refuge("r1")
        assert res is None
        assert "not found" in error
        
        # Exception
        mock_ref_dao.refugi_exists.side_effect = Exception("Fatal Error")
        res, error = ctrl.get_doubts_by_refuge("r1")
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_create_doubt_errors(self, mock_now, mock_doubt_dao_class, mock_ref_dao_class):
        """Test create_doubt errors"""
        ctrl = DoubtController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Refuge not found
        mock_ref_dao.refugi_exists.return_value = False
        res, error = ctrl.create_doubt("r1", "u1", "msg")
        assert res is None
        assert "not found" in error
        
        # DAO failure
        mock_ref_dao.refugi_exists.return_value = True
        mock_doubt_dao.create_doubt.return_value = None
        res, error = ctrl.create_doubt("r1", "u1", "msg")
        assert res is None
        assert "Error creating doubt" in error
        
        # Exception
        mock_ref_dao.refugi_exists.side_effect = Exception("Fatal Error")
        res, error = ctrl.create_doubt("r1", "u1", "msg")
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    @patch('api.controllers.doubt_controller.get_madrid_now')
    def test_create_answer_errors(self, mock_now, mock_doubt_dao_class, mock_ref_dao_class):
        """Test create_answer errors"""
        ctrl = DoubtController()
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Doubt not found
        mock_doubt_dao.get_doubt_by_id.return_value = None
        res, error = ctrl.create_answer("d1", "u1", "msg")
        assert res is None
        assert "Doubt not found" in error
        
        # Parent answer not found
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock()
        mock_doubt_dao.get_answer_by_id.return_value = None
        res, error = ctrl.create_answer("d1", "u1", "msg", "a_parent")
        assert res is None
        assert "Parent answer not found" in error
        
        # DAO failure
        mock_doubt_dao.get_answer_by_id.return_value = MagicMock()
        mock_doubt_dao.create_answer.return_value = None
        res, error = ctrl.create_answer("d1", "u1", "msg", "a_parent")
        assert res is None
        assert "Error creating answer" in error
        
        # Exception
        mock_doubt_dao.get_doubt_by_id.side_effect = Exception("Fatal Error")
        res, error = ctrl.create_answer("d1", "u1", "msg")
        assert res is None
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    def test_delete_doubt_errors(self, mock_doubt_dao_class, mock_ref_dao_class):
        """Test delete_doubt errors"""
        ctrl = DoubtController()
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Doubt not found
        mock_doubt_dao.get_doubt_by_id.return_value = None
        res, error = ctrl.delete_doubt("d1")
        assert res is False
        assert "not found" in error
        
        # DAO failure
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock()
        mock_doubt_dao.delete_doubt.return_value = False
        res, error = ctrl.delete_doubt("d1")
        assert res is False
        assert "Error deleting doubt" in error
        
        # Exception
        mock_doubt_dao.get_doubt_by_id.side_effect = Exception("Fatal Error")
        res, error = ctrl.delete_doubt("d1")
        assert res is False
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    def test_delete_answer_errors(self, mock_doubt_dao_class, mock_ref_dao_class):
        """Test delete_answer errors"""
        ctrl = DoubtController()
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Doubt not found
        mock_doubt_dao.get_doubt_by_id.return_value = None
        res, error = ctrl.delete_answer("d1", "a1")
        assert res is False
        assert "Doubt not found" in error
        
        # Answer not found
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock()
        mock_doubt_dao.get_answer_by_id.return_value = None
        res, error = ctrl.delete_answer("d1", "a1")
        assert res is False
        assert "Answer not found" in error
        
        # DAO failure
        mock_doubt_dao.get_answer_by_id.return_value = MagicMock()
        mock_doubt_dao.delete_answer.return_value = False
        res, error = ctrl.delete_answer("d1", "a1")
        assert res is False
        assert "Error deleting answer" in error
        
        # Exception
        mock_doubt_dao.get_doubt_by_id.side_effect = Exception("Fatal Error")
        res, error = ctrl.delete_answer("d1", "a1")
        assert res is False
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.DoubtDAO')
    def test_delete_by_creator_errors(self, mock_doubt_dao_class):
        """Test delete_doubts/answers_by_creator errors"""
        ctrl = DoubtController()
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # Doubts DAO failure
        mock_doubt_dao.delete_doubts_by_creator.return_value = (False, "DAO Error")
        res, error = ctrl.delete_doubts_by_creator("u1")
        assert res is False
        assert "DAO Error" in error
        
        # Doubts Exception
        mock_doubt_dao.delete_doubts_by_creator.side_effect = Exception("Fatal")
        res, error = ctrl.delete_doubts_by_creator("u1")
        assert res is False
        assert "Internal server error" in error
        
        # Answers DAO failure
        mock_doubt_dao.delete_answers_by_creator.return_value = (False, "DAO Error")
        res, error = ctrl.delete_answers_by_creator("u1")
        assert res is False
        assert "DAO Error" in error
        
        # Answers Exception
        mock_doubt_dao.delete_answers_by_creator.side_effect = Exception("Fatal")
        res, error = ctrl.delete_answers_by_creator("u1")
        assert res is False
        assert "Internal server error" in error

    @patch('api.controllers.doubt_controller.RefugiLliureDAO')
    @patch('api.controllers.doubt_controller.DoubtDAO')
    def test_success_paths(self, mock_doubt_dao_class, mock_ref_dao_class):
        """Test success paths for all methods"""
        ctrl = DoubtController()
        mock_ref_dao = mock_ref_dao_class.return_value
        mock_doubt_dao = mock_doubt_dao_class.return_value
        
        # get_doubts_by_refuge
        mock_ref_dao.refugi_exists.return_value = True
        mock_doubt_dao.get_doubts_by_refuge_id.return_value = []
        res, error = ctrl.get_doubts_by_refuge("r1")
        assert res == []
        assert error is None
        
        # create_doubt
        mock_doubt = MagicMock(spec=Doubt)
        mock_doubt.id = 'd1'
        mock_doubt_dao.create_doubt.return_value = mock_doubt
        res, error = ctrl.create_doubt("r1", "u1", "msg")
        assert res.id == 'd1'
        
        # create_answer
        mock_answer = MagicMock(spec=Answer)
        mock_answer.id = 'a1'
        mock_doubt_dao.get_doubt_by_id.return_value = MagicMock()
        mock_doubt_dao.create_answer.return_value = mock_answer
        res, error = ctrl.create_answer("d1", "u1", "msg")
        assert res.id == 'a1'
        
        # delete_doubt
        mock_doubt_dao.delete_doubt.return_value = True
        res, error = ctrl.delete_doubt("d1")
        assert res is True
        
        # delete_answer
        mock_doubt_dao.get_answer_by_id.return_value = MagicMock()
        mock_doubt_dao.delete_answer.return_value = True
        res, error = ctrl.delete_answer("d1", "a1")
        assert res is True
        
        # delete_doubts_by_creator
        mock_doubt_dao.delete_doubts_by_creator.return_value = (True, None)
        res, error = ctrl.delete_doubts_by_creator("u1")
        assert res is True
        
        # delete_answers_by_creator
        mock_doubt_dao.delete_answers_by_creator.return_value = (True, None)
        res, error = ctrl.delete_answers_by_creator("u1")
        assert res is True
