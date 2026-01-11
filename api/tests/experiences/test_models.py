"""
Tests per al model d'experiència
"""
import pytest
from unittest.mock import MagicMock, patch
from api.models.experience import Experience
from api.models.media_metadata import MediaMetadata

@pytest.mark.models
class TestExperienceModels:
    """Tests per al model Experience"""
    
    def test_experience_creation(self):
        """Test creació d'Experience"""
        experience = Experience(
            id="exp_123",
            refuge_id="ref_456",
            creator_uid="user_789",
            modified_at="2024-01-01T10:00:00Z",
            comment="Great view!",
            media_keys=["key1", "key2"]
        )
        
        assert experience.id == "exp_123"
        assert len(experience.media_keys) == 2
        assert experience.images_metadata == []

    def test_experience_to_dict(self):
        """Test conversió d'Experience a diccionari"""
        metadata = MediaMetadata(key="key1", url="http://url1")
        experience = Experience(
            id="exp_123",
            refuge_id="ref_456",
            creator_uid="user_789",
            modified_at="2024-01-01T10:00:00Z",
            comment="Comment",
            images_metadata=[metadata]
        )
        
        data = experience.to_dict()
        assert data['id'] == "exp_123"
        assert data['media_keys'] == ["key1"]
        assert len(data['images_metadata']) == 1
        assert data['images_metadata'][0]['url'] == "http://url1"

    @patch('api.models.experience.r2_media_service.get_refugi_media_service')
    def test_experience_from_dict(self, mock_get_service):
        """Test creació d'Experience des de diccionari amb metadades de mitjans"""
        mock_service = mock_get_service.return_value
        mock_service.generate_presigned_url.return_value = "http://presigned"
        
        data = {
            'id': 'exp_123',
            'refuge_id': 'ref_456',
            'creator_uid': 'user_789',
            'modified_at': '2024-01-01T10:00:00Z',
            'comment': 'Comment',
            'media_keys': ['key1']
        }
        
        experience = Experience.from_dict(data)
        
        assert experience.id == 'exp_123'
        assert len(experience.images_metadata) == 1
        assert experience.images_metadata[0].key == 'key1'
        assert experience.images_metadata[0].url == "http://presigned"
        mock_service.generate_presigned_url.assert_called_with('key1')

    @patch('api.models.experience.r2_media_service.get_refugi_media_service')
    def test_experience_from_dict_error_r2(self, mock_get_service):
        """Test creació d'Experience quan R2 falla"""
        mock_service = mock_get_service.return_value
        mock_service.generate_presigned_url.side_effect = Exception("R2 Error")
        
        data = {
            'id': 'exp_123',
            'media_keys': ['key1']
        }
        
        experience = Experience.from_dict(data)
        assert experience.id == 'exp_123'
        assert experience.images_metadata == [] # Hauria d'estar buit si falla
