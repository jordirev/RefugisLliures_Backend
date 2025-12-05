"""
Tests per renovations
"""
import pytest
from unittest.mock import patch
from datetime import datetime, date, timedelta
from rest_framework.test import APIRequestFactory
from rest_framework import status as http_status
from api.models.renovation import Renovation
from api.views.renovation_views import (
    RenovationListAPIView,
    RenovationAPIView,
    RenovationParticipantsAPIView,
    RenovationParticipantDetailAPIView
)
# ===== FIXTURES =====
@pytest.fixture
def sample_renovation_data():
    """Dades de prova per a una renovation"""
    today = date.today()
    return {
        'id': 'test_renovation_id',
        'creator_uid': 'test_creator_uid',
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).isoformat(),
        'fin_date': (today + timedelta(days=5)).isoformat(),
        'description': 'Test renovation description',
        'materials_needed': 'Wood, nails, paint',
        'group_link': 'https://wa.me/group/test',
        'participants_uids': ['participant1', 'participant2']
    }
@pytest.fixture
def sample_renovation(sample_renovation_data):
    """Instància de model Renovation de prova"""
    return Renovation(
        id=sample_renovation_data['id'],
        creator_uid=sample_renovation_data['creator_uid'],
        refuge_id=sample_renovation_data['refuge_id'],
        ini_date=datetime.fromisoformat(sample_renovation_data['ini_date']),
        fin_date=datetime.fromisoformat(sample_renovation_data['fin_date']),
        description=sample_renovation_data['description'],
        materials_needed=sample_renovation_data['materials_needed'],
        group_link=sample_renovation_data['group_link'],
        participants_uids=sample_renovation_data['participants_uids']
    )
@pytest.fixture
def minimal_renovation_data():
    """Dades mínimes per crear una renovation"""
    today = date.today()
    return {
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
        'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
        'description': 'Test renovation',
        'group_link': 'https://t.me/test'
    }
# ===== TEST MODEL =====


# ===== TEST VIEWS =====

@pytest.mark.django_db
class TestRenovationViews:
    """Tests per a les views de renovation"""
    
    def _get_authenticated_request(self, method, path, data=None, query_params=None, user_uid='test_user'):
        """Helper per crear requests autenticades"""
        factory = APIRequestFactory()
        if method == 'GET':
            request = factory.get(path, query_params or {})
        elif method == 'POST':
            request = factory.post(path, data or {}, format='json')
        elif method == 'PATCH':
            request = factory.patch(path, data or {}, format='json')
        elif method == 'DELETE':
            request = factory.delete(path)
        else:
            raise ValueError(f"Method {method} not supported")
        
        request.user_uid = user_uid
        
        # Per PATCH i DELETE, també podem passar query_params manualment
        if query_params and method in ['PATCH', 'DELETE']:
            from django.http import QueryDict
            q = QueryDict('', mutable=True)
            q.update(query_params)
            request.GET = q
        
        return request
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_success(self, mock_controller_class, sample_renovation):
        """Test GET /renovations/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.return_value = (True, [sample_renovation], None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        # Forçar autenticació
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
        assert len(response.data) == 1
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_success(self, mock_controller_class, sample_renovation, minimal_renovation_data):
        """Test POST /renovations/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_201_CREATED
        assert 'id' in response.data
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_invalid_data(self, mock_controller_class):
        """Test POST /renovations/ amb dades invàlides"""
        request = self._get_authenticated_request('POST', '/api/renovations/', {'invalid': 'data'})
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_no_user_uid(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ sense user_uid"""
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data, user_uid=None)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_overlap(self, mock_controller_class, sample_renovation, minimal_renovation_data):
        """Test POST /renovations/ amb solapament"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (
            False,
            sample_renovation,
            'Hi ha una altra renovation que es solapa temporalment'
        )
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_409_CONFLICT
        assert 'overlapping_renovation' in response.data
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_success(self, mock_controller_class, sample_renovation):
        """Test GET /renovations/{id}/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/test_id/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_200_OK
        assert response.data['id'] == sample_renovation.id
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_not_found(self, mock_controller_class):
        """Test GET /renovations/{id}/ (no trobada)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('GET', '/api/renovations/nonexistent/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='nonexistent')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_success(self, mock_controller_class, sample_renovation):
        """Test PATCH /renovations/{id}/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/test_id/',
            {'description': 'Updated'},
            user_uid=sample_renovation.creator_uid
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_forbidden(self, mock_controller_class):
        """Test PATCH /renovations/{id}/ (no creador)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (
            False,
            None,
            'Només el creador pot editar la renovation'
        )
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/test_id/',
            {'description': 'Updated'},
            user_uid='other_user'
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_no_user_uid(self, mock_controller_class):
        """Test PATCH /renovations/ sense user_uid"""
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/test_id/',
            {'description': 'Updated'},
            user_uid=None
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_controller_error(self, mock_controller_class):
        """Test PATCH amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/test_id/',
            {'description': 'Updated'}
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_success(self, mock_controller_class, sample_renovation):
        """Test DELETE /renovations/{id}/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (True, None)
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/test_id/',
            user_uid=sample_renovation.creator_uid
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_204_NO_CONTENT
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_forbidden(self, mock_controller_class):
        """Test DELETE /renovations/{id}/ (no creador)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (
            False,
            'Només el creador pot eliminar la renovation'
        )
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/test_id/',
            user_uid='other_user'
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_no_user_uid(self, mock_controller_class):
        """Test DELETE /renovations/ sense user_uid"""
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/test_id/',
            user_uid=None
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_controller_error(self, mock_controller_class):
        """Test DELETE amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (False, 'Controller error')
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/test_id/'
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.views.renovation_views.RenovationController')
    @patch('api.permissions.IsCreator.has_permission')
    def test_get_renovation_real_permissions(self, mock_has_perm, mock_controller_class, sample_renovation):
        """Test GET /renovations/ amb permisos reals per cobrir get_permissions"""
        mock_has_perm.return_value = True
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/test_id/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        # No forcem get_permissions, deixem que s'executi
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_controller_error(self, mock_controller_class):
        """Test GET /renovations/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.return_value = (False, [], 'Database error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_exception(self, mock_controller_class):
        """Test GET /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_controller_error(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (False, None, 'Error creating renovation')
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_exception(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_exception(self, mock_controller_class):
        """Test GET /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/test_id/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_invalid_data(self, mock_controller_class):
        """Test PATCH /renovations/ amb dades invàlides"""
        request = self._get_authenticated_request('PATCH', '/api/renovations/test_id/', {'ini_date': 'invalid'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_not_found(self, mock_controller_class):
        """Test PATCH /renovations/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/test_id/', {'description': 'Updated'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_overlap(self, mock_controller_class, sample_renovation):
        """Test PATCH /renovations/ amb solapament"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, sample_renovation, 'Solapament temporal')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/test_id/', {'description': 'Updated'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_409_CONFLICT
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_exception(self, mock_controller_class):
        """Test PATCH /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/test_id/', {'description': 'Updated'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_not_found(self, mock_controller_class):
        """Test DELETE /renovations/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (False, 'Renovation no trobada')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_exception(self, mock_controller_class):
        """Test DELETE /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/')
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_success(self, mock_controller_class, sample_renovation):
        """Test POST /renovations/{id}/participants/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_not_found(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_is_creator(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ quan l'usuari és el creador"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'El creador no pot unir-se')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_expelled(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ quan l'usuari està expulsat"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'Aquest usuari ha estat expulsat d\'aquesta renovation i no pot tornar a unir-se')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_already_participant(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ quan l'usuari ja és participant"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'L\'usuari ja és participant d\'aquesta renovation')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_409_CONFLICT
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_no_user_uid(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ sense user_uid"""
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/', user_uid=None)
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_controller_error(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_exception(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_success(self, mock_controller_class, sample_renovation):
        """Test DELETE /renovations/{id}/participants/{uid}/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_not_found(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_forbidden(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ sense permís"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'No tens permís')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_no_user_uid(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ sense user_uid"""
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/', user_uid=None)
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_controller_error(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_exception(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
