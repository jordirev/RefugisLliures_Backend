"""
Tests per a les vistes de gestió de mitjans de refugis
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
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
        controller_instance.get_refugi_media.assert_called_once_with('refugi_123', 3600, viewer_uid=None, is_admin=False)

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

    def test_post_media_not_allowed(self, factory, mock_controller, user_uid):
        """POST multipart a /media/ ja no existeix (la pujada va per upload-intents): 405"""
        view = RefugiMediaAPIView.as_view()
        request = factory.post('/api/refugis/refugi_123/media/', {}, format='multipart')
        force_authenticate(request, user=MagicMock())
        request.user_uid = user_uid

        response = view(request, id='refugi_123')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_get_media_list_error(self, factory, mock_controller):
        """Test error intern obtenint mitjans"""
        controller_instance = mock_controller.return_value
        controller_instance.get_refugi_media.return_value = (None, "Internal error")
        
        view = RefugiMediaAPIView.as_view()
        request = factory.get('/api/refugis/refugi_123/media/')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

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
        controller_instance.delete_refugi_media.assert_called_once_with('refugi_123', 'some/key.jpg', actor_uid=None)

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

    # ===== TESTS ADICIONALS PER MILLORAR COVERAGE =====

    def test_get_media_list_exception(self, factory, mock_controller):
        """Test excepció obtenint llista de mitjans (cobreix línies 92-94)"""
        controller_instance = mock_controller.return_value
        controller_instance.get_refugi_media.side_effect = Exception("Unexpected error")
        
        view = RefugiMediaAPIView.as_view()
        request = factory.get('/api/refugis/refugi_123/media/')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    @patch('api.views.refugi_media_views.IsMediaUploader.has_permission')
    def test_delete_media_success_returns_false_no_error(self, mock_permission, factory, mock_controller):
        """Test eliminació retorna False sense error (cobreix línia 249)"""
        mock_permission.return_value = True
        controller_instance = mock_controller.return_value
        controller_instance.delete_refugi_media.return_value = (False, None)
        
        view = RefugiMediaDeleteAPIView.as_view()
        request = factory.delete('/api/refugis/refugi_123/media/some%2Fkey.jpg')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123', key='some%2Fkey.jpg')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('api.views.refugi_media_views.IsMediaUploader.has_permission')
    def test_delete_media_exception(self, mock_permission, factory, mock_controller):
        """Test excepció en eliminació de mitjà (cobreix línies 260-262)"""
        mock_permission.return_value = True
        controller_instance = mock_controller.return_value
        controller_instance.delete_refugi_media.side_effect = Exception("Unexpected error")
        
        view = RefugiMediaDeleteAPIView.as_view()
        request = factory.delete('/api/refugis/refugi_123/media/key')
        force_authenticate(request, user=MagicMock())
        
        response = view(request, id='refugi_123', key='key')
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data
