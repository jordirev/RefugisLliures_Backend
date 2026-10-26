"""
Tests de les vistes legacy que continuen a `api/`: health check.
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
from api.views.health_check_views import HealthCheckAPIView


def floats_are_close(a, b):
    """Comprova si dos floats són gairebé iguals"""
    return math.isclose(a, b, rel_tol=1e-9)


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
