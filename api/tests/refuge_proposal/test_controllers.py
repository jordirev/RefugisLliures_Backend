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
    def test_list_proposals_invalid_filters(self, mock_proposal_dao_class):
        """Test llistar propostes amb filtres invàlids"""
        controller = RefugeProposalController()
        filters = {'refuge_id': 'ref_1', 'creator_uid': 'user_1'}
        result, error = controller.list_proposals(filters)
        
        assert result is None
        assert "Cannot filter by both" in error

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
