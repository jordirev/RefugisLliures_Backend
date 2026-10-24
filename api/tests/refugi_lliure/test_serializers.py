"""
Tests dels serializers legacy de refugi que encara fan servir altres dominis.
(`RefugiSerializer` i els filtres de cerca viuen a `apps.refuges.serializers`.)
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
    CoordinatesSerializer,
    InfoComplementariaSerializer,
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
