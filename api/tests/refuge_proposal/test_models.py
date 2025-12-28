"""
Tests per al model de proposta de refugi
"""
import pytest
from api.models.refuge_proposal import RefugeProposal

@pytest.mark.models
class TestRefugeProposalModels:
    """Tests per al model RefugeProposal"""
    
    def test_proposal_creation(self):
        """Test creació de RefugeProposal"""
        proposal = RefugeProposal(
            id="prop_123",
            refuge_id=None,
            action="create",
            payload={"name": "New Refuge"},
            comment="I found this one",
            status="pending",
            creator_uid="user_1",
            created_at="2024-01-01",
            reviewer_uid=None,
            reviewed_at=None
        )
        
        assert proposal.id == "prop_123"
        assert proposal.action == "create"
        assert proposal.status == "pending"

    def test_proposal_to_dict(self):
        """Test conversió de RefugeProposal a diccionari"""
        proposal = RefugeProposal(
            id="prop_123",
            refuge_id="ref_1",
            action="update",
            payload={"places": 10},
            comment="Updated places",
            status="approved",
            creator_uid="user_1",
            created_at="2024-01-01",
            reviewer_uid="admin_1",
            reviewed_at="2024-01-02"
        )
        
        data = proposal.to_dict()
        assert data['id'] == "prop_123"
        assert data['status'] == "approved"
        assert data['reviewer_uid'] == "admin_1"

    def test_proposal_from_dict(self):
        """Test creació de RefugeProposal des de diccionari"""
        data = {
            'id': 'prop_123',
            'action': 'delete',
            'status': 'rejected',
            'rejection_reason': 'Invalid',
            'creator_uid': 'u1',
            'created_at': 'd1',
            'reviewer_uid': 'a1',
            'reviewed_at': 'd2'
        }
        
        proposal = RefugeProposal.from_dict(data)
        assert proposal.id == 'prop_123'
        assert proposal.action == 'delete'
        assert proposal.status == 'rejected'
        assert proposal.rejection_reason == 'Invalid'
