"""
Tests per usuaris
"""

import pytest
from api.models.user import User
# ==================== TESTS DE MODELS ====================


@pytest.mark.mappers
class TestUserMapper:
    """Tests per al UserMapper"""
    
    def test_firebase_to_model(self, sample_user_data, user_mapper):
        """Test conversió de Firebase a model"""
        user = user_mapper.firebase_to_model(sample_user_data)
        
        assert isinstance(user, User)
        assert user.uid == sample_user_data['uid']
        assert user.username == sample_user_data['username']
    
    def test_model_to_firebase(self, sample_user, user_mapper):
        """Test conversió de model a Firebase"""
        firebase_data = user_mapper.model_to_firebase(sample_user)
        
        assert isinstance(firebase_data, dict)
        assert firebase_data['uid'] == sample_user.uid
        assert firebase_data['username'] == sample_user.username
    
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
    
    def test_validate_firebase_data_missing_username(self, user_mapper):
        """Test validació sense username"""
        data = {'uid': 'test_uid'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        # Username is optional, so this should be valid
        assert is_valid is True
    
    def test_validate_firebase_data_invalid_uid(self, user_mapper):
        """Test validació amb uid invàlid (buit)"""
        data = {'uid': '', 'username': 'test'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'uid' in error.lower()
    
    def test_validate_firebase_data_invalid_language(self, user_mapper):
        """Test validació amb language invàlid"""
        data = {'uid': 'test_uid', 'username': 'test', 'language': 'invalid'}
        is_valid, error = user_mapper.validate_firebase_data(data)
        
        assert is_valid is False
        assert 'idioma' in error.lower()  # Error message is still in Catalan
    
    def test_clean_firebase_data(self, user_mapper):
        """Test neteja de dades de Firebase"""
        data = {
            'uid': 'test_uid',
            'username': '  testuser  ',
            'language': '  CA  '
        }
        cleaned = user_mapper.clean_firebase_data(data)
        
        assert cleaned['username'] == 'testuser'
        assert cleaned['language'] == 'ca'
    
    def test_clean_firebase_data_preserves_other_fields(self, sample_user_data, user_mapper):
        """Test que la neteja preserva altres camps"""
        cleaned = user_mapper.clean_firebase_data(sample_user_data)
        
        assert cleaned['uid'] == sample_user_data['uid']
        assert cleaned['favourite_refuges'] == sample_user_data['favourite_refuges']


# ==================== TESTS DE DAOs ====================
