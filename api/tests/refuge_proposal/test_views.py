"""
Tests per a les vistes de propostes de refugi
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from api.views.refuge_proposal_views import (
    RefugeProposalCollectionAPIView, RefugeProposalApproveAPIView,
    RefugeProposalRejectAPIView, MyRefugeProposalCollectionAPIView
)
from api.models.refuge_proposal import RefugeProposal

@pytest.mark.views
class TestRefugeProposalViews:
    """Tests per a les vistes de propostes de refugi"""
    
    @pytest.fixture
    def factory(self):
        return APIRequestFactory()

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_post_proposal_success(self, mock_controller_class, factory):
        """Test crear proposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {
            'id': 'prop_1',
            'action': 'create',
            'status': 'pending',
            'creator_uid': 'user_1',
            'created_at': '2024-01-01',
            'refuge_id': None,
            'payload': {'name': 'New'},
            'comment': 'Test',
            'reviewer_uid': None,
            'reviewed_at': None
        }
        mock_controller.create_proposal.return_value = (mock_proposal, None)
        
        view = RefugeProposalCollectionAPIView.as_view()
        data = {
            'action': 'create',
            'payload': {'name': 'New', 'coord': {'lat': 0, 'long': 0}}
        }
        request = factory.post('/api/refuges-proposals/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['id'] == 'prop_1'

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_proposals_admin_success(self, mock_controller_class, factory):
        """Test llistar propostes per admin"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {'id': 'prop_1', 'status': 'pending', 'action': 'create', 'creator_uid': 'u1', 'created_at': 'd1', 'refuge_id': None, 'payload': {}, 'comment': None, 'reviewer_uid': None, 'reviewed_at': None}
        mock_controller.list_proposals.return_value = ([mock_proposal], None)
        
        view = RefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/refuges-proposals/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'admin_1'
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_approve_proposal_success(self, mock_controller_class, factory):
        """Test aprovar proposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_controller.approve_proposal.return_value = (True, None)
        
        view = RefugeProposalApproveAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/approve/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'admin_1'
        
        with patch.object(RefugeProposalApproveAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Proposal approved successfully'

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_reject_proposal_success(self, mock_controller_class, factory):
        """Test rebutjar proposta amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_controller.reject_proposal.return_value = (True, None)
        
        view = RefugeProposalRejectAPIView.as_view()
        data = {'reason': 'Invalid'}
        request = factory.post('/api/refuges-proposals/prop_1/reject/', data, format='json')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'admin_1'
        
        with patch.object(RefugeProposalRejectAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Proposal rejected successfully'
