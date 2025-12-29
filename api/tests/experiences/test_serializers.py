"""
Tests per als serializers d'experiències
"""
import pytest
from api.serializers.experience_serializer import (
    ExperienceCreateSerializer, ExperienceUpdateSerializer, 
    ExperienceResponseSerializer, ExperienceListResponseSerializer
)

@pytest.mark.serializers
class TestExperienceSerializers:
    """Tests per als serializers d'experiències"""
    
    def test_experience_create_serializer_valid(self):
        """Test ExperienceCreateSerializer amb dades vàlides"""
        data = {
            'refuge_id': 'ref_1',
            'comment': 'Great place!'
        }
        serializer = ExperienceCreateSerializer(data=data)
        assert serializer.is_valid()

    def test_experience_update_serializer_valid(self):
        """Test ExperienceUpdateSerializer amb dades vàlides"""
        data = {
            'comment': 'Updated comment'
        }
        serializer = ExperienceUpdateSerializer(data=data)
        assert serializer.is_valid()

    def test_experience_response_serializer_valid(self):
        """Test ExperienceResponseSerializer amb dades vàlides"""
        data = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Test',
            'images_metadata': [
                {
                    'key': 'key1',
                    'url': 'http://example.com/url1',
                    'uploaded_at': '2024-01-01',
                    'creator_uid': 'user_1'
                }
            ]
        }
        serializer = ExperienceResponseSerializer(data=data)
        assert serializer.is_valid()
        assert len(serializer.validated_data['images_metadata']) == 1

    def test_experience_list_response_serializer_valid(self):
        """Test ExperienceListResponseSerializer amb dades vàlides"""
        data = {
            'experiences': [
                {
                    'id': 'exp_1',
                    'refuge_id': 'ref_1',
                    'creator_uid': 'user_1',
                    'modified_at': '2024-01-01',
                    'comment': 'Test'
                }
            ]
        }
        serializer = ExperienceListResponseSerializer(data=data)
        assert serializer.is_valid()
        assert len(serializer.validated_data['experiences']) == 1
