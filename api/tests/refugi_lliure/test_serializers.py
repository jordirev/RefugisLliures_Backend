"""
Tests per refugis lliures
"""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import math
from api.models.refugi_lliure import (
    Refugi,
    Coordinates,
    InfoComplementaria,
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
    
    def test_refugi_serializer_with_visitors(self):
        """Test serialització de refugi amb visitants"""
        data = {
            'id': 'test_001',
            'name': 'Test Refugi',
            'coord': {'long': 1.5, 'lat': 42.5},
            'info_comp': {},
            'visitors': ['uid_001', 'uid_002', 'uid_003']
        }
        serializer = RefugiSerializer(data=data)
        
        assert serializer.is_valid()
        assert 'visitors' in serializer.validated_data
        assert len(serializer.validated_data['visitors']) == 3
    
    def test_refugi_serializer_without_visitors(self):
        """Test serialització de refugi sense visitants (camp opcional)"""
        data = {
            'id': 'test_001',
            'name': 'Test Refugi',
            'coord': {'long': 1.5, 'lat': 42.5},
            'info_comp': {}
        }
        serializer = RefugiSerializer(data=data)
        
        assert serializer.is_valid()
        # El camp visitors és opcional, pot no estar present o estar buit
        assert 'visitors' not in serializer.validated_data or serializer.validated_data.get('visitors') == []
    
    def test_refugi_serializer_empty_visitors_list(self):
        """Test serialització de refugi amb llista de visitants buida"""
        data = {
            'id': 'test_001',
            'name': 'Test Refugi',
            'coord': {'long': 1.5, 'lat': 42.5},
            'info_comp': {},
            'visitors': []
        }
        serializer = RefugiSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data.get('visitors', []) == []
    
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
    
    def test_refugi_search_filters_serializer_type_filter(self):
        """Test filtres amb tipus de refugi"""
        data = {
            'type': 'orri,emergence'
        }
        serializer = RefugiSearchFiltersSerializer(data=data)
        
        assert serializer.is_valid()
        # Verifica que la llista de tipus es parseja correctament
        assert len(serializer.validated_data['type']) == 2
    
    def test_refugi_search_filters_serializer_invalid_type(self):
        """Test filtres amb tipus invàlid"""
        data = {
            'type': 'tipus_inventat'
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
