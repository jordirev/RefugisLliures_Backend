"""
Tests per al controlador de propostes de refugi
"""
import pytest
from unittest.mock import MagicMock, patch
from api.controllers.refuge_proposal_controller import RefugeProposalController
from api.models.refuge_proposal import RefugeProposal

@pytest.mark.controllers
class TestRefugeProposalController:
    """Tests per a RefugeProposalController"""
    
    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    @patch('api.controllers.refuge_proposal_controller.RefugiLliureDAO')
    def test_create_proposal_create_action(self, mock_refugi_dao_class, mock_proposal_dao_class):
        """Test creació de proposta d'acció 'create'"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal_dao.create.return_value = mock_proposal
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'create', 'payload': {'name': 'New'}}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert error is None
        assert result == mock_proposal
        mock_proposal_dao.create.assert_called_with(proposal_data, "user_1")

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    @patch('api.controllers.refuge_proposal_controller.RefugiLliureDAO')
    def test_create_proposal_update_action_success(self, mock_refugi_dao_class, mock_proposal_dao_class):
        """Test creació de proposta d'acció 'update' amb èxit"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_proposal_dao = mock_proposal_dao_class.return_value
        
        mock_refugi = MagicMock()
        mock_refugi.to_dict.return_value = {'id': 'ref_1', 'name': 'Old'}
        mock_refugi_dao.get_by_id.return_value = mock_refugi
        
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal_dao.create.return_value = mock_proposal
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'update', 'refuge_id': 'ref_1', 'payload': {'name': 'New'}}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert error is None
        assert result == mock_proposal
        assert 'refuge_snapshot' in proposal_data
        mock_refugi_dao.get_by_id.assert_called_with('ref_1')

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    @patch('api.controllers.refuge_proposal_controller.RefugiLliureDAO')
    def test_create_proposal_delete_action_success(self, mock_refugi_dao_class, mock_proposal_dao_class):
        """Test creació de proposta d'acció 'delete' amb èxit"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_proposal_dao = mock_proposal_dao_class.return_value
        
        mock_refugi = MagicMock()
        mock_refugi.to_dict.return_value = {'id': 'ref_1', 'name': 'Old', 'images_metadata': [], 'media_metadata': [], 'visitors': []}
        mock_refugi_dao.get_by_id.return_value = mock_refugi
        
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal_dao.create.return_value = mock_proposal
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'delete', 'refuge_id': 'ref_1'}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert error is None
        assert result == mock_proposal
        # Verifica que els camps sensibles han estat eliminats
        assert 'images_metadata' not in proposal_data.get('refuge_snapshot', {})

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    @patch('api.controllers.refuge_proposal_controller.RefugiLliureDAO')
    def test_create_proposal_update_action_refuge_not_found(self, mock_refugi_dao_class, mock_proposal_dao_class):
        """Test creació de proposta 'update' amb refugi inexistent"""
        mock_refugi_dao = mock_refugi_dao_class.return_value
        mock_refugi_dao.get_by_id.return_value = None
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'update', 'refuge_id': 'ref_nonexistent', 'payload': {'name': 'New'}}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert result is None
        assert "does not exists" in error.lower()

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_create_proposal_create_action_dao_fails(self, mock_proposal_dao_class):
        """Test creació de proposta on DAO retorna None"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.create.return_value = None
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'create', 'payload': {'name': 'New'}}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert result is None
        assert "Error creating proposal" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_create_proposal_exception(self, mock_proposal_dao_class):
        """Test creació de proposta amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.create.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        proposal_data = {'action': 'create', 'payload': {'name': 'New'}}
        result, error = controller.create_proposal(proposal_data, "user_1")
        
        assert result is None
        assert "Internal server error" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_get_proposal_by_id_success(self, mock_proposal_dao_class):
        """Test obtenir proposta per ID amb èxit"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal_dao.get_by_id.return_value = mock_proposal
        
        controller = RefugeProposalController()
        result, error = controller.get_proposal_by_id("prop_1")
        
        assert result == mock_proposal
        assert error is None

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_get_proposal_by_id_not_found(self, mock_proposal_dao_class):
        """Test obtenir proposta per ID no trobada"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.get_by_id.return_value = None
        
        controller = RefugeProposalController()
        result, error = controller.get_proposal_by_id("prop_nonexistent")
        
        assert result is None
        assert "not found" in error.lower()

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_get_proposal_by_id_exception(self, mock_proposal_dao_class):
        """Test obtenir proposta per ID amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.get_by_id.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        result, error = controller.get_proposal_by_id("prop_1")
        
        assert result is None
        assert "Internal server error" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_list_proposals_invalid_filters(self, mock_proposal_dao_class):
        """Test llistar propostes amb filtres invàlids"""
        controller = RefugeProposalController()
        filters = {'refuge_id': 'ref_1', 'creator_uid': 'user_1'}
        result, error = controller.list_proposals(filters)
        
        assert result is None
        assert "Cannot filter by both" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_list_proposals_invalid_status(self, mock_proposal_dao_class):
        """Test llistar propostes amb status invàlid"""
        controller = RefugeProposalController()
        filters = {'status': 'invalid_status'}
        result, error = controller.list_proposals(filters)
        
        assert result is None
        assert "Invalid status filter" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_list_proposals_success(self, mock_proposal_dao_class):
        """Test llistar propostes amb èxit"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal_dao.list_all.return_value = [mock_proposal]
        
        controller = RefugeProposalController()
        result, error = controller.list_proposals({'status': 'pending'})
        
        assert result is not None
        assert len(result) == 1
        assert error is None

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_list_proposals_exception(self, mock_proposal_dao_class):
        """Test llistar propostes amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.list_all.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        result, error = controller.list_proposals({})
        
        assert result is None
        assert "Internal server error" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_approve_proposal_success(self, mock_proposal_dao_class):
        """Test aprovació de proposta"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.approve.return_value = (True, None)
        
        controller = RefugeProposalController()
        success, error = controller.approve_proposal("prop_1", "admin_1")
        
        assert success is True
        assert error is None
        mock_proposal_dao.approve.assert_called_with("prop_1", "admin_1")

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_approve_proposal_error(self, mock_proposal_dao_class):
        """Test aprovació de proposta amb error"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.approve.return_value = (False, "Proposal not found")
        
        controller = RefugeProposalController()
        success, error = controller.approve_proposal("prop_nonexistent", "admin_1")
        
        assert success is False
        assert error == "Proposal not found"

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_approve_proposal_exception(self, mock_proposal_dao_class):
        """Test aprovació de proposta amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.approve.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        success, error = controller.approve_proposal("prop_1", "admin_1")
        
        assert success is False
        assert "Internal server error" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_reject_proposal_success(self, mock_proposal_dao_class):
        """Test rebuig de proposta amb èxit"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.reject.return_value = (True, None)
        
        controller = RefugeProposalController()
        success, error = controller.reject_proposal("prop_1", "admin_1", "Invalid data")
        
        assert success is True
        assert error is None
        mock_proposal_dao.reject.assert_called_with("prop_1", "admin_1", "Invalid data")

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_reject_proposal_error(self, mock_proposal_dao_class):
        """Test rebuig de proposta amb error"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.reject.return_value = (False, "Proposal not found")
        
        controller = RefugeProposalController()
        success, error = controller.reject_proposal("prop_nonexistent", "admin_1", "Reason")
        
        assert success is False
        assert error == "Proposal not found"

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_reject_proposal_exception(self, mock_proposal_dao_class):
        """Test rebuig de proposta amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.reject.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        success, error = controller.reject_proposal("prop_1", "admin_1", "Reason")
        
        assert success is False
        assert "Internal server error" in error

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_anonymize_proposals_by_creator_success(self, mock_proposal_dao_class):
        """Test anonimització de propostes amb èxit"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.anonymize_proposals_by_creator.return_value = (True, None)
        
        controller = RefugeProposalController()
        success, error = controller.anonymize_proposals_by_creator("user_1")
        
        assert success is True
        assert error is None

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_anonymize_proposals_by_creator_error(self, mock_proposal_dao_class):
        """Test anonimització de propostes amb error"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.anonymize_proposals_by_creator.return_value = (False, "Error anonimitzant")
        
        controller = RefugeProposalController()
        success, error = controller.anonymize_proposals_by_creator("user_1")
        
        assert success is False
        assert error == "Error anonimitzant"

    @patch('api.controllers.refuge_proposal_controller.RefugeProposalDAO')
    def test_anonymize_proposals_by_creator_exception(self, mock_proposal_dao_class):
        """Test anonimització de propostes amb excepció"""
        mock_proposal_dao = mock_proposal_dao_class.return_value
        mock_proposal_dao.anonymize_proposals_by_creator.side_effect = Exception("Error inesperat")
        
        controller = RefugeProposalController()
        success, error = controller.anonymize_proposals_by_creator("user_1")
        
        assert success is False
        assert "Internal server error" in error
