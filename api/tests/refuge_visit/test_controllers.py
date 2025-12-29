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
