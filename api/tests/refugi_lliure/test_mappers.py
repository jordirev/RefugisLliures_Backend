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
from api.mappers.refugi_lliure_mapper import RefugiLliureMapper
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
