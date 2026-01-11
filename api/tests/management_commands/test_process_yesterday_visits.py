"""
Tests unitaris per al management command process_yesterday_visits
"""
import pytest
from unittest.mock import MagicMock, patch
from io import StringIO
from api.management.commands.process_yesterday_visits import Command as ProcessVisitsCommand


# ============= TESTS =============

class TestProcessYesterdayVisits:
    """Tests per al command process_yesterday_visits"""
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_success(self, mock_controller_class):
        """Test: Processament exitós de visites"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {
                'processed_visits': 10,
                'deleted_visits': 3,
                'updated_refuges': 7,
                'total_visitors_added': 25
            },
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Visites d\'ahir processades correctament' in output
        assert 'Visites processades: 10' in output
        assert 'Visites buides eliminades: 3' in output
        assert 'Refugis actualitzats: 7' in output
        assert 'Total visitants afegits: 25' in output
        
        # Verify controller was called
        mock_controller.process_yesterday_visits.assert_called_once()
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_no_visits(self, mock_controller_class):
        """Test: Processament sense visites"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {
                'processed_visits': 0,
                'deleted_visits': 0,
                'updated_refuges': 0,
                'total_visitors_added': 0
            },
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Visites d\'ahir processades correctament' in output
        assert 'Visites processades: 0' in output
        assert 'Visites buides eliminades: 0' in output
        assert 'Refugis actualitzats: 0' in output
        assert 'Total visitants afegits: 0' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_controller_error(self, mock_controller_class):
        """Test: Error retornat pel controller"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            False,
            None,
            "Error accessing Firestore"
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Error processant visites: Error accessing Firestore' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_exception(self, mock_controller_class):
        """Test: Excepció durant el processament"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.side_effect = Exception("Unexpected error")
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Error inesperat: Unexpected error' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_controller_instantiation_error(self, mock_controller_class):
        """Test: Error al instanciar el controller"""
        # Arrange
        mock_controller_class.side_effect = Exception("Cannot instantiate controller")
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Error inesperat: Cannot instantiate controller' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_partial_success(self, mock_controller_class):
        """Test: Èxit parcial amb algunes visites processades"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {
                'processed_visits': 15,
                'deleted_visits': 5,
                'updated_refuges': 10,
                'total_visitors_added': 30
            },
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Visites processades: 15' in output
        assert 'Visites buides eliminades: 5' in output
        assert 'Refugis actualitzats: 10' in output
        assert 'Total visitants afegits: 30' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    @patch('api.management.commands.process_yesterday_visits.logger')
    def test_process_visits_logs_error(self, mock_logger, mock_controller_class):
        """Test: Verificar que els errors es registren al logger"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        error_msg = "Database connection failed"
        mock_controller.process_yesterday_visits.side_effect = Exception(error_msg)
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        mock_logger.error.assert_called_once()
        assert error_msg in str(mock_logger.error.call_args)
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_empty_stats(self, mock_controller_class):
        """Test: Gestió d'estadístiques buides"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {},
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        # Should handle missing keys gracefully (though implementation may vary)
        assert 'Visites d\'ahir processades correctament' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_controller_returns_none_stats(self, mock_controller_class):
        """Test: Controller retorna None com a stats"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            False,
            None,
            "Processing error"
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Error processant visites: Processing error' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_large_numbers(self, mock_controller_class):
        """Test: Processament amb nombres grans de visites"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {
                'processed_visits': 1000,
                'deleted_visits': 150,
                'updated_refuges': 850,
                'total_visitors_added': 3500
            },
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert 'Visites processades: 1000' in output
        assert 'Visites buides eliminades: 150' in output
        assert 'Refugis actualitzats: 850' in output
        assert 'Total visitants afegits: 3500' in output
    
    @patch('api.management.commands.process_yesterday_visits.RefugeVisitController')
    def test_process_visits_success_message_format(self, mock_controller_class):
        """Test: Format del missatge d'èxit"""
        # Arrange
        mock_controller = MagicMock()
        mock_controller_class.return_value = mock_controller
        
        mock_controller.process_yesterday_visits.return_value = (
            True,
            {
                'processed_visits': 5,
                'deleted_visits': 2,
                'updated_refuges': 3,
                'total_visitors_added': 12
            },
            None
        )
        
        command = ProcessVisitsCommand()
        out = StringIO()
        command.stdout = out
        
        # Act
        command.handle()
        
        # Assert
        output = out.getvalue()
        assert '=' * 80 in output
        assert 'Visites d\'ahir processades correctament' in output
        assert output.count('=') >= 160  # Two lines of separators
