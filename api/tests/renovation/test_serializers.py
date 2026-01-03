"""
Tests per renovations
"""
import pytest
from datetime import datetime, date, timedelta
from api.models.renovation import Renovation
from api.serializers.renovation_serializer import (
    RenovationSerializer,
    RenovationCreateSerializer,
    RenovationUpdateSerializer,
    DateValidationMixin
)

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


# ===== TEST SERIALIZERS =====

@pytest.mark.django_db
class TestRenovationSerializers:
    """Tests per als serializers de renovation"""
    
    def test_date_validation_mixin_valid_dates(self):
        """Test validació de dates vàlides"""
        today = date.today()
        ini_date = today + timedelta(days=1)
        fin_date = today + timedelta(days=5)
        
        # No hauria de llançar error
        DateValidationMixin.validate_dates(ini_date, fin_date)
    
    def test_date_validation_mixin_invalid_dates(self):
        """Test validació amb dates invàlides"""
        from rest_framework import serializers
        today = date.today()
        ini_date = today + timedelta(days=5)
        fin_date = today + timedelta(days=1)
        
        with pytest.raises(serializers.ValidationError):
            DateValidationMixin.validate_dates(ini_date, fin_date)
    
    def test_date_validation_mixin_equal_dates(self):
        """Test validació amb dates iguals - dates iguals són permeses"""
        from rest_framework import serializers
        today = date.today()
        same_date = today + timedelta(days=1)
        
        # Equal dates should not raise an error according to current implementation
        # The validation only checks ini_date > fin_date, so ini_date == fin_date is valid
        try:
            DateValidationMixin.validate_dates(same_date, same_date)
        except serializers.ValidationError:
            pytest.fail("Equal dates should be valid according to current implementation")
    
    def test_date_validation_mixin_past_date(self):
        """Test validació data passada"""
        from rest_framework import serializers
        yesterday = date.today() - timedelta(days=1)
        
        with pytest.raises(serializers.ValidationError):
            DateValidationMixin.validate_ini_date_is_current_or_future(yesterday)
    
    def test_date_validation_mixin_today_valid(self):
        """Test validació data d'avui (vàlida)"""
        today = date.today()
        
        # No hauria de llançar error
        DateValidationMixin.validate_ini_date_is_current_or_future(today)
    
    def test_renovation_serializer_valid_data(self, sample_renovation_data):
        """Test serialització amb dades vàlides"""
        serializer = RenovationSerializer(data=sample_renovation_data)
        
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['refuge_id'] == sample_renovation_data['refuge_id']
    
    def test_renovation_serializer_missing_required_fields(self):
        """Test serialització amb camps requerits mancants"""
        data = {'description': 'Test'}
        serializer = RenovationSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'refuge_id' in serializer.errors
        assert 'ini_date' in serializer.errors
        assert 'fin_date' in serializer.errors
    
    def test_renovation_serializer_to_representation(self, sample_renovation):
        """Test representació d'una instància"""
        serializer = RenovationSerializer(sample_renovation)
        data = serializer.data
        
        assert data['id'] == sample_renovation.id
        assert data['creator_uid'] == sample_renovation.creator_uid
        # Les dates haurien de ser només YYYY-MM-DD
        assert len(data['ini_date']) == 10
        assert len(data['fin_date']) == 10
    
    def test_renovation_create_serializer_valid(self, minimal_renovation_data):
        """Test serializer de creació amb dades vàlides"""
        serializer = RenovationCreateSerializer(data=minimal_renovation_data)
        
        assert serializer.is_valid(), serializer.errors
    
    def test_renovation_create_serializer_invalid_dates(self):
        """Test serializer de creació amb dates invàlides"""
        today = date.today()
        data = {
            'refuge_id': 'test_refuge',
            'ini_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
            'fin_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'description': 'Test',
            'group_link': 'https://wa.me/test'
        }
        serializer = RenovationCreateSerializer(data=data)
        
        assert not serializer.is_valid()
    
    def test_renovation_create_serializer_past_date(self):
        """Test serializer de creació amb data passada"""
        yesterday = date.today() - timedelta(days=1)
        data = {
            'refuge_id': 'test_refuge',
            'ini_date': yesterday.strftime('%Y-%m-%d'),
            'fin_date': (yesterday + timedelta(days=4)).strftime('%Y-%m-%d'),
            'description': 'Test',
            'group_link': 'https://wa.me/test'
        }
        serializer = RenovationCreateSerializer(data=data)
        
        assert not serializer.is_valid()
    
    def test_renovation_create_serializer_invalid_url(self):
        """Test serializer de creació amb URL invàlida"""
        today = date.today()
        data = {
            'refuge_id': 'test_refuge',
            'ini_date': (today + timedelta(days=1)).strftime('%Y-%m-%d'),
            'fin_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
            'description': 'Test',
            'group_link': 'not_a_valid_url'
        }
        serializer = RenovationCreateSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'group_link' in serializer.errors
    
    def test_renovation_update_serializer_partial(self):
        """Test serializer d'actualització parcial"""
        data = {'description': 'Updated description'}
        serializer = RenovationUpdateSerializer(data=data)
        
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['description'] == 'Updated description'
    
    def test_renovation_update_serializer_all_fields(self):
        """Test serializer d'actualització amb tots els camps"""
        today = date.today()
        data = {
            'ini_date': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
            'fin_date': (today + timedelta(days=6)).strftime('%Y-%m-%d'),
            'description': 'Updated',
            'materials_needed': 'New materials',
            'group_link': 'https://t.me/updated'
        }
        serializer = RenovationUpdateSerializer(data=data)
        
        assert serializer.is_valid(), serializer.errors
