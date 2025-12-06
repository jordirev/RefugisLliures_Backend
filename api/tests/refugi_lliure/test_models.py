"""
Tests per refugis lliures
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from api.models.refugi_lliure import (
    Refugi, 
    Coordinates, 
    InfoComplementaria, 
    RefugiCoordinates,
    RefugiSearchFilters
)
from api.models.renovation import Renovation
from datetime import date, timedelta
import math


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
            refuge_id='test_001',
            refugi_name='Test Refugi',
            coord=Coordinates(1.5, 42.5),
            geohash='abc123'
        )
        
        assert coord.refuge_id == 'test_001'
        assert coord.refugi_name == 'Test Refugi'
        assert floats_are_close(coord.coord.long, 1.5)
        assert floats_are_close(coord.coord.lat, 42.5)
        assert coord.geohash == 'abc123'
    
    def test_refugi_search_filters_creation(self):
        """Test creació de RefugiSearchFilters"""
        filters = RefugiSearchFilters(
            name='Test',
            type=['garde'],
            places_min=5,
            places_max=15
        )
        
        assert filters.name == 'Test'
        assert filters.type == ['garde']
        assert filters.places_min == 5
        assert filters.places_max == 15
    
    def test_refugi_search_filters_defaults(self):
        """Test valors per defecte de RefugiSearchFilters"""
        filters = RefugiSearchFilters()
        
        assert filters.name == ""
        assert filters.type == []
        assert filters.condition == []
        assert filters.places_min is None
        assert filters.altitude_max is None
    
    def test_refugi_search_filters_to_dict(self):
        """Test conversió de filtres a diccionari"""
        filters = RefugiSearchFilters(
            name='Test',
            type=['garde', 'orri'],
            condition=[0, 1],
            places_min=5,
            altitude_max=2500
        )
        filters_dict = filters.to_dict()
        
        assert isinstance(filters_dict, dict)
        assert filters_dict['name'] == 'Test'
        assert filters_dict['type'] == ['garde', 'orri']
        assert filters_dict['condition'] == [0, 1]
        assert filters_dict['places_min'] == 5
        assert filters_dict['altitude_max'] == 2500
    
    def test_refugi_search_filters_to_dict_empty(self):
        """Test conversió de filtres buits a diccionari"""
        filters = RefugiSearchFilters()
        filters_dict = filters.to_dict()
        
        # Els filtres buits no haurien d'aparèixer
        assert len(filters_dict) == 0 or all(v for v in filters_dict.values())


# ==================== TESTS DE SERIALIZERS ====================
