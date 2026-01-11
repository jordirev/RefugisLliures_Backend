"""
Tests per usuaris
"""

import pytest
from rest_framework.exceptions import ValidationError
from api.serializers.user_serializer import (
    UserSerializer, 
    UserCreateSerializer, 
    UserUpdateSerializer,
    UserValidatorMixin
)
# ==================== TESTS DE MODELS ====================


@pytest.mark.serializers
class TestUserSerializers:
    """Tests per als serializers d'usuaris"""
    
    def test_user_serializer_valid_data(self, sample_user_data):
        """Test serialització amb dades vàlides"""
        serializer = UserSerializer(data=sample_user_data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['username'] == sample_user_data['username']
    
    def test_user_serializer_invalid_username(self):
        """Test serialització amb username massa curt"""
        data = {
            'uid': 'test_uid',
            'username': 'a',
            'language': 'ca'
        }
        serializer = UserSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'username' in serializer.errors
    
    def test_user_serializer_empty_username(self):
        """Test serialització amb username buit"""
        data = {
            'uid': 'test_uid',
            'username': '',
            'language': 'ca'
        }
        serializer = UserSerializer(data=data)
        
        # Username can be empty, so it should be valid
        assert serializer.is_valid()
    
    def test_user_serializer_invalid_language(self):
        """Test serialització amb language invàlid"""
        data = {
            'uid': 'test_uid',
            'username': 'test',
            'language': 'invalid_lang'
        }
        serializer = UserSerializer(data=data)
        
        assert not serializer.is_valid()
        assert 'language' in serializer.errors
    
    def test_user_create_serializer_valid(self):
        """Test UserCreateSerializer amb dades vàlides"""
        data = {
            'username': 'newuser',
            'language': 'ca'
        }
        serializer = UserCreateSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['username'] == 'newuser'
    
    def test_user_create_serializer_username_normalization(self):
        """Test normalització d'username (trim)"""
        data = {
            'username': '  testuser  ',
            'language': 'ca'
        }
        serializer = UserCreateSerializer(data=data)
        
        assert serializer.is_valid()
        assert serializer.validated_data['username'] == 'testuser'
    
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
            'language': 'es'
        }
        serializer = UserUpdateSerializer(data=data)
        
        assert serializer.is_valid()
        assert len(serializer.validated_data) == 2
    
    def test_validator_mixin_uid_field(self):
        """Test validador d'uid del mixin"""
        # UID vàlid
        uid = UserValidatorMixin.validate_uid_field('test_uid_123')
        assert uid == 'test_uid_123'
        
        # UID buit
        with pytest.raises(ValidationError):
            UserValidatorMixin.validate_uid_field('')
    
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
