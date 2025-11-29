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
