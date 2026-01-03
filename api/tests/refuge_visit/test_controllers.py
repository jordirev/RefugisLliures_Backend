"""
Tests per al controlador de visites a refugi
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from api.controllers.refuge_visit_controller import RefugeVisitController
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.controllers
class TestRefugeVisitController:
    """Tests per a RefugeVisitController"""
    
    @pytest.fixture
    def controller(self):
        with patch('api.controllers.refuge_visit_controller.RefugeVisitDAO'), \
             patch('api.controllers.refuge_visit_controller.RefugiLliureDAO'), \
             patch('api.controllers.refuge_visit_controller.UserController'):
            return RefugeVisitController()

    def test_get_refuge_visits_success(self, controller):
        """Test obtenir visites de refugi amb èxit"""
        controller.refuge_dao.get_by_id.return_value = MagicMock()
        controller.visit_dao.get_visits_by_refuge.return_value = []
        
        with patch('api.controllers.refuge_visit_controller.get_madrid_today', return_value=date(2024, 1, 1)):
            success, visits, error = controller.get_refuge_visits("ref_1")
            
            assert success is True
            assert visits == []
            assert error is None
            controller.refuge_dao.get_by_id.assert_called_with("ref_1")

    def test_create_visit_new_success(self, controller):
        """Test crear nova visita amb èxit"""
        controller.refuge_dao.get_by_id.return_value = MagicMock()
        controller.visit_dao.get_visit_by_refuge_and_date.return_value = None
        controller.visit_dao.create_visit.return_value = (True, "visit_123", None)
        
        with patch('api.controllers.refuge_visit_controller.get_madrid_today', return_value=date(2024, 1, 1)):
            success, visit, error = controller.create_visit("ref_1", "2024-01-02", "user_1", 2)
            
            assert success is True
            assert visit.total_visitors == 2
            assert error is None
            controller.visit_dao.create_visit.assert_called()

    def test_create_visit_existing_success(self, controller):
        """Test afegir visitant a visita existent"""
        controller.refuge_dao.get_by_id.return_value = MagicMock()
        existing_visit = RefugeVisit(date="2024-01-02", refuge_id="ref_1", visitors=[], total_visitors=0)
        controller.visit_dao.get_visit_by_refuge_and_date.return_value = ("visit_123", existing_visit)
        controller.visit_dao.add_visitor_to_visit.return_value = True
        
        with patch('api.controllers.refuge_visit_controller.get_madrid_today', return_value=date(2024, 1, 1)):
            success, visit, error = controller.create_visit("ref_1", "2024-01-02", "user_1", 2)
            
            assert success is True
            assert visit.total_visitors == 2
            assert len(visit.visitors) == 1
            controller.visit_dao.add_visitor_to_visit.assert_called()

    def test_delete_visit_success(self, controller):
        """Test eliminar visitant de visita"""
        controller.visit_dao.get_visit_by_refuge_and_date.return_value = ("visit_123", MagicMock())
        controller.visit_dao.remove_visitor_from_visit.return_value = True
        
        success, error = controller.delete_visit("ref_1", "2024-01-02", "user_1")
        
        assert success is True
        assert error is None
        controller.visit_dao.remove_visitor_from_visit.assert_called_with("visit_123", "user_1")

class TestRefugeVisitControllerExtended:
    """Tests per a RefugeVisitController cobrint casos d'error i excepcions"""

    @patch('api.controllers.refuge_visit_controller.RefugiLliureDAO')
    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    def test_get_refuge_visits_errors(self, mock_visit_dao_class, mock_refuge_dao_class):
        """Test get_refuge_visits errors"""
        ctrl = RefugeVisitController()
        mock_refuge_dao = mock_refuge_dao_class.return_value
        
        # Refuge not found
        mock_refuge_dao.get_by_id.return_value = None
        success, visits, error = ctrl.get_refuge_visits("r1")
        assert success is False
        assert "no trobat" in error
        
        # Exception
        mock_refuge_dao.get_by_id.side_effect = Exception("Error")
        success, visits, error = ctrl.get_refuge_visits("r1")
        assert success is False
        assert "Error intern" in error

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    def test_get_user_visits_exception(self, mock_visit_dao_class):
        """Test get_user_visits excepció"""
        ctrl = RefugeVisitController()
        mock_visit_dao = mock_visit_dao_class.return_value
        mock_visit_dao.get_visits_by_user.side_effect = Exception("Error")
        
        success, visits, error = ctrl.get_user_visits("u1")
        assert success is False
        assert "Error intern" in error

    @patch('api.controllers.refuge_visit_controller.RefugiLliureDAO')
    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    @patch('api.controllers.refuge_visit_controller.get_madrid_today')
    def test_create_visit_errors(self, mock_today, mock_visit_dao_class, mock_refuge_dao_class):
        """Test create_visit errors"""
        ctrl = RefugeVisitController()
        mock_refuge_dao = mock_refuge_dao_class.return_value
        mock_visit_dao = mock_visit_dao_class.return_value
        mock_today.return_value = date(2024, 1, 1)
        
        # Refuge not found
        mock_refuge_dao.get_by_id.return_value = None
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "no trobat" in error
        
        # Past date
        mock_refuge_dao.get_by_id.return_value = MagicMock()
        success, visit, error = ctrl.create_visit("r1", "2023-12-31", "u1", 2)
        assert success is False
        assert "posterior a avui" in error
        
        # Invalid date format
        success, visit, error = ctrl.create_visit("r1", "invalid-date", "u1", 2)
        assert success is False
        assert "Format de data invàlid" in error
        
        # User already registered
        existing_visit = RefugeVisit(date="2024-01-02", refuge_id="r1", visitors=[UserVisit(uid="u1", num_visitors=1)], total_visitors=1)
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = ("v1", existing_visit)
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "Ja estàs registrat" in error
        
        # DAO failure - add_visitor
        existing_visit.visitors = []
        existing_visit.total_visitors = 0
        mock_visit_dao.add_visitor_to_visit.return_value = False
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "Error afegint visitant" in error
        
        # DAO failure - create_visit
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = None
        mock_visit_dao.create_visit.return_value = (False, None, "DAO Error")
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "DAO Error" in error

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    def test_update_visit_errors(self, mock_visit_dao_class):
        """Test update_visit errors"""
        ctrl = RefugeVisitController()
        mock_visit_dao = mock_visit_dao_class.return_value
        
        # Visit not found
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = None
        success, visit, error = ctrl.update_visit("r1", "2024-01-02", "u1", 3)
        assert success is False
        assert "no trobat" in error
        
        # User not found in visit
        existing_visit = RefugeVisit(date="2024-01-02", refuge_id="r1", visitors=[UserVisit(uid="u2", num_visitors=1)], total_visitors=1)
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = ("v1", existing_visit)
        success, visit, error = ctrl.update_visit("r1", "2024-01-02", "u1", 3)
        assert success is False
        assert "No estàs registrat" in error
        
        # DAO failure
        existing_visit.visitors = [UserVisit(uid="u1", num_visitors=1)]
        mock_visit_dao.update_visitor_in_visit.return_value = False
        success, visit, error = ctrl.update_visit("r1", "2024-01-02", "u1", 3)
        assert success is False
        assert "Error actualitzant" in error

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    def test_delete_visit_errors(self, mock_visit_dao_class):
        """Test delete_visit errors"""
        ctrl = RefugeVisitController()
        mock_visit_dao = mock_visit_dao_class.return_value
        
        # Visit not found
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = None
        success, error = ctrl.delete_visit("r1", "2024-01-02", "u1")
        assert success is False
        assert "no trobada" in error
        
        # DAO failure
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = ("v1", MagicMock())
        mock_visit_dao.remove_visitor_from_visit.return_value = False
        success, error = ctrl.delete_visit("r1", "2024-01-02", "u1")
        assert success is False
        assert "No estàs registrat" in error

    @patch('api.controllers.refuge_visit_controller.RefugiLliureDAO')
    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    @patch('api.controllers.refuge_visit_controller.UserController')
    @patch('api.controllers.refuge_visit_controller.get_madrid_today')
    def test_process_yesterday_visits_scenarios(self, mock_today, mock_user_ctrl_class, 
                                              mock_visit_dao_class, mock_refuge_dao_class):
        """Test process_yesterday_visits diferents escenaris"""
        ctrl = RefugeVisitController()
        mock_visit_dao = mock_visit_dao_class.return_value
        mock_refuge_dao = mock_refuge_dao_class.return_value
        mock_user_ctrl = mock_user_ctrl_class.return_value
        mock_today.return_value = date(2024, 1, 2)
        
        # Case 1: Empty visit (deleted)
        empty_visit = MagicMock(spec=RefugeVisit)
        empty_visit.total_visitors = 0
        empty_visit.visitors = []
        mock_visit_dao.get_visits_by_date.return_value = [("v1", empty_visit)]
        
        success, stats, error = ctrl.process_yesterday_visits()
        assert success is True
        assert stats['deleted_visits'] == 1
        mock_visit_dao.delete_visit.assert_called_with("v1")
        
        # Case 2: Visit with visitors, refuge not found
        visit = MagicMock(spec=RefugeVisit)
        visit.total_visitors = 2
        visit.visitors = [UserVisit(uid="u1", num_visitors=2)]
        visit.refuge_id = "r1"
        mock_visit_dao.get_visits_by_date.return_value = [("v2", visit)]
        mock_refuge_dao.get_by_id.return_value = None
        
        success, stats, error = ctrl.process_yesterday_visits()
        assert success is True
        assert stats['updated_refuges'] == 0
        
        # Case 3: Success update
        mock_refuge = MagicMock()
        mock_refuge.visitors = ["u2"]
        mock_refuge_dao.get_by_id.return_value = mock_refuge
        mock_refuge_dao.update_refugi_visitors.return_value = True
        
        success, stats, error = ctrl.process_yesterday_visits()
        assert success is True
        assert stats['updated_refuges'] == 1
        mock_user_ctrl.add_refugi_visitat.assert_called()
        
        # Case 4: update_refugi_visitors failure
        mock_refuge_dao.update_refugi_visitors.return_value = False
        success, stats, error = ctrl.process_yesterday_visits()
        assert success is True # Still returns True but logs warning
        
        # Case 5: Exception
        mock_visit_dao.get_visits_by_date.side_effect = Exception("Process Error")
        success, stats, error = ctrl.process_yesterday_visits()
        assert success is False
        assert "Process Error" in error

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    @patch('api.controllers.refuge_visit_controller.RefugiLliureDAO')
    @patch('api.controllers.refuge_visit_controller.get_madrid_today')
    def test_create_visit_append_visitors(self, mock_today, mock_refuge_dao_class, mock_visit_dao_class):
        """Test create_visit quan ja hi ha visitants (línia 120)"""
        ctrl = RefugeVisitController()
        mock_refuge_dao = mock_refuge_dao_class.return_value
        mock_visit_dao = mock_visit_dao_class.return_value
        mock_today.return_value = date(2024, 1, 1)
        mock_refuge_dao.get_by_id.return_value = MagicMock()
        
        existing_visit = RefugeVisit(date="2024-01-02", refuge_id="r1", visitors=[UserVisit(uid="u2", num_visitors=1)], total_visitors=1)
        mock_visit_dao.get_visit_by_refuge_and_date.return_value = ("v1", existing_visit)
        mock_visit_dao.add_visitor_to_visit.return_value = True
        
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is True
        assert len(visit.visitors) == 2

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    @patch('api.controllers.refuge_visit_controller.RefugiLliureDAO')
    def test_controller_methods_exceptions(self, mock_refuge_dao_class, mock_visit_dao_class):
        """Test excepcions en mètodes del controlador"""
        ctrl = RefugeVisitController()
        mock_refuge_dao = mock_refuge_dao_class.return_value
        mock_visit_dao = mock_visit_dao_class.return_value
        
        # create_visit exception
        mock_refuge_dao.get_by_id.side_effect = Exception("Create Error")
        success, visit, error = ctrl.create_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "Create Error" in error
        
        # update_visit exception
        mock_visit_dao.get_visit_by_refuge_and_date.side_effect = Exception("Update Error")
        success, visit, error = ctrl.update_visit("r1", "2024-01-02", "u1", 2)
        assert success is False
        assert "Update Error" in error
        
        # delete_visit exception
        mock_visit_dao.get_visit_by_refuge_and_date.side_effect = Exception("Delete Error")
        success, error = ctrl.delete_visit("r1", "2024-01-02", "u1")
        assert success is False
        assert "Delete Error" in error

    @patch('api.controllers.refuge_visit_controller.RefugeVisitDAO')
    def test_remove_user_from_all_visits_errors(self, mock_visit_dao_class):
        """Test remove_user_from_all_visits errors"""
        ctrl = RefugeVisitController()
        mock_visit_dao = mock_visit_dao_class.return_value
        
        # get_user_visits failure
        with patch.object(ctrl, 'get_user_visits', return_value=(False, [], "Error")):
            success, error = ctrl.remove_user_from_all_visits("u1")
            assert success is False
            assert "Error" in error
            
        # DAO failure
        with patch.object(ctrl, 'get_user_visits', return_value=(True, [], None)):
            mock_visit_dao.remove_user_from_all_visits.return_value = (False, "DAO Error")
            success, error = ctrl.remove_user_from_all_visits("u1")
            assert success is False
            assert "DAO Error" in error
            
        # Exception
        mock_visit_dao.get_visits_by_user.side_effect = Exception("Error")
        success, error = ctrl.remove_user_from_all_visits("u1")
        assert success is False
        assert "Error intern" in error

