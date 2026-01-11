"""
Tests per a les vistes de visites a refugi
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status
from api.views.refuge_visit_views import (
    RefugeVisitsAPIView, UserVisitsAPIView, RefugeVisitDetailAPIView
)
from api.models.refuge_visit import RefugeVisit, UserVisit

@pytest.mark.views
class TestRefugeVisitViews:
    """Tests per a les vistes de visites a refugi"""
    
    @pytest.fixture
    def factory(self):
        return APIRequestFactory()

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_refuge_visits_success(self, mock_controller_class, factory):
        """Test obtenir visites de refugi"""
        mock_controller = mock_controller_class.return_value
        visit = RefugeVisit(
            date="2024-01-01",
            refuge_id="ref_1",
            visitors=[],
            total_visitors=0
        )
        mock_controller.get_refuge_visits.return_value = (True, [visit], None)
        
        view = RefugeVisitsAPIView.as_view()
        request = factory.get('/api/refuges/ref_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'result' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_success(self, mock_controller_class, factory):
        """Test crear visita"""
        mock_controller = mock_controller_class.return_value
        mock_visit = RefugeVisit(date="2024-01-01", refuge_id="ref_1", visitors=[], total_visitors=0)
        mock_controller.create_visit.return_value = (True, mock_visit, None)
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 2}
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['message'] == 'Visita creada correctament'

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_delete_visit_success(self, mock_controller_class, factory):
        """Test eliminar visitant"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_visit.return_value = (True, None)
        
        view = RefugeVisitDetailAPIView.as_view()
        request = factory.delete('/api/refuges/ref_1/visits/2024-01-01/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Visitant eliminat correctament'

    # ===== ERROR PATHS FOR RefugeVisitsAPIView =====
    
    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_refuge_visits_not_found(self, mock_controller_class, factory):
        """Test obtenir visites de refugi no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refuge_visits.return_value = (False, None, "Refugi no trobat")
        
        view = RefugeVisitsAPIView.as_view()
        request = factory.get('/api/refuges/nonexistent/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='nonexistent')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_refuge_visits_error(self, mock_controller_class, factory):
        """Test obtenir visites de refugi amb error genèric (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refuge_visits.return_value = (False, None, "Error de validació")
        
        view = RefugeVisitsAPIView.as_view()
        request = factory.get('/api/refuges/ref_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_refuge_visits_exception(self, mock_controller_class, factory):
        """Test obtenir visites amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refuge_visits.side_effect = Exception("Error inesperat")
        
        view = RefugeVisitsAPIView.as_view()
        request = factory.get('/api/refuges/ref_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    # ===== UserVisitsAPIView TESTS =====
    
    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_user_visits_success(self, mock_controller_class, factory):
        """Test obtenir visites d'usuari amb èxit"""
        mock_controller = mock_controller_class.return_value
        visit = RefugeVisit(
            date="2024-01-01",
            refuge_id="ref_1",
            visitors=[],
            total_visitors=0
        )
        mock_controller.get_user_visits.return_value = (True, [('visit_1', visit)], None)
        
        view = UserVisitsAPIView.as_view()
        request = factory.get('/api/users/user_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(UserVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, uid='user_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'result' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_user_visits_error(self, mock_controller_class, factory):
        """Test obtenir visites d'usuari amb error (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_visits.return_value = (False, None, "Error obtenint visites")
        
        view = UserVisitsAPIView.as_view()
        request = factory.get('/api/users/user_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(UserVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, uid='user_1')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_get_user_visits_exception(self, mock_controller_class, factory):
        """Test obtenir visites d'usuari amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_visits.side_effect = Exception("Error inesperat")
        
        view = UserVisitsAPIView.as_view()
        request = factory.get('/api/users/user_1/visits/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(UserVisitsAPIView, 'get_permissions', return_value=[]):
            response = view(request, uid='user_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    # ===== POST ERROR PATHS =====
    
    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_invalid_data(self, mock_controller_class, factory):
        """Test crear visita amb dades invàlides (400)"""
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': -1}  # Valor invàlid
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_no_uid(self, mock_controller_class, factory):
        """Test crear visita sense UID (401)"""
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 2}
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        # No establim request.user_uid
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_not_found(self, mock_controller_class, factory):
        """Test crear visita en refugi no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_visit.return_value = (False, None, "Refugi no trobat")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 2}
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_error(self, mock_controller_class, factory):
        """Test crear visita amb error genèric (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_visit.return_value = (False, None, "Usuari ja registrat")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 2}
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_post_visit_exception(self, mock_controller_class, factory):
        """Test crear visita amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_visit.side_effect = Exception("Error inesperat")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 2}
        request = factory.post('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    # ===== PATCH TESTS =====
    
    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_success(self, mock_controller_class, factory):
        """Test actualitzar visita amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_visit = RefugeVisit(date="2024-01-01", refuge_id="ref_1", visitors=[], total_visitors=0)
        mock_controller.update_visit.return_value = (True, mock_visit, None)
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 3}
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Visita actualitzada correctament'

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_invalid_data(self, mock_controller_class, factory):
        """Test actualitzar visita amb dades invàlides (400)"""
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 0}  # Valor invàlid
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_no_uid(self, mock_controller_class, factory):
        """Test actualitzar visita sense UID (401)"""
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 3}
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        # No establim request.user_uid
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_not_found(self, mock_controller_class, factory):
        """Test actualitzar visita no trobada (400, no 404 porque 'no trobat' no está en el error)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_visit.return_value = (False, None, "Visita no registrada")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 3}
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_error(self, mock_controller_class, factory):
        """Test actualitzar visita amb error genèric (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_visit.return_value = (False, None, "Usuari no registrat")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 3}
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_patch_visit_exception(self, mock_controller_class, factory):
        """Test actualitzar visita amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_visit.side_effect = Exception("Error inesperat")
        
        view = RefugeVisitDetailAPIView.as_view()
        data = {'num_visitors': 3}
        request = factory.patch('/api/refuges/ref_1/visits/2024-01-01/', data, format='json')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    # ===== DELETE ERROR PATHS =====
    
    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_delete_visit_no_uid(self, mock_controller_class, factory):
        """Test eliminar visita sense UID (401)"""
        view = RefugeVisitDetailAPIView.as_view()
        request = factory.delete('/api/refuges/ref_1/visits/2024-01-01/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        # No establim request.user_uid
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_delete_visit_not_found(self, mock_controller_class, factory):
        """Test eliminar visita sense registre (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_visit.return_value = (False, "Usuari no registrat")
        
        view = RefugeVisitDetailAPIView.as_view()
        request = factory.delete('/api/refuges/ref_1/visits/2024-01-01/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_delete_visit_error(self, mock_controller_class, factory):
        """Test eliminar visita amb error genèric (400)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_visit.return_value = (False, "Usuari no registrat a la visita")
        
        view = RefugeVisitDetailAPIView.as_view()
        request = factory.delete('/api/refuges/ref_1/visits/2024-01-01/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    @patch('api.views.refuge_visit_views.RefugeVisitController')
    def test_delete_visit_exception(self, mock_controller_class, factory):
        """Test eliminar visita amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_visit.side_effect = Exception("Error inesperat")
        
        view = RefugeVisitDetailAPIView.as_view()
        request = factory.delete('/api/refuges/ref_1/visits/2024-01-01/')
        user = MagicMock(uid='user_1')
        user.is_authenticated = True
        force_authenticate(request, user=user)
        request.user_uid = 'user_1'
        
        with patch.object(RefugeVisitDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, refuge_id='ref_1', visit_date='2024-01-01')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
