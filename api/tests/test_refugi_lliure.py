"""
Tests exhaustius per al mòdul Refugi Lliure
Cobreix: Views, Serializers, Controllers, DAOs, Mappers i Models
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from zoneinfo import ZoneInfo
from rest_framework import status
from rest_framework.test import APIRequestFactory
from api.models.refugi_lliure import (
    Refugi, 
    Coordinates, 
    InfoComplementaria, 
    RefugiCoordinates,
    RefugiSearchFilters
)
from api.serializers.refugi_lliure_serializer import (
    RefugiSerializer,
    CoordinatesSerializer,
    InfoComplementariaSerializer,
    RefugiSearchFiltersSerializer,
    RefugiSearchResponseSerializer,
    HealthCheckResponseSerializer
)
from api.controllers.refugi_lliure_controller import RefugiLliureController
from api.daos.refugi_lliure_dao import RefugiLliureDAO
from api.mappers.refugi_lliure_mapper import RefugiLliureMapper
from api.views.refugi_lliure_views import (
    RefugiDetailAPIView,
    RefugisCollectionAPIView
)
from api.views.health_check_views import HealthCheckAPIView
import math


def floats_are_close(a, b):
    """Comprova si dos floats són gairebé iguals"""
    return math.isclose(a, b, rel_tol=1e-9)


# ==================== TESTS DE MODELS ====================

@pytest.mark.models
class TestRefugiModels:
    """Tests per als models de Refugi"""
    
    def test_coordinates_creation(self):
        """Test creació de coordenades"""
        coord = Coordinates(long=1.5, lat=42.5)
        
        assert floats_are_close(coord.long, 1.5)
        assert floats_are_close(coord.lat, 42.5)
    
    def test_coordinates_to_dict(self, sample_coordinates):
        """Test conversió de coordenades a diccionari"""
        coord_dict = sample_coordinates.to_dict()
        
        assert isinstance(coord_dict, dict)
        assert floats_are_close(coord_dict['long'], 1.5)
        assert floats_are_close(coord_dict['lat'], 42.5)
    
    def test_coordinates_from_dict(self):
        """Test creació de coordenades des de diccionari"""
        data = {'long': 1.5, 'lat': 42.5}
        coord = Coordinates.from_dict(data)
        
        assert isinstance(coord, Coordinates)
        assert floats_are_close(coord.long, 1.5)
        assert floats_are_close(coord.lat, 42.5)
    
    def test_coordinates_from_dict_alternative_format(self):
        """Test coordenades amb format alternatiu (longitude, latitude)"""
        data = {'longitude': 1.5, 'latitude': 42.5}
        coord = Coordinates.from_dict(data)
        
        assert floats_are_close(coord.long, 1.5)
        assert floats_are_close(coord.lat, 42.5)
    
    def test_info_complementaria_creation(self):
        """Test creació d'InfoComplementaria"""
        info = InfoComplementaria(
            cheminee=1,
            poele=0,
            couvertures=1,
            latrines=1
        )
        
        assert info.cheminee == 1
        assert info.poele == 0
        assert info.couvertures == 1
        assert info.latrines == 1
    
    def test_info_complementaria_defaults(self):
        """Test valors per defecte d'InfoComplementaria"""
        info = InfoComplementaria()
        
        assert info.cheminee == 0
        assert info.poele == 0
        assert info.couvertures == 0
        assert info.matelas == 0
    
    def test_info_complementaria_to_dict(self, sample_info_complementaria):
        """Test conversió d'InfoComplementaria a diccionari"""
        info_dict = sample_info_complementaria.to_dict()
        
        assert isinstance(info_dict, dict)
        assert info_dict['cheminee'] == 1
        assert info_dict['mezzanine/etage'] == 0  # Mapejat correcte
    
    def test_info_complementaria_from_dict(self):
        """Test creació d'InfoComplementaria des de diccionari"""
        data = {
            'cheminee': 1,
            'poele': 1,
            'mezzanine/etage': 1
        }
        info = InfoComplementaria.from_dict(data)
        
        assert info.cheminee == 1
        assert info.poele == 1
        assert info.mezzanine_etage == 1
    
    def test_refugi_creation_valid(self, sample_refugi_data):
        """Test creació de refugi amb dades vàlides"""
        refugi = Refugi.from_dict(sample_refugi_data)
        
        assert refugi.id == sample_refugi_data['id']
        assert refugi.name == sample_refugi_data['name']
        assert refugi.altitude == sample_refugi_data['altitude']
        assert refugi.places == sample_refugi_data['places']
    
    def test_refugi_creation_missing_id(self):
        """Test creació de refugi sense ID (ha de fallar)"""
        with pytest.raises(ValueError, match="ID és requerit"):
            Refugi(id='', name='Test', coord=Coordinates(1.5, 42.5))
    
    def test_refugi_creation_missing_name(self):
        """Test creació de refugi sense nom (ha de fallar)"""
        with pytest.raises(ValueError, match="Name és requerit"):
            Refugi(id='test_001', name='', coord=Coordinates(1.5, 42.5))
    
    def test_refugi_creation_invalid_coordinates(self):
        """Test creació de refugi amb coordenades invàlides"""
        with pytest.raises(ValueError, match="Coordinates"):
            Refugi(id='test_001', name='Test', coord=None)
    
    def test_refugi_to_dict(self, sample_refugi):
        """Test conversió de refugi a diccionari"""
        refugi_dict = sample_refugi.to_dict()
        
        assert isinstance(refugi_dict, dict)
        assert refugi_dict['id'] == sample_refugi.id
        assert refugi_dict['name'] == sample_refugi.name
        assert 'coord' in refugi_dict
        assert 'info_comp' in refugi_dict
    
    def test_refugi_from_dict(self, sample_refugi_data):
        """Test creació de refugi des de diccionari"""
        refugi = Refugi.from_dict(sample_refugi_data)
        
        assert isinstance(refugi, Refugi)
        assert isinstance(refugi.coord, Coordinates)
        assert isinstance(refugi.info_comp, InfoComplementaria)
    
    def test_refugi_str_representation(self, sample_refugi):
        """Test representació textual del refugi"""
        refugi_str = str(sample_refugi)
        
        assert 'Refugi' in refugi_str
        assert sample_refugi.id in refugi_str
        assert sample_refugi.name in refugi_str
    
    def test_refugi_coordinates_creation(self):
        """Test creació de RefugiCoordinates"""
        coord = RefugiCoordinates(
            refugi_id='test_001',
            refugi_name='Test Refugi',
            coordinates=Coordinates(1.5, 42.5),
            geohash='abc123'
        )
        
        assert coord.refugi_id == 'test_001'
        assert coord.refugi_name == 'Test Refugi'
        assert floats_are_close(coord.coordinates.long, 1.5)
        assert floats_are_close(coord.coordinates.lat, 42.5)
        assert coord.geohash == 'abc123'
    
    def test_refugi_search_filters_creation(self):
        """Test creació de RefugiSearchFilters"""
        filters = RefugiSearchFilters(
            name='Test',
            region='Pirineus',
            places_min=5,
            places_max=15
        )
        
        assert filters.name == 'Test'
        assert filters.region == 'Pirineus'
        assert filters.places_min == 5
        assert filters.places_max == 15
    
    def test_refugi_search_filters_defaults(self):
        """Test valors per defecte de RefugiSearchFilters"""
        filters = RefugiSearchFilters()
        
        assert filters.name == ""
        assert filters.region == ""
        assert filters.places_min is None
        assert filters.cheminee is None
    
    def test_refugi_search_filters_to_dict(self, sample_search_filters):
        """Test conversió de filtres a diccionari"""
        filters_dict = sample_search_filters.to_dict()
        
        assert isinstance(filters_dict, dict)
        assert 'name' in filters_dict
        assert filters_dict['cheminee'] == 1
    
    def test_refugi_search_filters_to_dict_empty(self):
        """Test conversió de filtres buits a diccionari"""
        filters = RefugiSearchFilters()
        filters_dict = filters.to_dict()
        
        # Els filtres buits no haurien d'aparèixer
        assert len(filters_dict) == 0 or all(v for v in filters_dict.values())


# ==================== TESTS DE SERIALIZERS ====================

@pytest.mark.serializers
class TestRefugiSerializers:
    """Tests per als serializers de refugis"""
    
    def test_coordinates_serializer_valid(self):
        """Test serialització de coordenades vàlides"""
        data = {'long': 1.5, 'lat': 42.5}
        serializer = CoordinatesSerializer(data=data)
        
        assert serializer.is_valid()
        assert floats_are_close(serializer.validated_data['long'], 1.5)
        assert floats_are_close(serializer.validated_data['lat'], 42.5)
    
    def test_coordinates_serializer_invalid(self):
        """Test serialització de coordenades invàlides"""
        data = {'long': 'invalid', 'lat': 42.5}
        serializer = CoordinatesSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'long' in serializer.errors
    
    def test_info_complementaria_serializer_valid(self):
        """Test serialització d'InfoComplementaria vàlida"""
        data = {
            'cheminee': 1,
            'poele': 0,
            'couvertures': 1,
            'latrines': 1
        }
        serializer = InfoComplementariaSerializer(data=data)
        
        assert serializer.is_valid()
    
    def test_info_complementaria_serializer_defaults(self):
        """Test serialització amb valors per defecte"""
        data = {}
        serializer = InfoComplementariaSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['cheminee'] == 0
        assert serializer.validated_data['poele'] == 0
    
    def test_refugi_serializer_valid(self, sample_refugi_data):
        """Test serialització de refugi vàlid"""
        serializer = RefugiSerializer(data=sample_refugi_data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['name'] == sample_refugi_data['name']
    
    def test_refugi_serializer_missing_required_fields(self):
        """Test serialització sense camps requerits"""
        data = {'name': 'Test'}  # Falta id i coord
        serializer = RefugiSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'id' in serializer.errors or 'coord' in serializer.errors
    
    def test_refugi_search_filters_serializer_valid(self):
        """Test serialització de filtres vàlids"""
        data = {
            'name': 'Test',
            'region': 'Pirineus',
            'places_min': 5,
            'places_max': 15
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert serializer.is_valid()
    
    def test_refugi_search_filters_serializer_invalid_range(self):
        """Test filtres amb rang invàlid (min > max)"""
        data = {
            'places_min': 15,
            'places_max': 5  # Min > Max
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'places_min' in serializer.errors
    
    def test_refugi_search_filters_serializer_negative_values(self):
        """Test filtres amb valors negatius"""
        data = {
            'places_min': -5,
            'altitude_min': -100
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert not serializer.is_valid()
    
    def test_refugi_search_filters_serializer_amenities(self):
        """Test filtres amb amenitats"""
        data = {
            'cheminee': 1,
            'eau': 1,
            'matelas': 1
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert serializer.is_valid()
    
    def test_refugi_search_filters_serializer_invalid_amenity_value(self):
        """Test filtres amb valor d'amenitat invàlid"""
        data = {
            'cheminee': 2  # Ha de ser 0 o 1
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert not serializer.is_valid()
    
    def test_refugi_search_response_serializer(self):
        """Test serialització de resposta de cerca"""
        data = {
            'count': 2,
            'results': [],
            'filters': {}
        }
        serializer = RefugiSearchResponseSerializer(data=data)
        
        assert serializer.is_valid()
    
    def test_health_check_response_serializer_healthy(self):
        """Test serialització de health check (healthy)"""
        data = {
            'status': 'healthy',
            'message': 'OK',
            'firebase': True,
            'firestore': True,
            'collections_count': 5
        }
        serializer = HealthCheckResponseSerializer(data=data)
        
        assert serializer.is_valid()
    
    def test_health_check_response_serializer_unhealthy(self):
        """Test serialització de health check (unhealthy)"""
        data = {
            'status': 'unhealthy',
            'message': 'Error',
            'firebase': False
        }
        serializer = HealthCheckResponseSerializer(data=data)
        
        assert serializer.is_valid()
    
    @pytest.mark.parametrize("altitude_min,altitude_max,valid", [
        (1000, 2000, True),   # Rang vàlid
        (2000, 1000, False),  # Min > Max
        (0, 3000, True),      # Límits vàlids
        (-100, 2000, False),  # Valor negatiu
    ])
    def test_altitude_range_validation(self, altitude_min, altitude_max, valid):
        """Test validació de rangs d'altitud"""
        data = {
            'altitude_min': altitude_min,
            'altitude_max': altitude_max
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert serializer.is_valid() == valid


# ==================== TESTS DE MAPPERS ====================

@pytest.mark.mappers
class TestRefugiMapper:
    """Tests per al RefugiLliureMapper"""
    
    def test_firestore_to_model(self, sample_refugi_data, refugi_mapper):
        """Test conversió de Firestore a model"""
        refugi = refugi_mapper.firestore_to_model(sample_refugi_data)
        
        assert isinstance(refugi, Refugi)
        assert refugi.id == sample_refugi_data['id']
        assert refugi.name == sample_refugi_data['name']
    
    def test_model_to_firestore(self, sample_refugi, refugi_mapper):
        """Test conversió de model a Firestore"""
        firestore_data = refugi_mapper.model_to_firestore(sample_refugi)
        
        assert isinstance(firestore_data, dict)
        assert firestore_data['id'] == sample_refugi.id
        assert firestore_data['name'] == sample_refugi.name
    
    def test_firestore_list_to_models(self, multiple_refugis_data, refugi_mapper):
        """Test conversió de llista Firestore a models"""
        refugis = refugi_mapper.firestore_list_to_models(multiple_refugis_data)
        
        assert isinstance(refugis, list)
        assert len(refugis) == len(multiple_refugis_data)
        assert all(isinstance(r, Refugi) for r in refugis)
    
    def test_models_to_firestore_list(self, refugi_mapper):
        """Test conversió de llista de models a Firestore"""
        refugis = [
            Refugi(
                id='test_001',
                name='Test 1',
                coord=Coordinates(1.5, 42.5),
                info_comp=InfoComplementaria()
            ),
            Refugi(
                id='test_002',
                name='Test 2',
                coord=Coordinates(1.6, 42.6),
                info_comp=InfoComplementaria()
            )
        ]
        
        firestore_list = refugi_mapper.models_to_firestore_list(refugis)
        
        assert isinstance(firestore_list, list)
        assert len(firestore_list) == 2
        assert all(isinstance(r, dict) for r in firestore_list)
    
    def test_format_search_response(self, refugi_mapper):
        """Test formatació de resposta de cerca"""
        refugis = [
            Refugi(
                id='test_001',
                name='Test 1',
                coord=Coordinates(1.5, 42.5),
                info_comp=InfoComplementaria()
            )
        ]
        filters = {'region': 'Pirineus'}
        
        response = refugi_mapper.format_search_response(refugis, filters)
        
        assert 'count' in response
        assert 'results' in response
        assert 'filters' in response
        assert response['count'] == 1
    
    def test_format_search_response_from_raw_data(self, refugi_mapper):
        """Test formatació de resposta des de dades raw"""
        raw_data = [
            {'id': 'test_001', 'name': 'Test 1'},
            {'id': 'test_002', 'name': 'Test 2'}
        ]
        filters = {}
        
        response = refugi_mapper.format_search_response_from_raw_data(raw_data, filters)
        
        assert 'count' in response
        assert 'results' in response
        assert response['count'] == 2


# ==================== TESTS DE DAOs ====================

@pytest.mark.daos
class TestRefugiDAO:
    """Tests per al RefugiLliureDAO"""
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_found(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test obtenció de refugi per ID (trobat)"""
        # Cache miss
        mock_cache.get.return_value = None
        
        # Configurar Firestore mock
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Executar
        dao = RefugiLliureDAO()
        result = dao.get_by_id('refugi_001')
        
        # Verificacions
        assert result is not None
        assert result['id'] == sample_refugi_data['id']
        mock_cache.set.assert_called_once()
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_not_found(self, mock_cache, mock_firestore):
        """Test obtenció de refugi per ID (no trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        result = dao.get_by_id('nonexistent')
        
        assert result is None
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_get_by_id_from_cache(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test obtenció de refugi des de cache"""
        # Cache hit
        mock_cache.get.return_value = sample_refugi_data
        
        dao = RefugiLliureDAO()
        result = dao.get_by_id('refugi_001')
        
        assert result == sample_refugi_data
        # No hauria de cridar Firestore
        mock_firestore.get_db.assert_not_called()
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_no_filters(self, mock_cache, mock_firestore):
        """Test cerca de refugis sense filtres (retorna coordenades)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        coords_data = {
            'refugis_coordinates': [
                {
                    'refugi_id': 'ref_001',
                    'refugi_name': 'Refugi A',
                    'coordinates': {'longitude': 1.5, 'latitude': 42.5},
                    'geohash': 'abc'
                }
            ]
        }
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = coords_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        results = dao.search_refugis(filters)
        
        assert isinstance(results, list)
        assert len(results) > 0
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_with_name_filter(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test cerca de refugis amb filtre de nom"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'refugi_001'
        mock_doc.to_dict.return_value = sample_refugi_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(name='Refugi Test')
        results = dao.search_refugis(filters)
        
        assert isinstance(results, list)
        assert len(results) > 0
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_search_refugis_with_region_filter(self, mock_cache, mock_firestore):
        """Test cerca amb filtre de regió"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(region='Pirineus', departement='Ariège')
        results = dao.search_refugis(filters)
        
        assert isinstance(results, list)
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_health_check_success(self, mock_cache, mock_firestore):
        """Test health check exitós"""
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_collection = MagicMock()
        mock_db.collections.return_value = [mock_collection, mock_collection]
        
        dao = RefugiLliureDAO()
        result = dao.health_check()
        
        assert result['firebase'] is True
        assert result['firestore'] is True
        assert result['collections_count'] == 2
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    def test_health_check_failure(self, mock_firestore):
        """Test health check amb error"""
        mock_firestore.get_db.side_effect = Exception('Connection error')
        
        dao = RefugiLliureDAO()
        
        with pytest.raises(Exception):
            dao.health_check()
    
    def test_has_active_filters_true(self):
        """Test comprovació de filtres actius (true)"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters(name='Test', region='Pirineus')
        
        result = dao._has_active_filters(filters)
        
        assert result is True
    
    def test_has_active_filters_false(self):
        """Test comprovació de filtres actius (false)"""
        dao = RefugiLliureDAO()
        filters = RefugiSearchFilters()
        
        result = dao._has_active_filters(filters)
        
        assert result is False
    
    def test_matches_memory_filters_places_range(self):
        """Test filtres en memòria per rang de places"""
        dao = RefugiLliureDAO()
        refugi_data = {'places': 10}
        filters = RefugiSearchFilters(places_min=5, places_max=15)
        
        result = dao._matches_memory_filters(refugi_data, filters)
        
        assert result is True
    
    def test_matches_memory_filters_places_out_of_range(self):
        """Test filtres en memòria amb places fora de rang"""
        dao = RefugiLliureDAO()
        refugi_data = {'places': 20}
        filters = RefugiSearchFilters(places_min=5, places_max=15)
        
        result = dao._matches_memory_filters(refugi_data, filters)
        
        assert result is False
    
    def test_matches_memory_filters_amenities(self):
        """Test filtres en memòria per amenitats"""
        dao = RefugiLliureDAO()
        refugi_data = {
            'info_comp': {
                'cheminee': 1,
                'eau': 1
            }
        }
        filters = RefugiSearchFilters(cheminee=1, eau=1)
        
        result = dao._matches_memory_filters(refugi_data, filters)
        
        assert result is True
    
    def test_matches_memory_filters_missing_amenities(self):
        """Test filtres amb amenitats no disponibles"""
        dao = RefugiLliureDAO()
        refugi_data = {
            'info_comp': {
                'cheminee': 0,
                'eau': 1
            }
        }
        filters = RefugiSearchFilters(cheminee=1, eau=1)
        
        result = dao._matches_memory_filters(refugi_data, filters)
        
        assert result is False


# ==================== TESTS DE CONTROLLERS ====================

@pytest.mark.controllers
class TestRefugiController:
    """Tests per al RefugiLliureController"""
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureMapper')
    def test_get_refugi_by_id_success(self, mock_mapper_class, mock_dao_class, sample_refugi_data, sample_refugi):
        """Test obtenció de refugi per ID exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = sample_refugi_data
        
        mock_mapper = mock_mapper_class.return_value
        mock_mapper.firestore_to_model.return_value = sample_refugi
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001')
        
        assert refugi is not None
        assert error is None
        assert isinstance(refugi, Refugi)
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_get_refugi_by_id_not_found(self, mock_dao_class):
        """Test obtenció de refugi no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_by_id.return_value = None
        
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('nonexistent')
        
        assert refugi is None
        assert error is not None
        assert 'not found' in error.lower()
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureMapper')
    def test_search_refugis_no_filters(self, mock_mapper_class, mock_dao_class):
        """Test cerca sense filtres"""
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.return_value = [
            {'id': 'ref_001', 'name': 'Test 1'},
            {'id': 'ref_002', 'name': 'Test 2'}
        ]
        
        mock_mapper = mock_mapper_class.return_value
        mock_mapper.format_search_response_from_raw_data.return_value = {
            'count': 2,
            'results': []
        }
        
        controller = RefugiLliureController()
        result, error = controller.search_refugis({})
        
        assert result is not None
        assert error is None
        assert 'count' in result
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureMapper')
    def test_search_refugis_with_filters(self, mock_mapper_class, mock_dao_class, multiple_refugis_data):
        """Test cerca amb filtres"""
        mock_dao = mock_dao_class.return_value
        mock_dao.search_refugis.return_value = multiple_refugis_data
        
        mock_mapper = mock_mapper_class.return_value
        mock_refugis = [Refugi.from_dict(d) for d in multiple_refugis_data]
        mock_mapper.firestore_list_to_models.return_value = mock_refugis
        mock_mapper.format_search_response.return_value = {
            'count': len(mock_refugis),
            'results': multiple_refugis_data,
            'filters': {'region': 'Pirineus'}
        }
        
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params)
        
        assert result is not None
        assert error is None
        assert result['count'] == len(multiple_refugis_data)
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_success(self, mock_dao_class):
        """Test health check exitós"""
        mock_dao = mock_dao_class.return_value
        mock_dao.health_check.return_value = {
            'firebase': True,
            'firestore': True,
            'collections_count': 5
        }
        
        controller = RefugiLliureController()
        result, error = controller.health_check()
        
        assert result is not None
        assert error is None
        assert result['status'] == 'healthy'
        assert result['firebase'] is True
    
    @patch('api.controllers.refugi_lliure_controller.RefugiLliureDAO')
    def test_health_check_failure(self, mock_dao_class):
        """Test health check amb error"""
        mock_dao = mock_dao_class.return_value
        mock_dao.health_check.side_effect = Exception('Connection error')
        
        controller = RefugiLliureController()
        result, error = controller.health_check()
        
        assert result is not None
        assert error is not None
        assert result['status'] == 'unhealthy'


# ==================== TESTS DE VIEWS ====================

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
        request = factory.get('/refugis/refugi_001/')
        
        view = RefugiDetailAPIView.as_view()
        response = view(request, refugi_id='refugi_001')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'id' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugi_detail_not_found(self, mock_controller_class):
        """Test obtenció de refugi no existent"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugi_by_id.return_value = (None, 'Refugi not found')
        
        factory = APIRequestFactory()
        request = factory.get('/refugis/nonexistent/')
        
        view = RefugiDetailAPIView.as_view()
        response = view(request, refugi_id='nonexistent')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
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
        request = factory.get('/refugis/')
        
        view = RefugisCollectionAPIView.as_view()
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
        request = factory.get('/refugis/', {'region': 'Pirineus'})
        
        view = RefugisCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_invalid_filters(self, mock_controller_class):
        """Test cerca amb filtres invàlids"""
        factory = APIRequestFactory()
        request = factory.get('/refugis/', {
            'places_min': 15,
            'places_max': 5  # Min > Max
        })
        
        view = RefugisCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.refugi_lliure_views.RefugiLliureController')
    def test_get_refugis_collection_server_error(self, mock_controller_class):
        """Test cerca amb error del servidor"""
        mock_controller = mock_controller_class.return_value
        mock_controller.search_refugis.return_value = (None, 'Internal server error')
        
        factory = APIRequestFactory()
        request = factory.get('/refugis/')
        
        view = RefugisCollectionAPIView.as_view()
        response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS D'INTEGRACIÓ ====================

@pytest.mark.integration
class TestRefugiIntegration:
    """Tests d'integració entre components"""
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_full_refugi_retrieval_flow(self, mock_cache, mock_firestore, sample_refugi_data):
        """Test flux complet d'obtenció de refugi"""
        # Configurar mocks
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = sample_refugi_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Executar flux complet
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id('refugi_001')
        
        # Verificacions
        assert refugi is not None
        assert error is None
        assert isinstance(refugi, Refugi)
        assert refugi.id == sample_refugi_data['id']
    
    @patch('api.daos.refugi_lliure_dao.firestore_service')
    @patch('api.daos.refugi_lliure_dao.cache_service')
    def test_full_search_flow_with_filters(self, mock_cache, mock_firestore, multiple_refugis_data):
        """Test flux complet de cerca amb filtres"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore.get_db.return_value = mock_db
        
        mock_docs = []
        for data in multiple_refugis_data:
            mock_doc = MagicMock()
            mock_doc.id = data['id']
            mock_doc.to_dict.return_value = data
            mock_docs.append(mock_doc)
        
        mock_query = MagicMock()
        mock_query.stream.return_value = mock_docs
        mock_query.where.return_value = mock_query
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        # Executar cerca
        controller = RefugiLliureController()
        query_params = {'region': 'Pirineus'}
        result, error = controller.search_refugis(query_params)
        
        # Verificacions
        assert result is not None
        assert error is None
        assert 'count' in result
        assert 'results' in result


# ==================== TESTS DE CASOS EXTREMS ====================

@pytest.mark.unit
class TestEdgeCases:
    """Tests de casos extrems i límits"""
    
    def test_refugi_with_empty_links(self):
        """Test refugi amb llista de links buida"""
        refugi = Refugi(
            id='test',
            name='Test',
            coord=Coordinates(1.5, 42.5),
            links=[]
        )
        
        assert refugi.links == []
    
    def test_refugi_with_none_optional_fields(self):
        """Test refugi amb camps opcionals a None"""
        refugi = Refugi(
            id='test',
            name='Test',
            coord=Coordinates(1.5, 42.5),
            region=None,
            departement=None
        )
        
        assert refugi.region is None
        assert refugi.departement is None
    
    def test_search_filters_with_all_amenities(self):
        """Test filtres amb totes les amenitats activades"""
        filters = RefugiSearchFilters(
            cheminee=1,
            poele=1,
            couvertures=1,
            latrines=1,
            bois=1,
            eau=1,
            matelas=1,
            couchage=1,
            lits=1
        )
        
        filters_dict = filters.to_dict()
        assert len(filters_dict) >= 9
    
    def test_coordinates_with_extreme_values(self):
        """Test coordenades amb valors extrems"""
        coord = Coordinates(long=180.0, lat=90.0)
        
        assert floats_are_close(coord.long, 180.0)
        assert floats_are_close(coord.lat, 90.0)
    
    @pytest.mark.parametrize("places", [0, 1, 100, 999])
    def test_refugi_with_various_places(self, places):
        """Test refugi amb diversos valors de places"""
        refugi = Refugi(
            id='test',
            name='Test',
            coord=Coordinates(1.5, 42.5),
            places=places
        )
        
        assert refugi.places == places
    
    @pytest.mark.parametrize("altitude", [0, 1000, 3000, 4807])
    def test_refugi_with_various_altitudes(self, altitude):
        """Test refugi amb diverses altituds"""
        refugi = Refugi(
            id='test',
            name='Test',
            coord=Coordinates(1.5, 42.5),
            altitude=altitude
        )
        
        assert refugi.altitude == altitude
