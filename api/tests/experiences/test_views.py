"""
Tests per a les vistes d'experiències
"""
import pytest
from unittest.mock import MagicMock, patch
from rest_framework.test import APIRequestFactory
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from api.views.experience_views import ExperienceListAPIView, ExperienceDetailAPIView
from api.models.experience import Experience

@pytest.mark.views
class TestExperienceViews:
    """Tests per a les vistes d'experiències"""
    
    @pytest.fixture
    def factory(self):
        return APIRequestFactory()

    @patch('api.views.experience_views.ExperienceController')
    def test_get_experiences_list_success(self, mock_controller_class, factory):
        """Test llistar experiències amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Test',
            'images_metadata': []
        }
        mock_controller.get_experiences_by_refuge.return_value = ([mock_exp], None)
        
        view = ExperienceListAPIView.as_view()
        request = factory.get('/api/experiences/?refuge_id=ref_1')
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['experiences']) == 1

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_success(self, mock_controller_class, factory):
        """Test crear experiència amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Test'
        }
        mock_controller.create_experience.return_value = (mock_exp, None, None)
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['experience']['id'] == 'exp_1'

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_experience_success(self, mock_controller_class, factory):
        """Test actualitzar experiència amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Updated'
        }
        mock_controller.update_experience.return_value = (mock_exp, None, None)
        
        view = ExperienceDetailAPIView.as_view()
        data = {'comment': 'Updated'}
        request = factory.patch('/api/experiences/exp_1/', data, format='multipart')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['experience']['comment'] == 'Updated'

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_experience_success(self, mock_controller_class, factory):
        """Test eliminar experiència amb èxit"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_experience.return_value = (True, None)
        
        view = ExperienceDetailAPIView.as_view()
        request = factory.delete('/api/experiences/exp_1/')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
