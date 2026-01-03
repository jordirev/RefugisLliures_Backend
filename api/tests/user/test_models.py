"""
Tests per usuaris
"""

import pytest
from api.models.user import User
# ==================== TESTS DE MODELS ====================


@pytest.mark.models
class TestUserModel:
    """Tests per al model User"""
    
    def test_user_creation_valid(self, sample_user_data):
        """Test creació d'usuari amb dades vàlides"""
        user = User.from_dict(sample_user_data)
        
        assert user.uid == sample_user_data['uid']
        assert user.username == sample_user_data['username']
        assert user.language == sample_user_data['language']
    
    def test_user_creation_missing_uid(self):
        """Test creació d'usuari sense UID (ha de fallar)"""
        data = {'uid': '', 'username': 'test'}
        
        with pytest.raises(ValueError, match="UID és requerit"):
            User(**data)
    
    def test_user_creation_missing_username(self):
        """Test creació d'usuari sense username"""
        data = {'uid': 'test_uid', 'username': ''}
        
        # Username can be empty - just test it doesn't raise an error
        user = User(**data)
        assert user.uid == 'test_uid'
    
    def test_user_creation_with_language(self):
        """Test creació d'usuari amb idioma personalitzat"""
        data = {'uid': 'test_uid', 'username': 'test', 'language': 'es'}
        
        user = User(**data)
        assert user.language == 'es'
    
    def test_user_to_dict(self, sample_user):
        """Test conversió d'usuari a diccionari"""
        user_dict = sample_user.to_dict()
        
        assert isinstance(user_dict, dict)
        assert user_dict['uid'] == sample_user.uid
        assert user_dict['username'] == sample_user.username
        assert 'favourite_refuges' in user_dict
    
    def test_user_from_dict(self, sample_user_data):
        """Test creació d'usuari des de diccionari"""
        user = User.from_dict(sample_user_data)
        
        assert isinstance(user, User)
        assert user.uid == sample_user_data['uid']
        assert user.username == sample_user_data['username']
    
    def test_user_str_representation(self, sample_user):
        """Test representació textual de l'usuari"""
        user_str = str(sample_user)
        
        assert 'User' in user_str
        assert sample_user.uid in user_str
    
    def test_user_default_values(self):
        """Test valors per defecte de l'usuari"""
        user = User(uid='test', username='test')
        
        assert user.language == 'ca'
        assert user.num_shared_experiences == 0
        assert user.num_renovated_refuges == 0
        assert user.favourite_refuges is None
