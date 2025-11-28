"""
Tests per a renovations: models, serializers, mappers, DAOs, controllers i views
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, date, timedelta
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from rest_framework import status as http_status

from api.models.renovation import Renovation
from api.serializers.renovation_serializer import (
    RenovationSerializer,
    RenovationCreateSerializer,
    RenovationUpdateSerializer,
    DateValidationMixin
)
from api.mappers.renovation_mapper import RenovationMapper
from api.daos.renovation_dao import RenovationDAO
from api.controllers.renovation_controller import RenovationController
from api.views.renovation_views import (
    RenovationListAPIView,
    RenovationAPIView,
    RenovationParticipantsAPIView,
    RenovationParticipantDetailAPIView
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
        """Test validació amb dates iguals"""
        from rest_framework import serializers
        today = date.today()
        same_date = today + timedelta(days=1)
        
        with pytest.raises(serializers.ValidationError):
            DateValidationMixin.validate_dates(same_date, same_date)
    
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


# ===== TEST DAO =====

@pytest.mark.django_db
class TestRenovationDAO:
    """Tests per al DAO de renovation"""
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_create_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test creació exitosa de renovation"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = 'new_renovation_id'
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        
        result = dao.create_renovation(renovation_data)
        
        assert result is not None
        assert result.creator_uid == renovation_data['creator_uid']
        mock_doc_ref.set.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_found(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovation per ID (trobada)"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_not_found(self, mock_cache, mock_firestore_service):
        """Test obtenció de renovation per ID (no trobada)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('nonexistent_id')
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_from_cache(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovation des de cache"""
        mock_cache.get.return_value = sample_renovation_data
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de totes les renovations actives"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test actualització exitosa de renovation"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.update_renovation('test_id', {'description': 'Updated'})
        
        assert result is True
        mock_doc_ref.update.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test actualització de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.update_renovation('nonexistent_id', {'description': 'Updated'})
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_success(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminació exitosa de renovation"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.delete_renovation('test_id')
        
        assert result is True
        mock_doc_ref.delete.assert_called_once()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_found(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test detecció de solapament (trobat)"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        # Dades que se solapen
        result = dao.check_overlapping_renovations(
            sample_renovation_data['refuge_id'],
            sample_renovation_data['ini_date'],
            sample_renovation_data['fin_date']
        )
        
        assert result is not None
        assert result.id == sample_renovation_data['id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_not_found(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test detecció de solapament (no trobat)"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.check_overlapping_renovations(
            'test_refuge',
            (date.today() + timedelta(days=10)).isoformat(),
            (date.today() + timedelta(days=15)).isoformat()
        )
        
        assert result is None
    
    @patch('api.daos.user_dao.UserDAO')
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_success(self, mock_cache, mock_firestore_service, mock_user_dao_class, sample_renovation_data):
        """Test afegir participant amb èxit"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Mock UserDAO
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.increment_renovated_refuges.return_value = True
        
        dao = RenovationDAO()
        result = dao.add_participant('test_id', 'new_participant')
        
        assert result is True
        mock_user_dao.increment_renovated_refuges.assert_called_once_with('new_participant')
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_already_exists(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test afegir participant que ja existeix"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.add_participant('test_id', 'participant1')  # Ja existeix
        
        assert result is False
    
    @patch('api.daos.user_dao.UserDAO')
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_success(self, mock_cache, mock_firestore_service, mock_user_dao_class, sample_renovation_data):
        """Test eliminar participant amb èxit"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Mock UserDAO
        mock_user_dao = mock_user_dao_class.return_value
        mock_user_dao.decrement_renovated_refuges.return_value = True
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'participant1')
        
        assert result is True
        mock_user_dao.decrement_renovated_refuges.assert_called_once_with('participant1')
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_not_exists(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test eliminar participant que no existeix"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'nonexistent_participant')
        
        assert result is False
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS DEL DAO =====
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_create_renovation_exception(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test excepció durant la creació de renovation"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Firestore connection error")
        
        dao = RenovationDAO()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        
        result = dao.create_renovation(renovation_data)
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovation_by_id_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció per ID"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Database error")
        
        dao = RenovationDAO()
        result = dao.get_renovation_by_id('test_id')
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_from_cache(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations des de cache"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = [sample_renovation_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert isinstance(result, list)
        assert len(result) == 1
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_all_renovations_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció de totes les renovations"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.get_all_renovations()
        
        assert result == []
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_update_renovation_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'actualització"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Update error")
        
        dao = RenovationDAO()
        result = dao.update_renovation('test_id', {'description': 'Updated'})
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test eliminació de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.delete_renovation('nonexistent_id')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_delete_renovation_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Delete error")
        
        dao = RenovationDAO()
        result = dao.delete_renovation('test_id')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_all(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de totes les renovations d'un refugi"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=False)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].refuge_id == sample_renovation_data['refuge_id']
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_get_renovations_by_refuge_active_only(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció només de renovations actives d'un refugi"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id', active_only=True)
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_from_cache(self, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test obtenció de renovations per refugi des de cache"""
        mock_cache.get.return_value = [sample_renovation_data]
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert isinstance(result, list)
        assert len(result) == 1
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_empty(self, mock_cache, mock_firestore_service):
        """Test obtenció de renovations per refugi sense resultats"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_query = MagicMock()
        mock_query.stream.return_value = []
        
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_get_renovations_by_refuge_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'obtenció de renovations per refugi"""
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.get_renovations_by_refuge('test_refuge_id')
        
        assert result == []
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_with_exclude(self, mock_get_today, mock_cache, mock_firestore_service, sample_renovation_data):
        """Test detecció de solapament excloent una renovation"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = sample_renovation_data['id']
        mock_doc.to_dict.return_value = sample_renovation_data
        
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.where.return_value.order_by.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        # Excloure la renovation que coincideix
        result = dao.check_overlapping_renovations(
            sample_renovation_data['refuge_id'],
            sample_renovation_data['ini_date'],
            sample_renovation_data['fin_date'],
            exclude_id=sample_renovation_data['id']
        )
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.daos.renovation_dao.get_madrid_today')
    def test_check_overlapping_renovations_exception(self, mock_get_today, mock_cache, mock_firestore_service):
        """Test excepció durant la comprovació de solapaments"""
        mock_today = date.today()
        mock_get_today.return_value = mock_today
        
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Query error")
        
        dao = RenovationDAO()
        result = dao.check_overlapping_renovations(
            'test_refuge',
            (date.today() + timedelta(days=1)).isoformat(),
            (date.today() + timedelta(days=5)).isoformat()
        )
        
        assert result is None
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test afegir participant a renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.add_participant('nonexistent_id', 'participant_uid')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_add_participant_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'afegició de participant"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Add error")
        
        dao = RenovationDAO()
        result = dao.add_participant('test_id', 'participant_uid')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_renovation_not_found(self, mock_cache, mock_firestore_service):
        """Test eliminar participant de renovation no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = RenovationDAO()
        result = dao.remove_participant('nonexistent_id', 'participant_uid')
        
        assert result is False
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    def test_remove_participant_exception(self, mock_cache, mock_firestore_service):
        """Test excepció durant l'eliminació de participant"""
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.side_effect = Exception("Remove error")
        
        dao = RenovationDAO()
        result = dao.remove_participant('test_id', 'participant_uid')
        
        assert result is False


# ===== TEST CONTROLLER =====

@pytest.mark.django_db
class TestRenovationController:
    """Tests per al controller de renovation"""
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_success(self, mock_dao_class, sample_renovation_data, sample_renovation):
        """Test creació exitosa de renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = None
        mock_dao.create_renovation.return_value = sample_renovation
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is True
        assert renovation is not None
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_overlap(self, mock_dao_class, sample_renovation_data, sample_renovation):
        """Test creació amb solapament"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = sample_renovation
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation == sample_renovation
        assert 'solapa' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_success(self, mock_dao_class, sample_renovation):
        """Test obtenció exitosa de renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('test_id')
        
        assert success is True
        assert renovation == sample_renovation
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_not_found(self, mock_dao_class):
        """Test obtenció de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('nonexistent_id')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_all_renovations(self, mock_dao_class, sample_renovation):
        """Test obtenció de totes les renovations"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_all_renovations.return_value = [sample_renovation]
        
        controller = RenovationController()
        success, renovations, error = controller.get_all_renovations()
        
        assert success is True
        assert len(renovations) == 1
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_success(self, mock_dao_class, sample_renovation):
        """Test actualització exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.update_renovation.return_value = True
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            sample_renovation.creator_uid
        )
        
        assert success is True
        assert renovation is not None
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_not_creator(self, mock_dao_class, sample_renovation):
        """Test actualització per no creador"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            'other_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_invalid_dates(self, mock_dao_class, sample_renovation):
        """Test actualització amb dates invàlides"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        today = date.today()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {
                'ini_date': (today + timedelta(days=5)).isoformat(),
                'fin_date': (today + timedelta(days=1)).isoformat()
            },
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert 'anterior' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_success(self, mock_dao_class, sample_renovation):
        """Test eliminació exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.delete_renovation.return_value = True
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', sample_renovation.creator_uid)
        
        assert success is True
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_not_creator(self, mock_dao_class, sample_renovation):
        """Test eliminació per no creador"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', 'other_user')
        
        assert success is False
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_success(self, mock_dao_class, sample_renovation):
        """Test afegir participant amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = True
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'new_participant')
        
        assert success is True
        assert renovation is not None
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_is_creator(self, mock_dao_class, sample_renovation):
        """Test afegir creador com a participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', sample_renovation.creator_uid)
        
        assert success is False
        assert 'creador' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_success(self, mock_dao_class, sample_renovation):
        """Test eliminar participant amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.remove_participant.return_value = True
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is True
        assert renovation is not None
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_no_permission(self, mock_dao_class, sample_renovation):
        """Test eliminar participant sense permís"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'other_user')
        
        assert success is False
        assert 'permís' in error.lower()
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_dao_returns_none(self, mock_dao_class, sample_renovation_data):
        """Test quan el DAO retorna None en la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = None
        mock_dao.create_renovation.return_value = None  # DAO retorna None
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation is None
        assert 'Error creant renovation a la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_create_renovation_exception(self, mock_dao_class, sample_renovation_data):
        """Test excepció durant la creació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.side_effect = Exception("Database error")
        
        controller = RenovationController()
        renovation_data = sample_renovation_data.copy()
        renovation_data.pop('id')
        renovation_data.pop('creator_uid')
        renovation_data.pop('participants_uids')
        
        success, renovation, error = controller.create_renovation(renovation_data, 'test_creator')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Database error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovation_by_id_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció per ID"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Connection error")
        
        controller = RenovationController()
        success, renovation, error = controller.get_renovation_by_id('test_id')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Connection error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_all_renovations_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció de totes les renovations"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_all_renovations.side_effect = Exception("Firestore error")
        
        controller = RenovationController()
        success, renovations, error = controller.get_all_renovations()
        
        assert success is False
        assert renovations == []
        assert 'Error intern' in error
        assert 'Firestore error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_not_found(self, mock_dao_class):
        """Test actualització de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'nonexistent_id',
            {'description': 'Updated'},
            'test_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_with_dates_overlap(self, mock_dao_class, sample_renovation):
        """Test actualització amb dates que es solapen amb altra renovation"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        
        # Crear una altra renovation que es solapa
        overlapping_renovation = Renovation(
            id='other_renovation_id',
            creator_uid='other_user',
            refuge_id=sample_renovation.refuge_id,
            ini_date=sample_renovation.ini_date,
            fin_date=sample_renovation.fin_date,
            description='Overlapping renovation',
            group_link='https://t.me/other'
        )
        mock_dao.check_overlapping_renovations.return_value = overlapping_renovation
        
        controller = RenovationController()
        today = date.today()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {
                'ini_date': (today + timedelta(days=2)).isoformat(),
                'fin_date': (today + timedelta(days=6)).isoformat()
            },
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert renovation == overlapping_renovation
        assert 'solapa' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False en l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.update_renovation.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            sample_renovation.creator_uid
        )
        
        assert success is False
        assert renovation is None
        assert 'Error actualitzant renovation a la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_update_renovation_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'actualització"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Update error")
        
        controller = RenovationController()
        success, renovation, error = controller.update_renovation(
            'test_id',
            {'description': 'Updated'},
            'test_user'
        )
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Update error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_not_found(self, mock_dao_class):
        """Test eliminació de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, error = controller.delete_renovation('nonexistent_id', 'test_user')
        
        assert success is False
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False en l'eliminació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.delete_renovation.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', sample_renovation.creator_uid)
        
        assert success is False
        assert 'Error eliminant renovation de la base de dades' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_delete_renovation_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'eliminació"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Delete error")
        
        controller = RenovationController()
        success, error = controller.delete_renovation('test_id', 'test_user')
        
        assert success is False
        assert 'Error intern' in error
        assert 'Delete error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_renovation_not_found(self, mock_dao_class):
        """Test afegir participant a renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('nonexistent_id', 'participant_uid')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False (participant ja existeix o error)"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'new_participant')
        
        assert success is False
        assert renovation is None
        assert 'Error afegint participant o ja és participant' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_add_participant_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'afegició de participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Add participant error")
        
        controller = RenovationController()
        success, renovation, error = controller.add_participant('test_id', 'participant_uid')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Add participant error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_renovation_not_found(self, mock_dao_class):
        """Test eliminar participant de renovation no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = None
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('nonexistent_id', 'participant_uid', 'requester_uid')
        
        assert success is False
        assert renovation is None
        assert 'no trobada' in error.lower()
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_dao_returns_false(self, mock_dao_class, sample_renovation):
        """Test quan el DAO retorna False (participant no existeix o error)"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.remove_participant.return_value = False  # DAO retorna False
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is False
        assert renovation is None
        assert 'Error eliminant participant o no és participant' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_remove_participant_exception(self, mock_dao_class, sample_renovation):
        """Test excepció durant l'eliminació de participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.side_effect = Exception("Remove participant error")
        
        controller = RenovationController()
        success, renovation, error = controller.remove_participant('test_id', 'participant1', 'participant1')
        
        assert success is False
        assert renovation is None
        assert 'Error intern' in error
        assert 'Remove participant error' in error
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_success(self, mock_dao_class, sample_renovation):
        """Test obtenció de renovations per refugi amb èxit"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.return_value = [sample_renovation]
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is True
        assert len(renovations) == 1
        assert renovations[0] == sample_renovation
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_empty(self, mock_dao_class):
        """Test obtenció de renovations per refugi sense resultats"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.return_value = []
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is True
        assert len(renovations) == 0
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_get_renovations_by_refuge_exception(self, mock_dao_class):
        """Test excepció durant l'obtenció de renovations per refugi"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovations_by_refuge.side_effect = Exception("Query error")
        
        controller = RenovationController()
        success, renovations, error = controller.get_renovations_by_refuge('test_refuge_id')
        
        assert success is False
        assert renovations == []
        assert 'Error intern' in error
        assert 'Query error' in error


# ===== TEST VIEWS =====

@pytest.mark.django_db
class TestRenovationViews:
    """Tests per a les views de renovation"""
    
    def _get_authenticated_request(self, method, path, data=None, query_params=None, user_uid='test_user'):
        """Helper per crear requests autenticades"""
        factory = APIRequestFactory()
        if method == 'GET':
            request = factory.get(path, query_params or {})
        elif method == 'POST':
            request = factory.post(path, data or {}, format='json')
        elif method == 'PATCH':
            request = factory.patch(path, data or {}, format='json')
        elif method == 'DELETE':
            request = factory.delete(path)
        else:
            raise ValueError(f"Method {method} not supported")
        
        request.user_uid = user_uid
        
        # Per PATCH i DELETE, també podem passar query_params manualment
        if query_params and method in ['PATCH', 'DELETE']:
            from django.http import QueryDict
            q = QueryDict('', mutable=True)
            q.update(query_params)
            request.GET = q
        
        return request
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_success(self, mock_controller_class, sample_renovation):
        """Test GET /renovations/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.return_value = (True, [sample_renovation], None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        # Forçar autenticació
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
        assert len(response.data) == 1
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_success(self, mock_controller_class, sample_renovation, minimal_renovation_data):
        """Test POST /renovations/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_201_CREATED
        assert 'id' in response.data
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_invalid_data(self, mock_controller_class):
        """Test POST /renovations/ amb dades invàlides"""
        request = self._get_authenticated_request('POST', '/api/renovations/', {'invalid': 'data'})
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_no_user_uid(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ sense user_uid"""
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data, user_uid=None)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_overlap(self, mock_controller_class, sample_renovation, minimal_renovation_data):
        """Test POST /renovations/ amb solapament"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (
            False,
            sample_renovation,
            'Hi ha una altra renovation que es solapa temporalment'
        )
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_409_CONFLICT
        assert 'overlapping_renovation' in response.data
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_success(self, mock_controller_class, sample_renovation):
        """Test GET /renovations/?id=xxx"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/', query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
        assert response.data['id'] == sample_renovation.id
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_not_found(self, mock_controller_class):
        """Test GET /renovations/?id=xxx (no trobada)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('GET', '/api/renovations/', query_params={'id': 'nonexistent'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_success(self, mock_controller_class, sample_renovation):
        """Test PATCH /renovations/?id=xxx"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/',
            {'description': 'Updated'},
            query_params={'id': 'test_id'},
            user_uid=sample_renovation.creator_uid
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_forbidden(self, mock_controller_class):
        """Test PATCH /renovations/?id=xxx (no creador)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (
            False,
            None,
            'Només el creador pot editar la renovation'
        )
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/',
            {'description': 'Updated'},
            query_params={'id': 'test_id'},
            user_uid='other_user'
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_no_user_uid(self, mock_controller_class):
        """Test PATCH /renovations/ sense user_uid"""
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/',
            {'description': 'Updated'},
            query_params={'id': 'test_id'},
            user_uid=None
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_controller_error(self, mock_controller_class):
        """Test PATCH amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request(
            'PATCH',
            '/api/renovations/',
            {'description': 'Updated'},
            query_params={'id': 'test_id'}
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_success(self, mock_controller_class, sample_renovation):
        """Test DELETE /renovations/?id=xxx"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (True, None)
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/',
            query_params={'id': 'test_id'},
            user_uid=sample_renovation.creator_uid
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_204_NO_CONTENT
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_forbidden(self, mock_controller_class):
        """Test DELETE /renovations/?id=xxx (no creador)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (
            False,
            'Només el creador pot eliminar la renovation'
        )
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/',
            query_params={'id': 'test_id'},
            user_uid='other_user'
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_no_user_uid(self, mock_controller_class):
        """Test DELETE /renovations/ sense user_uid"""
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/',
            query_params={'id': 'test_id'},
            user_uid=None
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_controller_error(self, mock_controller_class):
        """Test DELETE amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (False, 'Controller error')
        
        request = self._get_authenticated_request(
            'DELETE',
            '/api/renovations/',
            query_params={'id': 'test_id'}
        )
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # ===== NOUS TESTS PER COBRIR EXCEPCIONS I CASOS NO COBERTS =====
    
    @patch('api.views.renovation_views.RenovationController')
    @patch('api.permissions.IsCreator.has_permission')
    def test_get_renovation_real_permissions(self, mock_has_perm, mock_controller_class, sample_renovation):
        """Test GET /renovations/ amb permisos reals per cobrir get_permissions"""
        mock_has_perm.return_value = True
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('GET', '/api/renovations/', query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        # No forcem get_permissions, deixem que s'executi
        response = view(request)
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_controller_error(self, mock_controller_class):
        """Test GET /renovations/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.return_value = (False, [], 'Database error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_all_renovations_exception(self, mock_controller_class):
        """Test GET /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_all_renovations.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/')
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_controller_error(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.return_value = (False, None, 'Error creating renovation')
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_create_renovation_exception(self, mock_controller_class, minimal_renovation_data):
        """Test POST /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/', minimal_renovation_data)
        
        view = RenovationListAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_missing_id(self, mock_controller_class):
        """Test GET /renovations/ sense ID"""
        request = self._get_authenticated_request('GET', '/api/renovations/', query_params={})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_get_renovation_exception(self, mock_controller_class):
        """Test GET /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_renovation_by_id.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('GET', '/api/renovations/', query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_missing_id(self, mock_controller_class):
        """Test PATCH /renovations/ sense ID"""
        request = self._get_authenticated_request('PATCH', '/api/renovations/', {'description': 'Updated'}, query_params={})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_invalid_data(self, mock_controller_class):
        """Test PATCH /renovations/ amb dades invàlides"""
        request = self._get_authenticated_request('PATCH', '/api/renovations/', {'ini_date': 'invalid'}, query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_not_found(self, mock_controller_class):
        """Test PATCH /renovations/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/', {'description': 'Updated'}, query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_overlap(self, mock_controller_class, sample_renovation):
        """Test PATCH /renovations/ amb solapament"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.return_value = (False, sample_renovation, 'Solapament temporal')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/', {'description': 'Updated'}, query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_409_CONFLICT
    
    @patch('api.views.renovation_views.RenovationController')
    def test_update_renovation_exception(self, mock_controller_class):
        """Test PATCH /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('PATCH', '/api/renovations/', {'description': 'Updated'}, query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_missing_id(self, mock_controller_class):
        """Test DELETE /renovations/ sense ID"""
        request = self._get_authenticated_request('DELETE', '/api/renovations/', query_params={})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_not_found(self, mock_controller_class):
        """Test DELETE /renovations/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.return_value = (False, 'Renovation no trobada')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/', query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_delete_renovation_exception(self, mock_controller_class):
        """Test DELETE /renovations/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_renovation.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/', query_params={'id': 'test_id'})
        
        view = RenovationAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.get_permissions = lambda self: []
        response = view(request)
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_success(self, mock_controller_class, sample_renovation):
        """Test POST /renovations/{id}/participants/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_not_found(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_is_creator(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ quan l'usuari és el creador"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'El creador no pot unir-se')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_400_BAD_REQUEST
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_no_user_uid(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ sense user_uid"""
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/', user_uid=None)
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_controller_error(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_add_participant_exception(self, mock_controller_class):
        """Test POST /renovations/{id}/participants/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.add_participant.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('POST', '/api/renovations/test_id/participants/')
        
        view = RenovationParticipantsAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_success(self, mock_controller_class, sample_renovation):
        """Test DELETE /renovations/{id}/participants/{uid}/"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (True, sample_renovation, None)
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_200_OK
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_not_found(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ no trobada"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'Renovation no trobada')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_404_NOT_FOUND
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_forbidden(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ sense permís"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'No tens permís')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_403_FORBIDDEN
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_no_user_uid(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ sense user_uid"""
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/', user_uid=None)
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_401_UNAUTHORIZED
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_controller_error(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ amb error del controller"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.return_value = (False, None, 'Controller error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('api.views.renovation_views.RenovationController')
    def test_remove_participant_exception(self, mock_controller_class):
        """Test DELETE /renovations/{id}/participants/{uid}/ amb excepció"""
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_participant.side_effect = Exception('Unexpected error')
        
        request = self._get_authenticated_request('DELETE', '/api/renovations/test_id/participants/participant1/')
        
        view = RenovationParticipantDetailAPIView.as_view()
        view.cls.authentication_classes = []
        view.cls.permission_classes = []
        response = view(request, id='test_id', uid='participant1')
        
        assert response.status_code == http_status.HTTP_500_INTERNAL_SERVER_ERROR


# ===== TEST INTEGRACIÓ =====

@pytest.mark.django_db
class TestRenovationIntegration:
    """Tests d'integració per al flux complet de renovations"""
    
    @patch('api.daos.renovation_dao.FirestoreService')
    @patch('api.daos.renovation_dao.cache_service')
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_full_renovation_creation_flow(self, mock_dao_class, mock_cache, mock_firestore_service, minimal_renovation_data):
        """Test flux complet de creació de renovation"""
        # Mock DAO
        mock_dao = mock_dao_class.return_value
        mock_dao.check_overlapping_renovations.return_value = None
        
        today = date.today()
        renovation_data = {
            'id': 'new_id',
            'creator_uid': 'test_user',
            'refuge_id': minimal_renovation_data['refuge_id'],
            'ini_date': (today + timedelta(days=1)).isoformat(),
            'fin_date': (today + timedelta(days=5)).isoformat(),
            'description': minimal_renovation_data['description'],
            'materials_needed': None,
            'group_link': minimal_renovation_data['group_link'],
            'participants_uids': []
        }
        
        mock_renovation = Renovation.from_dict(renovation_data)
        mock_dao.create_renovation.return_value = mock_renovation
        
        # Controller
        controller = RenovationController()
        success, renovation, error = controller.create_renovation(minimal_renovation_data, 'test_user')
        
        assert success is True
        assert renovation is not None
        assert renovation.creator_uid == 'test_user'
        assert error is None
    
    @patch('api.controllers.renovation_controller.RenovationDAO')
    def test_full_participant_flow(self, mock_dao_class, sample_renovation):
        """Test flux complet d'afegir i eliminar participant"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_renovation_by_id.return_value = sample_renovation
        mock_dao.add_participant.return_value = True
        mock_dao.remove_participant.return_value = True
        
        controller = RenovationController()
        
        # Afegir participant
        success, renovation, error = controller.add_participant('test_id', 'new_participant')
        assert success is True
        
        # Eliminar participant
        success, renovation, error = controller.remove_participant('test_id', 'new_participant', 'new_participant')
        assert success is True
