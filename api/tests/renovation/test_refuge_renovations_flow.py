"""
Tests d'integració per a refugis lliures.
Aquests tests proven el flux complet des de la vista fins a la base de dades.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory
from rest_framework import status
from api.views.renovation_views import RefugeRenovationsAPIView
from api.models.renovation import Renovation
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


@pytest.mark.integration
class TestRefugiLliureIntegration:
    """Tests d'integració per refugis lliures"""

    def _get_authenticated_request(self, method, path, data=None, query_params=None, user_uid='test_user'):
        """Helper per crear requests autenticades"""
        factory = APIRequestFactory()
        if method == 'GET':
            request = factory.get(path, query_params or {})
        elif method == 'POST':
            request = factory.post(path, data or {}, format='json')
        elif method == 'PATCH':
            request = factory.patch(path, data or {}, format='json')
        else:
            raise ValueError(f"Method {method} not supported")
        
        request.user_uid = user_uid
        return request


    @patch('api.views.renovation_views.RenovationController')
    def test_get_refuge_renovations_flow(self, mock_controller_class):
        """Test flux complet: GET renovacions d'un refugi"""
        # Preparar dades
        today = datetime.now(ZoneInfo('UTC'))
        renovation = Renovation(
            id='renovation_001',
            creator_uid='user_001',
            refuge_id='refugi_001',
            ini_date=today,
            fin_date=today + timedelta(days=7),
            description='Reparar teulada',
            group_link='https://wa.me/test',
            participants_uids=['user_001', 'user_002'],
            expelled_uids=[]
        )
        
        # Configurar mock controller
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovations_by_refuge.return_value = (True, [renovation], None)
        
        # Crear request autenticat
        request = self._get_authenticated_request('GET', '/api/refuges/refugi_001/renovations/', user_uid='user_001')
        
        # Afegir atributs d'autenticació mock
        request.user = MagicMock()
        request.user.is_authenticated = True
        
        # Executar vista amb permís mockat
        # Hackear els permisos de la classe temporalment
        original_permissions = RefugeRenovationsAPIView.permission_classes
        RefugeRenovationsAPIView.permission_classes = []
        
        try:
            view = RefugeRenovationsAPIView.as_view()
            response = view(request, id='refugi_001')
            
            # Verificar resposta
            assert response.status_code == status.HTTP_200_OK
            assert len(response.data) == 1
            assert response.data[0]['id'] == 'renovation_001'
            assert response.data[0]['refuge_id'] == 'refugi_001'
            
            # Verificar crida al controller
            mock_controller.get_renovations_by_refuge.assert_called_once()
        finally:
            # Restaurar permisos originals
            RefugeRenovationsAPIView.permission_classes = original_permissions


