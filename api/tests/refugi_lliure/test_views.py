"""
Tests per refugis lliures
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
from api.views.refugi_lliure_views import (
    RefugiLliureDetailAPIView,
    RefugiLliureCollectionAPIView,
    RefugeRenovationsAPIView
)
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
        assert 'Error: Database connection failed' in response.data['message']
        assert response.data['firebase'] is False
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_success(self, mock_controller_class, sample_refugi):
        """Test obtenció de detall de refugi exitosa"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugi_by_id.return_value = (sample_refugi, None)
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/')
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_not_found(self, mock_controller_class):
        """Test obtenció de refugi no existent"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugi_by_id.return_value = (None, 'Refugi not found')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/nonexistent/')
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='nonexistent')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_without_auth_no_visitors(self, mock_controller_class, sample_refugi):
        """Test obtenció de detall de refugi sense autenticació - no retorna visitants"""
        # Configurar el mock per retornar refugi sense visitants quan include_visitors=False
        mock_controller = mock_controller_class.return_value
        
        def get_refugi_side_effect(refuge_id, include_visitors=False):
            refugi_copy = Refugi.from_dict(sample_refugi.to_dict())
            if not include_visitors:
                refugi_copy.visitors = []
            else:
                refugi_copy.visitors = ['uid_001', 'uid_002', 'uid_003']
            return (refugi_copy, None)
        
        mock_controller.get_refugi_by_id.side_effect = get_refugi_side_effect
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/')
        # No afegir autenticació - usuari anònim
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
        # Verificar que els visitants NO estan en la resposta o estan buits
        assert response.data.get('visitors', []) == []
        # Verificar que el controller es va cridar amb include_visitors=False
        mock_controller.get_refugi_by_id.assert_called_once_with('refugi_001', include_visitors=False)
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_with_auth_includes_visitors(self, mock_controller_class, sample_refugi, db):
        """Test obtenció de detall de refugi amb autenticació - retorna visitants"""
        from django.contrib.auth.models import User
        from rest_framework.test import force_authenticate
        
        # Configurar el mock per retornar refugi amb visitants quan include_visitors=True
        mock_controller = mock_controller_class.return_value
        
        def get_refugi_side_effect(refuge_id, include_visitors=False):
            refugi_copy = Refugi.from_dict(sample_refugi.to_dict())
            if not include_visitors:
                refugi_copy.visitors = []
            else:
                refugi_copy.visitors = ['uid_001', 'uid_002', 'uid_003']
            return (refugi_copy, None)
        
        mock_controller.get_refugi_by_id.side_effect = get_refugi_side_effect
        
        # Crear un usuari autenticat real
        user = User.objects.create_user(username='testuser', password='testpass')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/')
        force_authenticate(request, user=user)
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
        # Verificar que els visitants estan en la resposta
        assert 'visitors' in response.data
        assert len(response.data['visitors']) == 3
        assert response.data['visitors'] == ['uid_001', 'uid_002', 'uid_003']
        # Verificar que el controller es va cridar amb include_visitors=True
        mock_controller.get_refugi_by_id.assert_called_once_with('refugi_001', include_visitors=True)
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_no_filters(self, mock_controller_class):
        """Test obtenció de col·lecció sense filtres"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (
            {
                'count': 2,
                'results': [
                    {'id': 'ref_001', 'name': 'Test 1'},
                    {'id': 'ref_002', 'name': 'Test 2'}
                ]
            },
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/')
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'count' in response.data
        assert response.data['count'] == 2
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_with_filters(self, mock_controller_class):
        """Test obtenció de col·lecció amb filtres"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (
            {
                'count': 1,
                'results': [{'id': 'ref_001', 'name': 'Test 1'}],
                'filters': {'region': 'Pirineus'}
            },
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/', {'region': 'Pirineus'})
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_without_auth_no_visitors(self, mock_controller_class):
        """Test obtenció de col·lecció sense autenticació - no retorna visitants"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (
            {
                'count': 1,
                'results': [{'id': 'ref_001', 'name': 'Test 1', 'visitors': []}],
            },
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/', {'region': 'Pirineus'})
        # No autenticar l'usuari
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        # Verificar que search_refugis es va cridar amb include_visitors=False
        mock_controller.search_refugis.assert_called_once()
        call_args = mock_controller.search_refugis.call_args
        assert call_args[1]['include_visitors'] == False
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_with_auth_includes_visitors(self, mock_controller_class, db):
        """Test obtenció de col·lecció amb autenticació - retorna visitants"""
        from django.contrib.auth.models import User
        from rest_framework.test import force_authenticate
        
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (
            {
                'count': 1,
                'results': [{'id': 'ref_001', 'name': 'Test 1', 'visitors': ['uid_001', 'uid_002']}],
            },
            None
        )
        
        # Crear un usuari autenticat real
        user = User.objects.create_user(username='testuser', password='testpass')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/', {'region': 'Pirineus'})
        force_authenticate(request, user=user)
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        # Verificar que search_refugis es va cridar amb include_visitors=True
        mock_controller.search_refugis.assert_called_once()
        call_args = mock_controller.search_refugis.call_args
        assert call_args[1]['include_visitors'] == True
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_invalid_filters(self, mock_controller_class):
        """Test cerca amb filtres invàlids"""
        factory = APIRequestFactory()
        request = factory.get('/refuges/', {
            'places_min': 15,
            'places_max': 5  # Min > Max
        })
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_server_error(self, mock_controller_class):
        """Test cerca amb error del servidor"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (None, 'Internal server error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/')
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_exception(self, mock_controller_class):
        """Test cerca amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.side_effect = Exception('Unexpected error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/')
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_invalid_serializer(self, mock_controller_class):
        """Test cerca amb resposta que no es pot serialitzar"""
        mock_controller = mock_controller_class.return_value
        # Retornem un dict sense alguns camps obligatoris
        mock_controller.search_refugis.return_value = (
            {'invalid': 'data'},
            None
        )
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/')
        
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
        # Ha de retornar les dades sense validar
        assert 'invalid' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_controller_error(self, mock_controller_class):
        """Test obtenció de refugi amb error del controller (no 'not found')"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugi_by_id.return_value = (None, 'Database error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/')
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_exception(self, mock_controller_class):
        """Test obtenció de refugi amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugi_by_id.side_effect = Exception('Unexpected error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/')
        
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RenovationController')
    def test_get_refuge_renovations_success(self, mock_controller_class, sample_renovation):
        """Test obtenció de renovations d'un refugi exitosa"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.return_value = (True, [sample_renovation], None)
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == http_status.HTTP_200_OK
        assert isinstance(response.data, list)
    
    @patch('api.views.refugi_lliure_views.RenovationController')
    def test_get_refuge_renovations_error(self, mock_controller_class):
        """Test obtenció de renovations amb error"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.return_value = (False, [], 'Database error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RenovationController')
    def test_get_refuge_renovations_exception(self, mock_controller_class):
        """Test obtenció de renovations amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.side_effect = Exception('Unexpected error')
        
        factory = APIRequestFactory()
        request = factory.get('/refuges/refugi_001/renovations/')
        
        view = RefugeRenovationsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, refuge_id='refugi_001')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS D'INTEGRACIÓ ====================
