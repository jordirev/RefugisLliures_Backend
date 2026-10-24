"""
Tests de les vistes legacy que continuen a `api/`: health check i renovations d'un refugi.
(Les vistes de refugis i mitjans viuen a `apps/refuges` i es proven a `apps/refuges/tests`.)
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import math
from rest_framework import status
from rest_framework import status as http_status
from rest_framework.test import APIRequestFactory
from api.models.refugi_lliure import (
    Refugi,
    Coordinates,
    InfoComplementaria,
    RefugiSearchFilters
)
from api.views.renovation_views import RefugeRenovationsAPIView
from api.views.health_check_views import HealthCheckAPIView
from api.models.renovation import Renovation


def floats_are_close(a, b):
    """Comprova si dos floats són gairebé iguals"""
    return math.isclose(a, b, rel_tol=1e-9)
@pytest.fixture
def sample_renovation():
    """Fixture per crear una renovation de mostra"""
    today = date.today()
    return Renovation(
        id='test_renovation',
        creator_uid='test_user',
        refuge_id='refugi_001',
        ini_date=datetime(today.year, today.month, today.day, tzinfo=ZoneInfo('UTC')),
        fin_date=datetime(today.year, today.month, today.day, tzinfo=ZoneInfo('UTC')) + timedelta(days=14),
        description='Test renovation',
        materials_needed='Test materials',
        group_link='https://test.com',
        participants_uids=[]
    )
# ==================== TESTS DE MODELS ====================


@pytest.mark.views
class TestRefugiViews:
    """Tests per a les views de refugis"""
    
    @patch('api.views.health_check_views.RefugiLliureController')
    def test_health_check_success(self, mock_controller_class):
        """Test endpoint health check exitós"""
        mock_controller = mock_controller_class.return_value
        mock_controller.health_check.return_value = (
            {
                'status': 'healthy',
                'message': 'OK',
                'firebase': True,
                'firestore': True,
                'collections_count': 5
            },
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/health/')
        
        view = HealthCheckAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'
    
    @patch('api.views.health_check_views.RefugiLliureController')
    def test_health_check_unhealthy(self, mock_controller_class):
        """Test endpoint health check amb error"""
        mock_controller = mock_controller_class.return_value
        mock_controller.health_check.return_value = (
            {
                'status': 'unhealthy',
                'message': 'Error',
                'firebase': False
            },
            'Connection error'
        )
        
        factory = APIRequestFactory()
        request = factory.get('/health/')
        
        view = HealthCheckAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data['status'] == 'unhealthy'
    
    @patch('api.views.health_check_views.RefugiLliureController')
    def test_health_check_success_invalid_serializer(self, mock_controller_class):
        """Test health check exitós amb dades que no passen validació del serialitzador"""
        mock_controller = mock_controller_class.return_value
        # Retornem dades amb un camp extra que no està al serialitzador
        mock_controller.health_check.return_value = (
            {
                'status': 'healthy',
                'message': 'OK',
                'firebase': True,
                'firestore': True,
                'collections_count': 5,
                'extra_field': 'extra_value'  # Camp extra
            },
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/health/')
        
        view = HealthCheckAPIView.as_view()
        response = view(request)
        
        # Tot i que el serialitzador no és vàlid, retorna 200 amb les dades originals
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'
    
    @patch('api.views.health_check_views.RefugiLliureController')
    def test_health_check_unhealthy_invalid_serializer(self, mock_controller_class):
        """Test health check unhealthy amb dades que no passen validació del serialitzador"""
        mock_controller = mock_controller_class.return_value
        # Retornem dades amb un camp extra
        mock_controller.health_check.return_value = (
            {
                'status': 'unhealthy',
                'message': 'Error',
                'firebase': False,
                'extra_field': 'extra_value'  # Camp extra
            },
            'Connection error'
        )
        
        factory = APIRequestFactory()
        request = factory.get('/health/')
        
        view = HealthCheckAPIView.as_view()
        response = view(request)
        
        # Tot i que el serialitzador no és vàlid, retorna 503 amb les dades originals
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data['status'] == 'unhealthy'
    
    @patch('api.views.health_check_views.RefugiLliureController')
    def test_health_check_exception(self, mock_controller_class):
        """Test health check quan es produeix una excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.health_check.side_effect = Exception("Database connection failed")
        
        factory = APIRequestFactory()
        request = factory.get('/health/')
        
        view = HealthCheckAPIView.as_view()
        response = view(request)
        
        # Verifica que retorna error 503
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data['status'] == 'unhealthy'
        assert response.data['message'] == 'Health check failed'
        assert 'Database connection failed' not in str(response.data)
        assert response.data['firebase'] is False
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_refuge_renovations_success(self, mock_controller_class, sample_renovation):
        """Test obtenció de renovations d'un refugi exitosa"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.return_value = (True, [sample_renovation], None)
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='refugi_001')
        
        assert response.status_code == http_status.HTTP_200_OK
        assert isinstance(response.data, list)
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_refuge_renovations_error(self, mock_controller_class):
        """Test obtenció de renovations amb error"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.return_value = (False, [], 'Database error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_refuge_renovations_exception(self, mock_controller_class):
        """Test obtenció de renovations amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.side_effect = Exception('Unexpected error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
