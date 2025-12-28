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
