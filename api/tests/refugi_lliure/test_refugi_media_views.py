"""
Tests per a les vistes de gestió de mitjans de refugis
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from django.core.files.uploadedfile import SimpleUploadedFile
from api.views.refugi_media_views import RefugiMediaAPIView, RefugiMediaDeleteAPIView

@pytest.mark.views
class TestRefugiMediaViews:
    """Tests per a les vistes de mitjans"""
    
    @pytest.fixture
    def factory(self):
        return APIRequestFactory()
    
    @pytest.fixture
    def mock_controller(self):
        with patch('api.views.refugi_media_views.RefugiLliureController') as mock:
            yield mock
    
    @pytest.fixture
    def user_uid(self):
        return 'test_user_uid'
    
    def test_get_media_list_success(self, factory, mock_controller, user_uid):
        """Test obtenció de llista de mitjans exitosa"""
        # Configurar mock
        controller_instance = mock_controller.return_value
        expected_media = [
            {'key': 'path/1.jpg', 'url': 'http://url1', 'uploaded_at': '2024-01-01'},
            {'key': 'path/2.jpg', 'url': 'http://url2', 'uploaded_at': '2024-01-02'}
        ]
        controller_instance.get_refugi_media.return_value = (expected_media, None)
        
        # Crear request
        view = RefugiMediaAPIView.as_view()
        request = factory.get('/api/refugis/refugi_123/media/')
        force_authenticate(request, user=MagicMock())
        
        # Executar vista
        response = view(request, id='refugi_123')
        
        # Verificar
        assert response.status_code == status.HTTP_200_OK
        assert response.data['media'] == expected_media
        controller_instance.get_refugi_media.assert_called_once_with('refugi_123', 3600)

    def test_get_media_list_not_found(self, factory, mock_controller):
        """Test obtenció de mitjans quan el refugi no existeix"""
        controller_instance = mock_controller.return_value
        controller_instance.get_refugi_media.return_value = (None, "Refugi not found")
        
        view = RefugiMediaAPIView.as_view()
        request = factory.get('/api/refugis/nonexistent/media/')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='nonexistent')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.data['error']

    def test_get_media_list_error(self, factory, mock_controller):
        """Test error intern obtenint mitjans"""
        controller_instance = mock_controller.return_value
        controller_instance.get_refugi_media.return_value = (None, "Internal error")
        
        view = RefugiMediaAPIView.as_view()
        request = factory.get('/api/refugis/refugi_123/media/')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_post_media_success(self, factory, mock_controller, user_uid):
        """Test pujada de mitjans exitosa"""
        controller_instance = mock_controller.return_value
        expected_response = {
            'uploaded': [{'key': 'k1'}],
            'failed': []
        }
        controller_instance.upload_refugi_media.return_value = (expected_response, None)
        
        # Crear fitxers mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        file1 = SimpleUploadedFile("file1.jpg", b"content", content_type="image/jpeg")
        
        view = RefugiMediaAPIView.as_view()
        request = factory.post(
            '/api/refugis/refugi_123/media/',
            {'files': [file1]},
            format='multipart'
        )
        force_authenticate(request, user=MagicMock())
        request.user_uid = user_uid
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data == expected_response
        controller_instance.upload_refugi_media.assert_called_once()
        # Verificar arguments de crida
        args, _ = controller_instance.upload_refugi_media.call_args
        assert args[0] == 'refugi_123'
        assert len(args[1]) == 1 # Llista de fitxers
        assert args[2] == user_uid

    def test_post_media_no_files(self, factory, mock_controller):
        """Test pujada sense fitxers"""
        view = RefugiMediaAPIView.as_view()
        request = factory.post('/api/refugis/refugi_123/media/', {}, format='multipart')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_post_media_not_authenticated(self, factory, mock_controller):
        """Test pujada sense user_uid"""
        view = RefugiMediaAPIView.as_view()
        file1 = SimpleUploadedFile("file1.jpg", b"content", content_type="image/jpeg")
        request = factory.post(
            '/api/refugis/refugi_123/media/',
            {'files': [file1]},
            format='multipart'
        )
        force_authenticate(request, user=MagicMock())
        # No assignem request.user_uid
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch('api.views.refugi_media_views.IsMediaUploader.has_permission')
    def test_delete_media_success(self, mock_permission, factory, mock_controller):
        """Test eliminació de mitjà exitosa"""
        mock_permission.return_value = True
        controller_instance = mock_controller.return_value
        controller_instance.delete_refugi_media.return_value = (True, None)
        
        view = RefugiMediaDeleteAPIView.as_view()
        request = factory.delete('/api/refugis/refugi_123/media/some%2Fkey.jpg')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123', key='some%2Fkey.jpg')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True
        controller_instance.delete_refugi_media.assert_called_once_with('refugi_123', 'some/key.jpg')

    @patch('api.views.refugi_media_views.IsMediaUploader.has_permission')
    def test_delete_media_not_found(self, mock_permission, factory, mock_controller):
        """Test eliminació de mitjà no trobat"""
        mock_permission.return_value = True
        controller_instance = mock_controller.return_value
        controller_instance.delete_refugi_media.return_value = (False, "Media not found")
        
        view = RefugiMediaDeleteAPIView.as_view()
        request = factory.delete('/api/refugis/refugi_123/media/key')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123', key='key')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('api.views.refugi_media_views.IsMediaUploader.has_permission')
    def test_delete_media_error(self, mock_permission, factory, mock_controller):
        """Test error eliminant mitjà"""
        mock_permission.return_value = True
        controller_instance = mock_controller.return_value
        controller_instance.delete_refugi_media.return_value = (False, "Delete error")
        
        view = RefugiMediaDeleteAPIView.as_view()
        request = factory.delete('/api/refugis/refugi_123/media/key')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123', key='key')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
