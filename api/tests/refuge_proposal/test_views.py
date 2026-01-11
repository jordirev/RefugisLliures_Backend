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

    # ===== TESTS D'ERROR PER MILLORAR COVERAGE =====

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_post_proposal_invalid_data(self, mock_controller_class, factory):
        """Test crear proposta amb dades invàlides (400)"""
        view = RefugeProposalCollectionAPIView.as_view()
        data = {'action': 'invalid'}  # Acció invàlida
        request = factory.post('/api/refuges-proposals/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_post_proposal_no_uid(self, mock_controller_class, factory):
        """Test crear proposta sense UID (401)"""
        # Mockejar el controller per evitar l'error de desempaquetament
        mock_controller = mock_controller_class.return_value
        mock_controller.create_proposal.return_value = (None, "No UID")
        
        view = RefugeProposalCollectionAPIView.as_view()
        data = {'action': 'create', 'payload': {'name': 'New', 'coord': {'lat': 0, 'long': 0}}}
        request = factory.post('/api/refuges-proposals/', data, format='json')
        user = MagicMock()
        user.is_authenticated = True
        # Sense uid - l'usuari no té atribut uid
        delattr(user, 'uid') if hasattr(user, 'uid') else None
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_post_proposal_refuge_not_exists(self, mock_controller_class, factory):
        """Test crear proposta amb refugi inexistent (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_proposal.return_value = (None, "Refuge does not exists")
        
        view = RefugeProposalCollectionAPIView.as_view()
        data = {'action': 'update', 'refuge_id': 'nonexistent', 'payload': {'name': 'New'}}
        request = factory.post('/api/refuges-proposals/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_post_proposal_server_error(self, mock_controller_class, factory):
        """Test crear proposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_proposal.return_value = (None, "Database error")
        
        view = RefugeProposalCollectionAPIView.as_view()
        data = {'action': 'create', 'payload': {'name': 'New', 'coord': {'lat': 0, 'long': 0}}}
        request = factory.post('/api/refuges-proposals/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_proposals_with_status_filter(self, mock_controller_class, factory):
        """Test llistar propostes amb filtre d'status"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {'id': 'prop_1', 'status': 'pending', 'action': 'create', 'creator_uid': 'u1', 'created_at': 'd1', 'refuge_id': None, 'payload': {}, 'comment': None, 'reviewer_uid': None, 'reviewed_at': None}
        mock_controller.list_proposals.return_value = ([mock_proposal], None)
        
        view = RefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/refuges-proposals/?status=pending')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        mock_controller.list_proposals.assert_called()

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_proposals_with_refuge_id_filter(self, mock_controller_class, factory):
        """Test llistar propostes amb filtre de refuge_id"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {'id': 'prop_1', 'status': 'pending', 'action': 'update', 'creator_uid': 'u1', 'created_at': 'd1', 'refuge_id': 'ref_1', 'payload': {}, 'comment': None, 'reviewer_uid': None, 'reviewed_at': None}
        mock_controller.list_proposals.return_value = ([mock_proposal], None)
        
        view = RefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/refuges-proposals/?refuge-id=ref_1')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_proposals_invalid_filter(self, mock_controller_class, factory):
        """Test llistar propostes amb filtre invàlid (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.list_proposals.return_value = (None, "Invalid status filter")
        
        view = RefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/refuges-proposals/?status=invalid')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_proposals_server_error(self, mock_controller_class, factory):
        """Test llistar propostes amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.list_proposals.return_value = (None, "Database error")
        
        view = RefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/refuges-proposals/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ===== MyRefugeProposalCollectionAPIView TESTS =====

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_my_proposals_success(self, mock_controller_class, factory):
        """Test llistar les meves propostes amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {'id': 'prop_1', 'status': 'pending', 'action': 'create', 'creator_uid': 'user_1', 'created_at': 'd1', 'refuge_id': None, 'payload': {}, 'comment': None, 'reviewer_uid': None, 'reviewed_at': None}
        mock_controller.list_proposals.return_value = ([mock_proposal], None)
        
        view = MyRefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/my-refuges-proposals/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(MyRefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        mock_controller.list_proposals.assert_called_once()

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_my_proposals_no_uid(self, mock_controller_class, factory):
        """Test llistar les meves propostes sense UID (401)"""
        # Mockejar el controller per evitar l'error de desempaquetament
        mock_controller = mock_controller_class.return_value
        mock_controller.list_proposals.return_value = ([], None)
        
        view = MyRefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/my-refuges-proposals/')
        user = MagicMock()
        user.is_authenticated = True
        # Sense uid - eliminem l'atribut uid si existeix
        delattr(user, 'uid') if hasattr(user, 'uid') else None
        force_authenticate(request, user=user)
        
        with patch.object(MyRefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_my_proposals_with_status_filter(self, mock_controller_class, factory):
        """Test llistar les meves propostes amb filtre d'status"""
        mock_controller = mock_controller_class.return_value
        mock_proposal = MagicMock(spec=RefugeProposal)
        mock_proposal.to_dict.return_value = {'id': 'prop_1', 'status': 'pending', 'action': 'create', 'creator_uid': 'user_1', 'created_at': 'd1', 'refuge_id': None, 'payload': {}, 'comment': None, 'reviewer_uid': None, 'reviewed_at': None}
        mock_controller.list_proposals.return_value = ([mock_proposal], None)
        
        view = MyRefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/my-refuges-proposals/?status=pending')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(MyRefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_my_proposals_invalid_status(self, mock_controller_class, factory):
        """Test llistar les meves propostes amb status invàlid (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.list_proposals.return_value = (None, "Invalid status")
        
        view = MyRefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/my-refuges-proposals/?status=invalid')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(MyRefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_get_my_proposals_server_error(self, mock_controller_class, factory):
        """Test llistar les meves propostes amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.list_proposals.return_value = (None, "Database error")
        
        view = MyRefugeProposalCollectionAPIView.as_view()
        request = factory.get('/api/my-refuges-proposals/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(MyRefugeProposalCollectionAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ===== APPROVE/REJECT ERROR TESTS =====

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_approve_proposal_no_uid(self, mock_controller_class, factory):
        """Test aprovar proposta sense UID (401)"""
        # Mockejar el controller per evitar l'error de desempaquetament
        mock_controller = mock_controller_class.return_value
        mock_controller.approve_proposal.return_value = (False, "No UID")
        
        view = RefugeProposalApproveAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/approve/')
        user = MagicMock()
        user.is_authenticated = True
        # Sense uid - eliminem l'atribut uid si existeix
        delattr(user, 'uid') if hasattr(user, 'uid') else None
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalApproveAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_approve_proposal_not_found(self, mock_controller_class, factory):
        """Test aprovar proposta no trobada (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.approve_proposal.return_value = (False, "Proposal not found")
        
        view = RefugeProposalApproveAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/approve/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalApproveAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_approve_proposal_already_reviewed(self, mock_controller_class, factory):
        """Test aprovar proposta ja revisada (409)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.approve_proposal.return_value = (False, "Proposal already approved")
        
        view = RefugeProposalApproveAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/approve/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalApproveAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_409_CONFLICT

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_approve_proposal_server_error(self, mock_controller_class, factory):
        """Test aprovar proposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.approve_proposal.return_value = (False, "Database error")
        
        view = RefugeProposalApproveAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/approve/')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalApproveAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_reject_proposal_no_uid(self, mock_controller_class, factory):
        """Test rebutjar proposta sense UID (401)"""
        # Mockejar el controller per evitar l'error de desempaquetament
        mock_controller = mock_controller_class.return_value
        mock_controller.reject_proposal.return_value = (False, "No UID")
        
        view = RefugeProposalRejectAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/reject/', {}, format='json')
        user = MagicMock()
        user.is_authenticated = True
        # Sense uid - eliminem l'atribut uid si existeix
        delattr(user, 'uid') if hasattr(user, 'uid') else None
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalRejectAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_reject_proposal_not_found(self, mock_controller_class, factory):
        """Test rebutjar proposta no trobada (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.reject_proposal.return_value = (False, "Proposal not found")
        
        view = RefugeProposalRejectAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/reject/', {}, format='json')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalRejectAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_reject_proposal_already_reviewed(self, mock_controller_class, factory):
        """Test rebutjar proposta ja revisada (409)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.reject_proposal.return_value = (False, "Proposal already rejected")
        
        view = RefugeProposalRejectAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/reject/', {}, format='json')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalRejectAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_409_CONFLICT

    @patch('api.views.refuge_proposal_views.RefugeProposalController')
    def test_reject_proposal_server_error(self, mock_controller_class, factory):
        """Test rebutjar proposta amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.reject_proposal.return_value = (False, "Database error")
        
        view = RefugeProposalRejectAPIView.as_view()
        request = factory.post('/api/refuges-proposals/prop_1/reject/', {}, format='json')
        user = MagicMock(uid='admin_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        
        with patch.object(RefugeProposalRejectAPIView, 'get_permissions', return_value=[]):
            response = view(request, id='prop_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
