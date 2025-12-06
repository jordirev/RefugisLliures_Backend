"""
Tests per usuaris
"""

import pytest
from unittest.mock import patch
from rest_framework import status
from api.models.user import User
from api.views.user_views import (
    UsersCollectionAPIView,
    UserDetailAPIView,
    UserFavouriteRefugesAPIView,
    UserFavouriteRefugesDetailAPIView,
    UserVisitedRefugesAPIView,
    UserVisitedRefugesDetailAPIView
)


# ==================== FIXTURES ====================

@pytest.fixture
def sample_refugis_info_list():
    """Llista d'informació de refugis per tests"""
    return [
        {
            'id': 'refugi_001',
            'name': 'Refugi A',
            'region': 'Pirineus',
            'places': 10,
            'coord': {'long': 1.5, 'lat': 42.5}
        },
        {
            'id': 'refugi_002',
            'name': 'Refugi B',
            'region': 'Pirineus',
            'places': 15,
            'coord': {'long': 1.6, 'lat': 42.6}
        }
    ]


# ==================== TESTS DE VIEWS ====================


@pytest.mark.views
class TestUserViews:
    """Tests per a les views d'usuaris"""
    
    @patch('api.views.user_views.UserController')
    def test_create_user_success(self, mock_controller_class, sample_user_data, sample_user, mock_authenticated_request):
        """Test creació d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.create_user.return_value = (True, sample_user, None)
        
        # Crear request autenticat
        request = mock_authenticated_request('post', '/api/users/', sample_user_data)
        
        # Cridar la vista directament
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_201_CREATED
        assert 'uid' in response.data
        assert response.data['email'] == sample_user.email
        
        # Verificar que el controller es va cridar correctament
        mock_controller.create_user.assert_called_once()
    
    @patch('api.views.user_views.UserController')
    def test_create_user_missing_uid(self, mock_controller_class, mock_authenticated_request):
        """Test creació d'usuari sense UID al token"""
        # Crear request sense user_uid
        request = mock_authenticated_request('post', '/api/users/', {'email': 'test@example.com', 'username': 'test'})
        delattr(request, 'user_uid')  # Eliminar l'atribut user_uid
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Sense user_uid, esperem 401
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'detail' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_create_user_invalid_data(self, mock_controller_class, mock_authenticated_request):
        """Test creació d'usuari amb dades invàlides"""
        invalid_data = {'username': 'test'}  # Falta email
        
        request = mock_authenticated_request('post', '/api/users/', invalid_data)
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Dades invàlides, esperem 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_create_user_duplicate(self, mock_controller_class, sample_user_data, mock_authenticated_request):
        """Test creació d'usuari duplicat"""
        # Configurar mock per retornar error de duplicat
        mock_controller = mock_controller_class.return_value
        mock_controller.create_user.return_value = (False, None, "L'usuari ja existeix")
        
        request = mock_authenticated_request('post', '/api/users/', sample_user_data)
        
        view = UsersCollectionAPIView.as_view()
        response = view(request)
        
        # Usuari duplicat, esperem 409
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_get_user_success(self, mock_controller_class, sample_user, mock_authenticated_request):
        """Test obtenció d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_by_uid.return_value = (True, sample_user, None)
        
        # Crear request autenticat
        request = mock_authenticated_request('get', f'/api/users/{sample_user.uid}/')
        
        # Cridar la vista directament
        view = UserDetailAPIView.as_view()
        response = view(request, uid=sample_user.uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['uid'] == sample_user.uid
        assert response.data['email'] == sample_user.email
    
    @patch('api.views.user_views.UserController')
    def test_get_user_not_found(self, mock_controller_class, mock_authenticated_request):
        """Test obtenció d'usuari no existent"""
        # Configurar mock per retornar usuari no trobat
        mock_controller = mock_controller_class.return_value
        mock_controller.get_user_by_uid.return_value = (False, None, "Usuari no trobat")
        
        request = mock_authenticated_request('get', '/api/users/nonexistent/')
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid='nonexistent')
        
        # Usuari no trobat, esperem 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_update_user_success(self, mock_controller_class, sample_user, mock_authenticated_request):
        """Test actualització d'usuari via API amb autenticació mockejada"""
        update_data = {'username': 'updated_username'}
        
        # Configurar mock del controller
        updated_user = User.from_dict({**sample_user.to_dict(), 'username': 'updated_username'})
        mock_controller = mock_controller_class.return_value
        mock_controller.update_user.return_value = (True, updated_user, None)
        
        # Crear request autenticat amb el mateix UID
        request = mock_authenticated_request('patch', f'/api/users/{sample_user.uid}/', update_data, uid=sample_user.uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=sample_user.uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'updated_username'
    
    @patch('api.views.user_views.UserController')
    def test_update_user_invalid_data(self, mock_controller_class, mock_authenticated_request):
        """Test actualització amb dades invàlides"""
        invalid_data = {'email': 'invalid_email'}  # Email sense @
        
        request = mock_authenticated_request('patch', '/api/users/test_uid/', invalid_data, uid='test_uid')
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid='test_uid')
        
        # Dades invàlides, esperem 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('api.views.user_views.UserController')
    def test_delete_user_success(self, mock_controller_class, mock_authenticated_request):
        """Test eliminació d'usuari via API amb autenticació mockejada"""
        # Configurar mock del controller
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_user.return_value = (True, None)
        
        # Crear request autenticat
        test_uid = 'test_uid_12345'
        request = mock_authenticated_request('delete', f'/api/users/{test_uid}/', uid=test_uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=test_uid)
        
        # Verificar resposta
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    @patch('api.views.user_views.UserController')
    def test_delete_user_not_found(self, mock_controller_class, mock_authenticated_request):
        """Test eliminació d'usuari no existent"""
        # Configurar mock per retornar usuari no trobat
        mock_controller = mock_controller_class.return_value
        mock_controller.delete_user.return_value = (False, "Usuari no trobat")
        
        test_uid = 'nonexistent_uid'
        request = mock_authenticated_request('delete', f'/api/users/{test_uid}/', uid=test_uid)
        
        view = UserDetailAPIView.as_view()
        response = view(request, uid=test_uid)
        
        # Usuari no trobat, esperem 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data


# ==================== TESTS REFUGIS PREFERITS I VISITATS ====================

@pytest.mark.views
class TestUserFavouriteRefugesAPIViewGet:
    """Tests per GET /users/{uid}/favorite-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test obtenir refugis preferits amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['id'] == 'refugi_001'
        mock_controller.get_refugis_preferits_info.assert_called_once_with('test_uid_123')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_empty_list(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (True, [], None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
        assert 'no trobat' in response.data['error']
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.return_value = (False, None, "Error genèric")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_preferits_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis preferits amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_preferits_info.side_effect = Exception("Database error")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/favorite-refuges/')
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

@pytest.mark.views
class TestUserFavouriteRefugesAPIViewPost:
    """Tests per POST /users/{uid}/favorite-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test afegir refugi preferit amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (True, sample_refugis_info_list, None)
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.add_refugi_preferit.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_invalid_data_missing_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit sense refuge_id"""
        # Arrange
        data = {}  # Falta refuge_id
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'details' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_invalid_data_empty_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit amb refuge_id buit"""
        # Arrange
        data = {'refuge_id': ''}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_refugi_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit quan el refugi no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.return_value = (False, None, "Refugi amb ID refugi_001 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi preferit amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_preferit.side_effect = Exception("Network error")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/favorite-refuges/', data)
        view = UserFavouriteRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS PREFERITS - DETAIL ENDPOINT ====================

@pytest.mark.views
class TestUserFavouriteRefugesDetailAPIViewDelete:
    """Tests per DELETE /users/{uid}/favorite-refuges/{refuge_id}/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test eliminar refugi preferit amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.remove_refugi_preferit.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_empty_result(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit resultant en llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (True, [], None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_preferit_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.return_value = (False, None, "Error eliminant refugi")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_preferit_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi preferit amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_preferit.side_effect = Exception("Connection timeout")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/favorite-refuges/refugi_001/')
        view = UserFavouriteRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS VISITATS - COLLECTION ENDPOINT ====================

@pytest.mark.views
class TestUserVisitedRefugesAPIViewGet:
    """Tests per GET /users/{uid}/visited-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test obtenir refugis visitats amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        assert response.data['results'][0]['id'] == 'refugi_001'
        mock_controller.get_refugis_visitats_info.assert_called_once_with('test_uid_123')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_empty_list(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (True, [], None)
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.return_value = (False, None, "Error genèric")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_get_refugis_visitats_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test obtenir refugis visitats amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.get_refugis_visitats_info.side_effect = Exception("Database error")
        
        request = mock_authenticated_request('get', '/api/users/test_uid_123/visited-refuges/')
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

@pytest.mark.views
class TestUserVisitedRefugesAPIViewPost:
    """Tests per POST /users/{uid}/visited-refuges/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test afegir refugi visitat amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (True, sample_refugis_info_list, None)
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.add_refugi_visitat.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_invalid_data_missing_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat sense refuge_id"""
        # Arrange
        data = {}  # Falta refuge_id
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'details' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_invalid_data_empty_refugi_id(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat amb refuge_id buit"""
        # Arrange
        data = {'refuge_id': ''}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_refugi_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat quan el refugi no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.return_value = (False, None, "Refugi amb ID refugi_001 no trobat")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_post_refugi_visitat_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test afegir refugi visitat amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.add_refugi_visitat.side_effect = Exception("Network error")
        
        data = {'refuge_id': 'refugi_001'}
        request = mock_authenticated_request('post', '/api/users/test_uid_123/visited-refuges/', data)
        view = UserVisitedRefugesAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data


# ==================== TESTS REFUGIS VISITATS - DETAIL ENDPOINT ====================

@pytest.mark.views
class TestUserVisitedRefugesDetailAPIViewDelete:
    """Tests per DELETE /users/{uid}/visited-refuges/{refuge_id}/"""
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_success(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request, sample_refugis_info_list):
        """Test eliminar refugi visitat amb èxit"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (True, sample_refugis_info_list, None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert len(response.data['results']) == 2
        mock_controller.remove_refugi_visitat.assert_called_once_with('test_uid_123', 'refugi_001')
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_empty_result(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat resultant en llista buida"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (True, [], None)
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_user_not_found(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat quan l'usuari no existeix"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (False, None, "Usuari amb UID test_uid_123 no trobat")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_generic_error(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat amb error genèric"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.return_value = (False, None, "Error eliminant refugi")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
    
    @patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True)
    @patch('api.permissions.IsSameUser.has_permission', return_value=True)
    @patch('api.views.user_views.UserController')
    def test_delete_refugi_visitat_exception(self, mock_controller_class, mock_same_user, mock_auth, mock_authenticated_request):
        """Test eliminar refugi visitat amb excepció"""
        # Arrange
        mock_controller = mock_controller_class.return_value
        mock_controller.remove_refugi_visitat.side_effect = Exception("Connection timeout")
        
        request = mock_authenticated_request('delete', '/api/users/test_uid_123/visited-refuges/refugi_001/')
        view = UserVisitedRefugesDetailAPIView.as_view()
        
        # Act
        response = view(request, uid='test_uid_123', refuge_id='refugi_001')
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

