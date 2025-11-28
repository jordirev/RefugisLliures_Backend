"""
Tests per renovations
"""
import pytest
from datetime import datetime, date, timedelta
from api.models.renovation import Renovation

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


# ===== TEST MODEL =====

@pytest.mark.django_db
class TestRenovationModel:
    """Tests per al model Renovation"""
    
    def test_renovation_creation_valid(self, sample_renovation_data):
        """Test creació vàlida d'una renovation"""
        renovation = Renovation(
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
        
        assert renovation.id == sample_renovation_data['id']
        assert renovation.creator_uid == sample_renovation_data['creator_uid']
        assert renovation.refuge_id == sample_renovation_data['refuge_id']
        assert renovation.description == sample_renovation_data['description']
    
    def test_renovation_missing_id(self):
        """Test creació amb ID buit"""
        today = date.today()
        with pytest.raises(ValueError, match="ID és requerit"):
            Renovation(
                id='',
                creator_uid='test_uid',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                description='Test',
                group_link='https://wa.me/test'
            )
    
    def test_renovation_missing_creator_uid(self):
        """Test creació amb creator_uid buit"""
        today = date.today()
        with pytest.raises(ValueError, match="Creator UID és requerit"):
            Renovation(
                id='test_id',
                creator_uid='',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                description='Test',
                group_link='https://wa.me/test'
            )
    
    def test_renovation_missing_refuge_id(self):
        """Test creació amb refuge_id buit"""
        today = date.today()
        with pytest.raises(ValueError, match="Refuge ID és requerit"):
            Renovation(
                id='test_id',
                creator_uid='test_uid',
                refuge_id='',
                ini_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                description='Test',
                group_link='https://wa.me/test'
            )
    
    def test_renovation_invalid_dates(self):
        """Test amb data d'inici posterior a data de finalització"""
        today = date.today()
        with pytest.raises(ValueError, match="Data d'inici ha de ser anterior"):
            Renovation(
                id='test_id',
                creator_uid='test_uid',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                description='Test',
                group_link='https://wa.me/test'
            )
    
    def test_renovation_equal_dates(self):
        """Test amb dates iguals"""
        today = date.today()
        same_date = (today + timedelta(days=1)).isoformat()
        with pytest.raises(ValueError, match="Data d'inici ha de ser anterior"):
            Renovation(
                id='test_id',
                creator_uid='test_uid',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat(same_date),
                fin_date=datetime.fromisoformat(same_date),
                description='Test',
                group_link='https://wa.me/test'
            )
    
    def test_renovation_missing_description(self):
        """Test creació sense descripció"""
        today = date.today()
        with pytest.raises(ValueError, match="Descripció és requerida"):
            Renovation(
                id='test_id',
                creator_uid='test_uid',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                description=None,
                group_link='https://wa.me/test'
            )
    
    def test_renovation_missing_group_link(self):
        """Test creació sense group_link"""
        today = date.today()
        with pytest.raises(ValueError, match="Enllaç de grup és requerit"):
            Renovation(
                id='test_id',
                creator_uid='test_uid',
                refuge_id='test_refuge',
                ini_date=datetime.fromisoformat((today + timedelta(days=1)).isoformat()),
                fin_date=datetime.fromisoformat((today + timedelta(days=5)).isoformat()),
                description='Test',
                group_link=None
            )
    
    def test_renovation_to_dict(self, sample_renovation):
        """Test conversió a diccionari"""
        renovation_dict = sample_renovation.to_dict()
        
        assert renovation_dict['id'] == sample_renovation.id
        assert renovation_dict['creator_uid'] == sample_renovation.creator_uid
        assert renovation_dict['refuge_id'] == sample_renovation.refuge_id
        assert renovation_dict['description'] == sample_renovation.description
        assert isinstance(renovation_dict['ini_date'], str)
        assert isinstance(renovation_dict['fin_date'], str)
    
    def test_renovation_from_dict(self, sample_renovation_data):
        """Test creació des d'un diccionari"""
        renovation = Renovation.from_dict(sample_renovation_data)
        
        assert renovation.id == sample_renovation_data['id']
        assert renovation.creator_uid == sample_renovation_data['creator_uid']
        assert renovation.refuge_id == sample_renovation_data['refuge_id']
        assert renovation.description == sample_renovation_data['description']
    
    def test_renovation_str_representation(self, sample_renovation):
        """Test representació textual"""
        str_repr = str(sample_renovation)
        
        assert 'Renovation' in str_repr
        assert sample_renovation.id in str_repr
        assert sample_renovation.creator_uid in str_repr
