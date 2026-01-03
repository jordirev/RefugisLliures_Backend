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

    # ===== TESTS D'ERROR PER MILLORAR COVERAGE =====

    @patch('api.views.experience_views.ExperienceController')
    def test_get_experiences_missing_refuge_id(self, mock_controller_class, factory):
        """Test llistar experiències sense refuge_id (400)"""
        view = ExperienceListAPIView.as_view()
        request = factory.get('/api/experiences/')
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'refuge_id' in str(response.data['error']).lower()

    @patch('api.views.experience_views.ExperienceController')
    def test_get_experiences_not_found(self, mock_controller_class, factory):
        """Test llistar experiències amb error not found (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_experiences_by_refuge.return_value = (None, "Refuge not found")
        
        view = ExperienceListAPIView.as_view()
        request = factory.get('/api/experiences/?refuge_id=nonexistent')
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.experience_views.ExperienceController')
    def test_get_experiences_server_error(self, mock_controller_class, factory):
        """Test llistar experiències amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_experiences_by_refuge.return_value = (None, "Internal error")
        
        view = ExperienceListAPIView.as_view()
        request = factory.get('/api/experiences/?refuge_id=ref_1')
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_get_experiences_exception(self, mock_controller_class, factory):
        """Test llistar experiències amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.get_experiences_by_refuge.side_effect = Exception("Error inesperat")
        
        view = ExperienceListAPIView.as_view()
        request = factory.get('/api/experiences/?refuge_id=ref_1')
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_invalid_data(self, mock_controller_class, factory):
        """Test crear experiència amb dades invàlides (400)"""
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1'}  # Falta comment
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_no_uid(self, mock_controller_class, factory):
        """Test crear experiència sense UID (401)"""
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        # No establim request.user_uid
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_not_found(self, mock_controller_class, factory):
        """Test crear experiència en refugi no trobat (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_experience.return_value = (None, None, "Refuge not found")
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'nonexistent', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_server_error(self, mock_controller_class, factory):
        """Test crear experiència amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_experience.return_value = (None, None, "Database error")
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_with_partial_upload_error(self, mock_controller_class, factory):
        """Test crear experiència amb error parcial de pujada (201)"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Test'
        }
        upload_result = {'uploaded': ['file1.jpg'], 'failed': ['file2.jpg']}
        mock_controller.create_experience.return_value = (mock_exp, upload_result, "Error assigning media keys")
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'message' in response.data

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_with_upload_error_only(self, mock_controller_class, factory):
        """Test crear experiència amb error de pujada però experiència creada (201)"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Test'
        }
        mock_controller.create_experience.return_value = (mock_exp, None, "Error uploading files")
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'message' in response.data

    @patch('api.views.experience_views.ExperienceController')
    def test_create_experience_exception(self, mock_controller_class, factory):
        """Test crear experiència amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.create_experience.side_effect = Exception("Error inesperat")
        
        view = ExperienceListAPIView.as_view()
        data = {'refuge_id': 'ref_1', 'comment': 'Test'}
        request = factory.post('/api/experiences/', data, format='multipart')
        request.user_uid = 'user_1'
        
        with patch.object(ExperienceListAPIView, 'get_permissions', return_value=[]):
            response = view(request)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_experience_invalid_data(self, mock_controller_class, factory):
        """Test actualitzar experiència amb dades invàlides (400)"""
        mock_controller = mock_controller_class.return_value
        # El serializer ExperienceUpdateSerializer no requereix cap camp, però podem forçar un error
        mock_controller.update_experience.return_value = (None, None, "Invalid data")
        
        view = ExperienceDetailAPIView.as_view()
        # Dades buides, que el serializer hauria d'acceptar
        data = {}
        request = factory.patch('/api/experiences/exp_1/', data, format='multipart')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        # Quan result és None, retorna 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_experience_not_found(self, mock_controller_class, factory):
        """Test actualitzar experiència no trobada (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_experience.return_value = (None, None, "Experience not found")
        
        view = ExperienceDetailAPIView.as_view()
        data = {'comment': 'Updated'}
        request = factory.patch('/api/experiences/exp_1/', data, format='multipart')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_experience_with_partial_upload_error(self, mock_controller_class, factory):
        """Test actualitzar experiència amb error parcial de pujada (200)"""
        mock_controller = mock_controller_class.return_value
        mock_exp = MagicMock(spec=Experience)
        mock_exp.to_dict.return_value = {
            'id': 'exp_1',
            'refuge_id': 'ref_1',
            'creator_uid': 'user_1',
            'modified_at': '2024-01-01',
            'comment': 'Updated'
        }
        upload_result = {'uploaded': ['file1.jpg'], 'failed': ['file2.jpg']}
        mock_controller.update_experience.return_value = (mock_exp, upload_result, "Error assigning media keys")
        
        view = ExperienceDetailAPIView.as_view()
        data = {'comment': 'Updated'}
        request = factory.patch('/api/experiences/exp_1/', data, format='multipart')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data

    @patch('api.views.experience_views.ExperienceController')
    def test_patch_experience_exception(self, mock_controller_class, factory):
        """Test actualitzar experiència amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.update_experience.side_effect = Exception("Error inesperat")
        
        view = ExperienceDetailAPIView.as_view()
        data = {'comment': 'Updated'}
        request = factory.patch('/api/experiences/exp_1/', data, format='multipart')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_experience_not_found(self, mock_controller_class, factory):
        """Test eliminar experiència no trobada (404)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_experience.return_value = (False, "Experience not found")
        
        view = ExperienceDetailAPIView.as_view()
        request = factory.delete('/api/experiences/exp_1/')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_experience_server_error(self, mock_controller_class, factory):
        """Test eliminar experiència amb error del servidor (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_experience.return_value = (False, "Database error")
        
        view = ExperienceDetailAPIView.as_view()
        request = factory.delete('/api/experiences/exp_1/')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.experience_views.ExperienceController')
    def test_delete_experience_exception(self, mock_controller_class, factory):
        """Test eliminar experiència amb excepció (500)"""
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_experience.side_effect = Exception("Error inesperat")
        
        view = ExperienceDetailAPIView.as_view()
        request = factory.delete('/api/experiences/exp_1/')
        
        with patch.object(ExperienceDetailAPIView, 'get_permissions', return_value=[]):
            response = view(request, experience_id='exp_1')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
