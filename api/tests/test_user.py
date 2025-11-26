"""
Tests exhaustius per al mòdul User
Cobreix: Views, Serializers, Controllers, DAOs, Mappers i Models
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from zoneinfo import ZoneInfo
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import ValidationError

from api.models.user import User
from api.serializers.user_serializer import (
    UserSerializer, 
    UserCreateSerializer, 
    UserUpdateSerializer,
    UserValidatorMixin
)
from api.controllers.user_controller import UserController
from api.daos.user_dao import UserDAO
from api.views.user_views import UsersCollectionAPIView, UserDetailAPIView


# ==================== TESTS DE MODELS ====================

@pytest.mark.models
class TestUserModel:
    """Tests per al model User"""
    
    def test_user_creation_valid(self, sample_user_data):
        """Test creació d'usuari amb dades vàlides"""
        user = User.from_dict(sample_user_data)
        
        assert user.uid == sample_user_data['uid']
        assert user.email == sample_user_data['email']
        assert user.username == sample_user_data['username']
        assert user.language == sample_user_data['language']
    
    def test_user_creation_missing_uid(self):
        """Test creació d'usuari sense UID (ha de fallar)"""
        data = {'uid': '', 'email': 'test@example.com', 'username': 'test'}
        
        with pytest.raises(ValueError, match="UID és requerit"):
            User(**data)
    
    def test_user_creation_missing_email(self):
        """Test creació d'usuari sense email (ha de fallar)"""
        data = {'uid': 'test_uid', 'email': '', 'username': 'test'}
        
        with pytest.raises(ValueError, match="Email és requerit"):
            User(**data)
    
    def test_user_creation_invalid_email_format(self):
        """Test creació d'usuari amb email sense @"""
        data = {'uid': 'test_uid', 'email': 'invalid_email', 'username': 'test'}
        
        with pytest.raises(ValueError, match="Format d'email invàlid"):
            User(**data)
    
    def test_user_to_dict(self, sample_user):
        """Test conversió d'usuari a diccionari"""
        user_dict = sample_user.to_dict()
        
        assert isinstance(user_dict, dict)
        assert user_dict['uid'] == sample_user.uid
        assert user_dict['email'] == sample_user.email
        assert user_dict['username'] == sample_user.username
        assert 'favourite_refuges' in user_dict
    
    def test_user_from_dict(self, sample_user_data):
        """Test creació d'usuari des de diccionari"""
        user = User.from_dict(sample_user_data)
        
        assert isinstance(user, User)
        assert user.uid == sample_user_data['uid']
        assert user.email == sample_user_data['email']
    
    def test_user_str_representation(self, sample_user):
        """Test representació textual de l'usuari"""
        user_str = str(sample_user)
        
        assert 'User' in user_str
        assert sample_user.uid in user_str
        assert sample_user.email in user_str
    
    def test_user_default_values(self):
        """Test valors per defecte de l'usuari"""
        user = User(uid='test', username='test', email='test@example.com')
        
        assert user.language == 'ca'
        assert user.num_uploaded_photos == 0
        assert user.num_shared_experiences == 0
        assert user.num_renovated_refuges == 0
        assert user.favourite_refuges is None
    
    @pytest.mark.parametrize("email", [
        'test@example.com',
        'user.name@domain.co.uk',
        'first.last+tag@example.com'
    ])
    def test_user_valid_emails(self, email):
        """Test usuari amb diversos formats d'email vàlids"""
        user = User(uid='test', username='test', email=email)
        assert user.email == email
    
    @pytest.mark.parametrize("language", ['ca', 'es', 'en', 'fr'])
    def test_user_valid_languages(self, language):
        """Test usuari amb diferents idiomes vàlids"""
        user = User(uid='test', username='test', email='test@example.com', language=language)
        assert user.language == language


# ==================== TESTS DE SERIALIZERS ====================

@pytest.mark.serializers
class TestUserSerializers:
    """Tests per als serializers d'usuaris"""
    
    def test_user_serializer_valid_data(self, sample_user_data):
        """Test serialització amb dades vàlides"""
        serializer = UserSerializer(data=sample_user_data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['email'] == sample_user_data['email'].lower()
    
    def test_user_serializer_invalid_email(self):
        """Test serialització amb email invàlid"""
        data = {
            'uid': 'test_uid',
            'username': 'test',
            'email': 'invalid_email',
            'language': 'ca'
        }
        serializer = UserSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'email' in serializer.errors
    
    def test_user_serializer_short_username(self):
        """Test serialització amb username massa curt"""
        data = {
            'uid': 'test_uid',
            'username': 'a',  # Només 1 caràcter
            'email': 'test@example.com',
            'language': 'ca'
        }
        serializer = UserSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'username' in serializer.errors
    
    def test_user_serializer_invalid_language(self):
        """Test serialització amb language invàlid"""
        data = {
            'uid': 'test_uid',
            'username': 'test',
            'email': 'test@example.com',
            'language': 'invalid_lang'
        }
        serializer = UserSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'language' in serializer.errors
    
    def test_user_create_serializer_valid(self):
        """Test UserCreateSerializer amb dades vàlides"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'language': 'ca'
        }
        serializer = UserCreateSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['email'] == 'newuser@example.com'
    
    def test_user_create_serializer_email_normalization(self):
        """Test normalització d'email (lowercase i trim)"""
        data = {
            'username': 'test',
            'email': '  TEST@EXAMPLE.COM  ',
            'language': 'ca'
        }
        serializer = UserCreateSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['email'] == 'test@example.com'
    
    def test_user_update_serializer_partial_update(self):
        """Test UserUpdateSerializer amb actualització parcial"""
        data = {'username': 'updated_username'}
        serializer = UserUpdateSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['username'] == 'updated_username'
    
    def test_user_update_serializer_empty_data(self):
        """Test UserUpdateSerializer sense dades (els defaults s'apliquen)"""
        data = {}
        serializer = UserUpdateSerializer(data=data)
        
        # El serializer és vàlid però el camp 'language' té default='ca'
        assert serializer.is_valid()
        # El validated_data pot tenir el default d'language
        assert 'language' in serializer.validated_data or len(serializer.validated_data) == 0
    
    def test_user_update_serializer_multiple_fields(self):
        """Test actualització de múltiples camps"""
        data = {
            'username': 'updated',
            'email': 'updated@example.com',
            'language': 'es'
        }
        serializer = UserUpdateSerializer(data=data)
        
        assert serializer.is_valid()
        assert len(serializer.validated_data) == 3
    
    def test_validator_mixin_email_field(self):
        """Test validador d'email del mixin"""
        # Email vàlid
        email = UserValidatorMixin.validate_email_field('test@example.com', required=True)
        assert email == 'test@example.com'
        
        # Email buit amb required=True
        with pytest.raises(ValidationError):
            UserValidatorMixin.validate_email_field('', required=True)
    
    def test_validator_mixin_username_field(self):
        """Test validador de username del mixin"""
        # Username vàlid
        username = UserValidatorMixin.validate_username_field('testuser', required=False)
        assert username == 'testuser'
        
        # Username massa curt
        with pytest.raises(ValidationError):
            UserValidatorMixin.validate_username_field('a', required=False)
    
    def test_validator_mixin_idioma_field(self):
        """Test validador d'language del mixin"""
        # language vàlid
        language = UserValidatorMixin.validate_language_field('ca', required=False)
        assert language == 'ca'
        
        # language invàlid
        with pytest.raises(ValidationError):
            UserValidatorMixin.validate_language_field('invalid', required=False)
    
    @pytest.mark.parametrize("email,expected", [
        ('TEST@EXAMPLE.COM', 'test@example.com'),
        ('  test@example.com  ', 'test@example.com'),
        ('Test@Example.Com', 'test@example.com')
    ])
    def test_email_normalization_variations(self, email, expected):
        """Test diverses variacions de normalització d'email"""
        result = UserValidatorMixin.validate_email_field(email, required=True)
        assert result == expected


# ==================== TESTS DE MAPPERS ====================

@pytest.mark.mappers
class TestUserMapper:
    """Tests per al UserMapper"""
    
    def test_firebase_to_model(self, sample_user_data, user_mapper):
        """Test conversió de Firebase a model"""
        user = user_mapper.firebase_to_model(sample_user_data)
        
        assert isinstance(user, User)
        assert user.uid == sample_user_data['uid']
        assert user.email == sample_user_data['email']
    
    def test_model_to_firebase(self, sample_user, user_mapper):
        """Test conversió de model a Firebase"""
        firebase_data = user_mapper.model_to_firebase(sample_user)
        
        assert isinstance(firebase_data, dict)
        assert firebase_data['uid'] == sample_user.uid
        assert firebase_data['email'] == sample_user.email
    
    def test_validate_firebase_data_valid(self, sample_user_data, user_mapper):
        """Test validació de dades vàlides de Firebase"""
        is_valid, error = user_mapper.validate_firebase_data(sample_user_data)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_firebase_data_missing_uid(self, user_mapper):
        """Test validació sense UID"""
        data = {'email': 'test@example.com'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'uid' in error
    
    def test_validate_firebase_data_missing_email(self, user_mapper):
        """Test validació sense email"""
        data = {'uid': 'test_uid'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'email' in error
    
    def test_validate_firebase_data_invalid_email(self, user_mapper):
        """Test validació amb email invàlid"""
        data = {'uid': 'test_uid', 'email': 'invalid_email'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'email' in error.lower()
    
    def test_validate_firebase_data_invalid_language(self, user_mapper):
        """Test validació amb language invàlid"""
        data = {'uid': 'test_uid', 'email': 'test@example.com', 'language': 'invalid'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'idioma' in error.lower()  # Error message is still in Catalan
    
    def test_clean_firebase_data(self, user_mapper):
        """Test neteja de dades de Firebase"""
        data = {
            'uid': 'test_uid',
            'email': '  TEST@EXAMPLE.COM  ',
            'username': '  testuser  ',
            'language': '  CA  '
        }
        cleaned = user_mapper.clean_firebase_data(data)
        
        assert cleaned['email'] == 'test@example.com'
        assert cleaned['username'] == 'testuser'
        assert cleaned['language'] == 'ca'
    
    def test_clean_firebase_data_preserves_other_fields(self, sample_user_data, user_mapper):
        """Test que la neteja preserva altres camps"""
        cleaned = user_mapper.clean_firebase_data(sample_user_data)
        
        assert cleaned['uid'] == sample_user_data['uid']
        assert cleaned['favourite_refuges'] == sample_user_data['favourite_refuges']


# ==================== TESTS DE DAOs ====================

@pytest.mark.daos
class TestUserDAO:
    """Tests per al UserDAO"""
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_create_user_success(self, mock_cache, mock_firestore_service, sample_user_data):
        """Test creació d'usuari exitosa"""
        # Configurar mocks
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_collection = MagicMock()
        mock_db.collection.return_value = mock_collection
        
        mock_doc_ref = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        
        # Crear DAO i executar
        dao = UserDAO()
        user = dao.create_user(sample_user_data, 'test_uid')
        
        # Verificacions
        assert user is not None
        assert user.uid == sample_user_data['uid']
        assert user.email == sample_user_data['email']
        mock_db.collection.assert_called_once_with('users')
        mock_collection.document.assert_called_once_with('test_uid')
        mock_doc_ref.set.assert_called_once_with(sample_user_data)
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_uid_found(self, mock_firestore_service, mock_cache, sample_user_data):
        """Test obtenció d'usuari per UID (trobat)"""
        # Cache miss
        mock_cache.get.return_value = None
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        
        # Configurar Firestore mock
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.id = 'test_uid'
        mock_doc_snapshot.to_dict.return_value = sample_user_data
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        # Executar
        dao = UserDAO()
        result = dao.get_user_by_uid('test_uid')
        
        # Verificacions
        assert result is not None
        assert result.uid == 'test_uid'
        assert result.email == sample_user_data['email']
        mock_cache.set.assert_called_once()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_uid_not_found(self, mock_cache, mock_firestore_service):
        """Test obtenció d'usuari per UID (no trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_user_by_uid('nonexistent_uid')
        
        assert result is None
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_get_user_by_uid_from_cache(self, mock_firestore_service, mock_cache, sample_user_data):
        """Test obtenció d'usuari des de cache"""
        # Cache hit
        mock_cache.get.return_value = sample_user_data
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        dao = UserDAO()
        result = dao.get_user_by_uid('test_uid')
        
        assert result is not None
        assert result.uid == sample_user_data['uid']
        assert result.email == sample_user_data['email']
        # No hauria de cridar Firestore
        mock_firestore_service.return_value.get_db.assert_not_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_get_user_by_email_found(self, mock_cache, mock_firestore_service, sample_user_data):
        """Test obtenció d'usuari per email (trobat)"""
        mock_cache.get.return_value = None
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.id = 'test_uid'
        mock_doc.to_dict.return_value = sample_user_data
        
        mock_query = MagicMock()
        mock_query.get.return_value = [mock_doc]
        
        mock_collection = MagicMock()
        mock_collection.where.return_value.limit.return_value = mock_query
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        result = dao.get_user_by_email('test@example.com')
        
        assert result is not None
        assert result.uid == 'test_uid'
        assert result.email == sample_user_data['email']
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_update_user_success(self, mock_firestore_service, mock_cache):
        """Test actualització d'usuari exitosa"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        update_data = {'username': 'updated_username'}
        success = dao.update_user('test_uid', update_data)
        
        assert success is True
        mock_doc_ref.update.assert_called_once_with(update_data)
        mock_cache.delete.assert_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_update_user_not_found(self, mock_cache, mock_firestore_service):
        """Test actualització d'usuari no existent"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success = dao.update_user('nonexistent_uid', {'username': 'test'})
        
        assert success is False
        mock_doc_ref.update.assert_not_called()
    
    @patch('api.daos.user_dao.cache_service')
    @patch('api.daos.user_dao.FirestoreService')
    def test_delete_user_success(self, mock_firestore_service, mock_cache):
        """Test eliminació d'usuari exitosa"""
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        success = dao.delete_user('test_uid')
        
        assert success is True
        mock_doc_ref.delete.assert_called_once()
        mock_cache.delete.assert_called()
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_true(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència d'usuari (existeix)"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        exists = dao.user_exists('test_uid')
        
        assert exists is True
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_user_exists_false(self, mock_cache, mock_firestore_service):
        """Test comprovació d'existència d'usuari (no existeix)"""
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot
        
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection
        
        dao = UserDAO()
        exists = dao.user_exists('nonexistent_uid')
        
        assert exists is False


# ==================== TESTS DE CONTROLLERS ====================

@pytest.mark.controllers
class TestUserController:
    """Tests per al UserController"""
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_success(self, mock_dao_class, sample_user_data, sample_user):
        """Test creació d'usuari exitosa"""
        # Configurar mocks
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None  # No existeix
        mock_dao.get_user_by_email.return_value = None  # Email no en ús
        mock_dao.create_user.return_value = sample_user
        
        # Executar
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        # Verificacions
        assert success is True
        assert user is not None
        assert error is None
        mock_dao.create_user.assert_called_once()
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_duplicate_uid(self, mock_dao_class, sample_user_data):
        """Test creació d'usuari amb UID duplicat"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = sample_user_data  # Ja existeix
        
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        assert success is False
        assert user is None
        assert 'ja existeix' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_create_user_duplicate_email(self, mock_dao_class, sample_user_data):
        """Test creació d'usuari amb email duplicat"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        mock_dao.get_user_by_email.return_value = sample_user_data  # Email en ús
        
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        assert success is False
        assert user is None
        assert 'ja està en ús' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_success(self, mock_dao_class, sample_user):
        """Test obtenció d'usuari per UID exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = sample_user
        
        controller = UserController()
        success, user, error = controller.get_user_by_uid('test_uid')
        
        assert success is True
        assert user is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_not_found(self, mock_dao_class):
        """Test obtenció d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.get_user_by_uid.return_value = None
        
        controller = UserController()
        success, user, error = controller.get_user_by_uid('nonexistent_uid')
        
        assert success is False
        assert user is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_get_user_by_uid_empty_uid(self, mock_dao_class):
        """Test obtenció d'usuari amb UID buit"""
        controller = UserController()
        success, user, error = controller.get_user_by_uid('')
        
        assert success is False
        assert user is None
        assert 'no proporcionat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_success(self, mock_dao_class, sample_user):
        """Test actualització d'usuari exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.get_user_by_email.return_value = None
        mock_dao.update_user.return_value = True
        mock_dao.get_user_by_uid.return_value = sample_user
        
        controller = UserController()
        update_data = {'username': 'updated'}
        success, user, error = controller.update_user('test_uid', update_data)
        
        assert success is True
        assert user is not None
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_not_found(self, mock_dao_class):
        """Test actualització d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = False
        
        controller = UserController()
        success, user, error = controller.update_user('nonexistent_uid', {'username': 'test'})
        
        assert success is False
        assert user is None
        assert 'no trobat' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_update_user_duplicate_email(self, mock_dao_class, sample_user):
        """Test actualització amb email ja en ús per altre usuari"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        
        # Email ja en ús per altre usuari
        from ..models.user import User
        other_user = User(
            uid='other_uid',
            username=sample_user.username,
            email=sample_user.email,
            language=sample_user.language
        )
        mock_dao.get_user_by_email.return_value = other_user
        
        controller = UserController()
        success, user, error = controller.update_user('test_uid', {'email': 'test@example.com'})
        
        assert success is False
        assert user is None
        assert 'ja està en ús' in error
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_success(self, mock_dao_class):
        """Test eliminació d'usuari exitosa"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = True
        mock_dao.delete_user.return_value = True
        
        controller = UserController()
        success, error = controller.delete_user('test_uid')
        
        assert success is True
        assert error is None
    
    @patch('api.controllers.user_controller.UserDAO')
    def test_delete_user_not_found(self, mock_dao_class):
        """Test eliminació d'usuari no existent"""
        mock_dao = mock_dao_class.return_value
        mock_dao.user_exists.return_value = False
        
        controller = UserController()
        success, error = controller.delete_user('nonexistent_uid')
        
        assert success is False
        assert 'no trobat' in error


# ==================== TESTS DE VIEWS ====================

@pytest.mark.views
class TestUserViews:
    """Tests per a les views d'usuaris"""
    
    @patch('api.views.user_views.UserController')
    def test_create_user_success(self, mock_controller_class, sample_user_data, sample_user, mock_authenticated_request):
        """Test creació d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.create_user.return_value = (True, sample_user, None)
        
        # Crear request autenticat
        request = mock_authenticated_request('post', '/api/users/', sample_user_data)
        
        # Cridar la vista directament
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_201_CREATED
        assert 'uid' in response.data
        assert response.data['email'] == sample_user.email
        
        # Verificar que el controller es va cridar correctament
        mock_controller.create_user.assert_called_once()
    
    @patch('api.views.user_views.UserController')
    def test_create_user_missing_uid(self, mock_controller_class, mock_authenticated_request):
        """Test creació d'usuari sense UID al token"""
        # Crear request sense user_uid
        request = mock_authenticated_request('post', '/api/users/', {'email': 'test@example.com', 'username': 'test'})
        delattr(request, 'user_uid')  # Eliminar l'atribut user_uid
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Sense user_uid, esperem 401
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_create_user_invalid_data(self, mock_controller_class, mock_authenticated_request):
        """Test creació d'usuari amb dades invàlides"""
        invalid_data = {'username': 'test'}  # Falta email
        
        request = mock_authenticated_request('post', '/api/users/', invalid_data)
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Dades invàlides, esperem 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_create_user_duplicate(self, mock_controller_class, sample_user_data, mock_authenticated_request):
        """Test creació d'usuari duplicat"""
        # Configurar mock per retornar error de duplicat
        mock_controller = mock_controller_class.return_value
        mock_controller.create_user.return_value = (False, None, "L'usuari ja existeix")
        
        request = mock_authenticated_request('post', '/api/users/', sample_user_data)
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Usuari duplicat, esperem 409
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_get_user_success(self, mock_controller_class, sample_user, mock_authenticated_request):
        """Test obtenció d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_by_uid.return_value = (True, sample_user, None)
        
        # Crear request autenticat
        request = mock_authenticated_request('get', f'/api/users/{sample_user.uid}/')
        
        # Cridar la vista directament
        view = UserDetailAPIView.as_view()
        response = view(request, uid=sample_user.uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['uid'] == sample_user.uid
        assert response.data['email'] == sample_user.email
    
    @patch('api.views.user_views.UserController')
    def test_get_user_not_found(self, mock_controller_class, mock_authenticated_request):
        """Test obtenció d'usuari no existent"""
        # Configurar mock per retornar usuari no trobat
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_by_uid.return_value = (False, None, "Usuari no trobat")
        
        request = mock_authenticated_request('get', '/api/users/nonexistent/')
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid='nonexistent')
        
        # Usuari no trobat, esperem 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_update_user_success(self, mock_controller_class, sample_user, mock_authenticated_request):
        """Test actualització d'usuari via API amb autenticació mockejada"""
        update_data = {'username': 'updated_username'}
        
        # Configurar mock del controller
        updated_user = User.from_dict({**sample_user.to_dict(), 'username': 'updated_username'})
        mock_controller = mock_controller_class.return_value
        mock_controller.update_user.return_value = (True, updated_user, None)
        
        # Crear request autenticat amb el mateix UID
        request = mock_authenticated_request('patch', f'/api/users/{sample_user.uid}/', update_data, uid=sample_user.uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=sample_user.uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'updated_username'
    
    @patch('api.views.user_views.UserController')
    def test_update_user_invalid_data(self, mock_controller_class, mock_authenticated_request):
        """Test actualització amb dades invàlides"""
        invalid_data = {'email': 'invalid_email'}  # Email sense @
        
        request = mock_authenticated_request('patch', '/api/users/test_uid/', invalid_data, uid='test_uid')
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid='test_uid')
        
        # Dades invàlides, esperem 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_delete_user_success(self, mock_controller_class, mock_authenticated_request):
        """Test eliminació d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_user.return_value = (True, None)
        
        # Crear request autenticat
        test_uid = 'test_uid_12345'
        request = mock_authenticated_request('delete', f'/api/users/{test_uid}/', uid=test_uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=test_uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @patch('api.views.user_views.UserController')
    def test_delete_user_not_found(self, mock_controller_class, mock_authenticated_request):
        """Test eliminació d'usuari no existent"""
        # Configurar mock per retornar usuari no trobat
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_user.return_value = (False, "Usuari no trobat")
        
        test_uid = 'nonexistent_uid'
        request = mock_authenticated_request('delete', f'/api/users/{test_uid}/', uid=test_uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=test_uid)
        
        # Usuari no trobat, esperem 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data


# ==================== TESTS D'INTEGRACIÓ ====================

@pytest.mark.integration
class TestUserIntegration:
    """Tests d'integració entre components"""
    
    @patch('api.daos.user_dao.FirestoreService')
    @patch('api.daos.user_dao.cache_service')
    def test_full_user_creation_flow(self, mock_cache, mock_firestore_service, sample_user_data):
        """Test flux complet de creació d'usuari"""
        # Configurar cache mock
        mock_cache.get.return_value = None  # Cache miss
        mock_cache.generate_key.return_value = 'test_cache_key'
        
        # Configurar mocks de Firestore
        mock_db = MagicMock()
        mock_firestore_instance = mock_firestore_service.return_value
        mock_firestore_instance.get_db.return_value = mock_db
        
        mock_collection = MagicMock()
        mock_db.collection.return_value = mock_collection
        
        # Mock per comprovar que no existeix (get_user_by_uid)
        mock_doc_snapshot_not_exists = MagicMock()
        mock_doc_snapshot_not_exists.exists = False
        
        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc_snapshot_not_exists
        mock_collection.document.return_value = mock_doc_ref
        
        # Mock per cerca per email (no existeix)
        mock_query = MagicMock()
        mock_query.get.return_value = []
        mock_collection.where.return_value.limit.return_value = mock_query
        
        # Crear usuari a través del controller
        controller = UserController()
        success, user, error = controller.create_user(sample_user_data, 'test_uid')
        
        # Verificacions
        if not success:
            print(f"Error: {error}")
        assert success is True, f"Expected success=True but got error: {error}"
        assert user is not None
        assert error is None
        assert isinstance(user, User)
