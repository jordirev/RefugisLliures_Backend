"""
Tests per al mapper d'experiències
"""
import pytest
from unittest.mock import patch
from api.mappers.experience_mapper import ExperienceMapper
from api.models.experience import Experience

@pytest.mark.mappers
class TestExperienceMapper:
    """Tests per al mapper ExperienceMapper"""
    
    @patch('api.models.experience.r2_media_service.get_refugi_media_service')
    def test_firestore_to_model(self, mock_get_service):
        """Test conversió de Firestore a model Experience"""
        data = {
            'id': 'exp_1',
            'comment': 'Test',
            'media_keys': []
        }
        experience = ExperienceMapper.firestore_to_model(data)
        assert isinstance(experience, Experience)
        assert experience.id == 'exp_1'

    def test_model_to_firestore(self):
        """Test conversió de model Experience a Firestore"""
        experience = Experience(
            id='exp_1',
            refuge_id='ref_1',
            creator_uid='user_1',
            modified_at='2024-01-01',
            comment='Test',
            media_keys=['key1']
        )
        data = ExperienceMapper.model_to_firestore(experience)
        assert data['id'] == 'exp_1'
        assert 'images_metadata' not in data
        assert data['media_keys'] == ['key1']

    @patch('api.models.experience.r2_media_service.get_refugi_media_service')
    def test_lists_conversion(self, mock_get_service):
        """Test conversió de llistes"""
        data_list = [{'id': 'exp_1', 'comment': 'm'}]
        models = ExperienceMapper.firestore_list_to_models(data_list)
        assert len(models) == 1
        assert models[0].id == 'exp_1'
        
        back_to_data = ExperienceMapper.models_to_firestore_list(models)
        assert len(back_to_data) == 1
        assert back_to_data[0]['id'] == 'exp_1'
