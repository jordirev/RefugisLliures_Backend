"""
Tests per renovations
"""
import pytest
from datetime import datetime, date, timedelta
from api.models.renovation import Renovation
from api.mappers.renovation_mapper import RenovationMapper
# ===== FIXTURES =====
@pytest.fixture
def sample_renovation_data():
    """Dades de prova per a una renovation"""
    today = date.today()
    return {
        'id': 'test_renovation_id',
        'creator_uid': 'test_creator_uid',
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).isoformat(),
        'fin_date': (today + timedelta(days=5)).isoformat(),
        'description': 'Test renovation description',
        'materials_needed': 'Wood, nails, paint',
        'group_link': 'https://wa.me/group/test',
        'participants_uids': ['participant1', 'participant2']
    }
@pytest.fixture
def sample_renovation(sample_renovation_data):
    """Instància de model Renovation de prova"""
    return Renovation(
        id=sample_renovation_data['id'],
        creator_uid=sample_renovation_data['creator_uid'],
        refuge_id=sample_renovation_data['refuge_id'],
        ini_date=datetime.fromisoformat(sample_renovation_data['ini_date']),
        fin_date=datetime.fromisoformat(sample_renovation_data['fin_date']),
        description=sample_renovation_data['description'],
        materials_needed=sample_renovation_data['materials_needed'],
        group_link=sample_renovation_data['group_link'],
        participants_uids=sample_renovation_data['participants_uids']
    )
@pytest.fixture
def minimal_renovation_data():
    """Dades mínimes per crear una renovation"""
    today = date.today()
    return {
        'refuge_id': 'test_refuge_id',
        'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
        'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
        'description': 'Test renovation',
        'group_link': 'https://t.me/test'
    }
# ===== TEST MODEL =====


# ===== TEST MAPPER =====

@pytest.mark.django_db
class TestRenovationMapper:
    """Tests per al mapper de renovation"""
    
    def test_firestore_to_model(self, sample_renovation_data):
        """Test conversió de Firestore a model"""
        mapper = RenovationMapper()
        renovation = mapper.firestore_to_model(sample_renovation_data)
        
        assert isinstance(renovation, Renovation)
        assert renovation.id == sample_renovation_data['id']
        assert renovation.creator_uid == sample_renovation_data['creator_uid']
    
    def test_model_to_firestore(self, sample_renovation):
        """Test conversió de model a Firestore"""
        mapper = RenovationMapper()
        data = mapper.model_to_firestore(sample_renovation)
        
        assert isinstance(data, dict)
        assert data['id'] == sample_renovation.id
        assert data['creator_uid'] == sample_renovation.creator_uid
    
    def test_firestore_list_to_models(self, sample_renovation_data):
        """Test conversió de llista Firestore a models"""
        mapper = RenovationMapper()
        data_list = [sample_renovation_data, sample_renovation_data.copy()]
        renovations = mapper.firestore_list_to_models(data_list)
        
        assert len(renovations) == 2
        assert all(isinstance(r, Renovation) for r in renovations)
    
    def test_models_to_firestore_list(self, sample_renovation):
        """Test conversió de llista de models a Firestore"""
        mapper = RenovationMapper()
        renovations = [sample_renovation, sample_renovation]
        data_list = mapper.models_to_firestore_list(renovations)
        
        assert len(data_list) == 2
        assert all(isinstance(d, dict) for d in data_list)
