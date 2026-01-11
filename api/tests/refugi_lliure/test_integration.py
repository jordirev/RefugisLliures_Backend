"""
Tests d'integració per a refugis lliures.
Aquests tests proven el flux complet des de la vista fins a la base de dades.
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory
from rest_framework import status
from api.views.refugi_lliure_views import (
    RefugiLliureDetailAPIView,
    RefugiLliureCollectionAPIView,
    RefugeRenovationsAPIView
)
from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
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

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refuge_detail_complete_flow(self, mock_dao_class):
        """Test flux complet: GET refugi -> Controller -> DAO -> View"""
        # Preparar model del refugi
        from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
        
        refugi_model = Refugi(
            id='refugi_001',
            name='Refugi Test',
            departement='Ariège',
            coord=Coordinates(long=1.5, lat=42.5),
            places=10,
            altitude=2000,
            info_comp=InfoComplementaria(
                cheminee=1,
                poele=1,
                eau=1,
                matelas=5,
                couvertures=5,
                couchage=10,
                lits=2,
                bas_flancs=2,
                latrines=1,
                bois=1,
                mezzanine_etage=1,
                manque_un_mur=0
            ),
            visitors=[]
        )
        
        # Configurar mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = refugi_model
        
        # Crear request
        request = self._get_authenticated_request('GET', '/api/refuges/refugi_001/')
        
        # Executar vista
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, id='refugi_001')
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == 'refugi_001'
        assert response.data['name'] == 'Refugi Test'
        assert response.data['places'] == 10
        assert 'coord' in response.data
        assert 'info_comp' in response.data
        
        # Verificar que el DAO es va cridar correctament
        mock_dao.get_by_id.assert_called_once_with('refugi_001')

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_all_refuges_with_filters(self, mock_dao_class):
        """Test flux complet: GET refugis amb filtres"""
        # Preparar models de refugis
        from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
        
        refugis_models = [
            Refugi(
                id='refugi_001',
                name='Refugi A',
                departement='Ariège',
                coord=Coordinates(long=1.5, lat=42.5),
                places=10,
                altitude=2000,
                info_comp=InfoComplementaria(),
                visitors=[]
            ),
            Refugi(
                id='refugi_002',
                name='Refugi B',
                departement='Ariège',
                coord=Coordinates(long=1.6, lat=42.6),
                places=15,
                altitude=2100,
                info_comp=InfoComplementaria(),
                visitors=[]
            )
        ]
        
        # Configurar mock
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.return_value = {
            'results': refugis_models,
            'has_filters': True
        }
        
        # Crear request amb query params
        request = self._get_authenticated_request(
            'GET', 
            '/api/refuges/',
            query_params={'places_min': '10'}
        )
        
        # Executar vista
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert 'count' in response.data
        assert 'results' in response.data
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['id'] == 'refugi_001'
        assert response.data['results'][1]['id'] == 'refugi_002'
        
        # Verificar que el DAO es va cridar
        mock_dao.search_refugis.assert_called_once()

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refuge_not_found(self, mock_dao_class):
        """Test flux complet quan un refugi no existeix"""
        # Configurar mock per retornar None
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = None
        
        # Crear request
        request = self._get_authenticated_request('GET', '/api/refuges/refugi_999/')
        
        # Executar vista
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, id='refugi_999')
        
        # Verificar resposta d'error
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data

    @patch('api.views.refugi_lliure_views.RenovationController')
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

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_search_refuges_by_location(self, mock_dao_class):
        """Test flux complet: Cerca de refugis per ubicació"""
        # Preparar dades
        nearby_refuges = [
            {
                'id': 'refugi_001',
                'nom': 'Refugi Proper',
                'departement': 'Ariège',
                'coord': {'long': 1.5, 'lat': 42.5},
                'places': 10,
                'altitude': 2000,
                'info_complementaria': {}
            }
        ]
        
        # Configurar mock
        mock_dao = mock_dao_class.return_value
        mock_dao.get_all_refugis.return_value = nearby_refuges
        
        # Crear request amb coordenades
        request = self._get_authenticated_request(
            'GET',
            '/api/refuges/',
            query_params={
                'longitude': '1.5',
                'latitude': '42.5',
                'radius': '10'
            }
        )
        
        # Executar vista
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refuge_with_missing_optional_fields(self, mock_dao_class):
        """Test flux amb refugi que té camps opcionals buits"""
        # Preparar model amb camps mínims
        from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria
        
        refugi_model = Refugi(
            id='refugi_minimal',
            name='Refugi Mínim',
            departement='Ariège',
            coord=Coordinates(long=1.5, lat=42.5),
            places=5,
            altitude=1500,
            info_comp=InfoComplementaria(),
            visitors=[]
        )
        
        # Configurar mock
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = refugi_model
        
        # Crear request
        request = self._get_authenticated_request('GET', '/api/refuges/refugi_minimal/')
        
        # Executar vista
        view = RefugiLliureDetailAPIView.as_view()
        response = view(request, id='refugi_minimal')
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == 'refugi_minimal'
        assert response.data['name'] == 'Refugi Mínim'

    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refuges_empty_result(self, mock_dao_class):
        """Test flux quan no hi ha refugis"""
        # Configurar mock per retornar llista buida
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.return_value = {
            'results': [],
            'has_filters': False
        }
        
        # Crear request
        request = self._get_authenticated_request('GET', '/api/refuges/')
        
        # Executar vista
        view = RefugiLliureCollectionAPIView.as_view()
        response = view(request)
        
        # Verificar resposta buida
        assert response.status_code == status.HTTP_200_OK
        assert 'count' in response.data
        assert response.data['count'] == 0
        assert 'results' in response.data
        assert len(response.data['results']) == 0
