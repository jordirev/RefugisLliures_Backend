"""
Tests per al mapper de propostes de refugi
"""
import pytest
from api.mappers.refuge_proposal_mapper import RefugeProposalMapper
from api.models.refuge_proposal import RefugeProposal

@pytest.mark.mappers
class TestRefugeProposalMapper:
    """Tests per al mapper RefugeProposalMapper"""
    
    def test_firestore_to_model(self):
        """Test conversió de Firestore a model RefugeProposal"""
        data = {
            'id': 'prop_1',
            'action': 'create',
            'status': 'pending',
            'creator_uid': 'u1',
            'created_at': 'd1',
            'reviewer_uid': None,
            'reviewed_at': None
        }
        proposal = RefugeProposalMapper.firestore_to_model(data)
        assert isinstance(proposal, RefugeProposal)
        assert proposal.id == 'prop_1'

    def test_model_to_firestore(self):
        """Test conversió de model RefugeProposal a Firestore"""
        proposal = RefugeProposal(
            id='prop_1',
            refuge_id=None,
            action='create',
            payload={},
            comment='Test',
            status='pending',
            creator_uid='user_1',
            created_at='2024-01-01',
            reviewer_uid=None,
            reviewed_at=None
        )
        data = RefugeProposalMapper.model_to_firestore(proposal)
        assert data['id'] == 'prop_1'
        assert data['status'] == 'pending'

    def test_lists_conversion(self):
        """Test conversió de llistes"""
        data = {
            'id': 'prop_1',
            'action': 'create',
            'creator_uid': 'u1',
            'created_at': 'd1',
            'reviewer_uid': None,
            'reviewed_at': None
        }
        data_list = [data]
        models = RefugeProposalMapper.firestore_list_to_models(data_list)
        assert len(models) == 1
        assert models[0].id == 'prop_1'
        
        back_to_data = RefugeProposalMapper.models_to_firestore_list(models)
        assert len(back_to_data) == 1
        assert back_to_data[0]['id'] == 'prop_1'
