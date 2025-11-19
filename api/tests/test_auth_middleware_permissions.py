"""
Tests per a middleware, authentication i permissions de l'API
Comprova el funcionament de Firebase Auth Middleware, FirebaseAuthentication i permissions personalitzades
"""
import pytest
from unittest.mock import Mock, patch
from django.http import JsonResponse
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIRequestFactory
from rest_framework import exceptions
from firebase_admin import auth

from api.middleware.firebase_auth_middleware import FirebaseAuthenticationMiddleware
from api.authentication import FirebaseAuthentication
from api.permissions import IsOwnerOrReadOnly, IsOwner, IsSameUser


# ============= FIXTURES =============

@pytest.fixture
def request_factory():
    """Factory per crear requests Django"""
    return RequestFactory()


@pytest.fixture
def api_request_factory():
    """Factory per crear requests DRF"""
    return APIRequestFactory()


@pytest.fixture
def valid_token():
    """Token JWT vàlid de mostra"""
    return "valid_firebase_token_12345"


@pytest.fixture
def expired_token():
    """Token JWT expirat de mostra"""
    return "expired_firebase_token_12345"


@pytest.fixture
def invalid_token():
    """Token JWT invàlid de mostra"""
    return "invalid_firebase_token_12345"


@pytest.fixture
def decoded_token():
    """Token decodificat de mostra"""
    return {
        'uid': 'test_uid_12345',
        'email': 'test@example.com',
        'email_verified': True,
        'name': 'Test User'
    }


@pytest.fixture
def mock_firebase_user():
    """Mock d'usuari Firebase"""
    user = Mock()
    user.uid = 'test_uid_12345'
    user.email = 'test@example.com'
    user.is_authenticated = True
    user.is_anonymous = False
    return user


@pytest.fixture
def mock_object_with_uid():
    """Mock d'objecte amb UID"""
    obj = Mock()
    obj.uid = 'test_uid_12345'
    return obj


@pytest.fixture
def mock_view():
    """Mock de vista DRF"""
    view = Mock()
    view.kwargs = {}
    return view


# ============= TESTS FIREBASE AUTH MIDDLEWARE =============

class TestFirebaseAuthenticationMiddleware:
    """Tests per al middleware d'autenticació Firebase"""
    
    def test_excluded_path_health(self, request_factory):
        """Test que el path /api/health/ està exclòs"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/health/')
        
        result = middleware.process_request(request)
        assert result is None
    
    def test_excluded_path_refugis(self, request_factory):
        """Test que el path /api/refuges/ està exclòs"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/refuges/')
        
        result = middleware.process_request(request)
        assert result is None
    
    def test_excluded_path_cache(self, request_factory):
        """Test que el path /api/cache/ està exclòs"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/cache/')
        
        result = middleware.process_request(request)
        assert result is None
    
    def test_excluded_path_admin(self, request_factory):
        """Test que el path /admin/ està exclòs"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/admin/')
        
        result = middleware.process_request(request)
        assert result is None
    
    def test_no_authorization_header(self, request_factory):
        """Test que retorna error 401 si no hi ha header Authorization"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Comprova el contingut de la resposta
        import json
        content = json.loads(result.content)
        assert 'error' in content
        assert content['error'] == 'No autoritzat'
    
    def test_invalid_authorization_format_no_bearer(self, request_factory):
        """Test que retorna error si el format no és 'Bearer <token>'"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = 'InvalidFormat token123'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_invalid_authorization_format_only_bearer(self, request_factory):
        """Test que retorna error si només hi ha 'Bearer' sense token"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_valid_token(self, mock_verify, request_factory, valid_token, decoded_token):
        """Test que verifica correctament un token vàlid"""
        mock_verify.return_value = decoded_token
        
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        result = middleware.process_request(request)
        
        assert result is None  # No retorna error
        assert hasattr(request, 'firebase_user')
        assert hasattr(request, 'user_uid')
        assert request.firebase_user == decoded_token
        assert request.user_uid == 'test_uid_12345'
        mock_verify.assert_called_once_with(valid_token)
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_expired_token(self, mock_verify, request_factory, expired_token):
        """Test que retorna error 401 amb token expirat"""
        mock_verify.side_effect = auth.ExpiredIdTokenError('Token expired', Exception('cause'))
        
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {expired_token}'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        
        import json
        content = json.loads(result.content)
        assert content['message'] == 'Token expirat'
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_revoked_token(self, mock_verify, request_factory, valid_token):
        """Test que retorna error 401 amb token revocat"""
        mock_verify.side_effect = auth.RevokedIdTokenError('Token revoked')
        
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        
        import json
        content = json.loads(result.content)
        assert content['message'] == 'Token revocat'
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_invalid_token(self, mock_verify, request_factory, invalid_token):
        """Test que retorna error 401 amb token invàlid"""
        mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
        
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {invalid_token}'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        
        import json
        content = json.loads(result.content)
        assert content['message'] == 'Token invàlid'
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_generic_exception(self, mock_verify, request_factory, valid_token):
        """Test que retorna error 401 amb excepció genèrica"""
        mock_verify.side_effect = Exception('Generic error')
        
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED
        
        import json
        content = json.loads(result.content)
        assert 'Error verificant el token' in content['message']


# ============= TESTS FIREBASE AUTHENTICATION =============

class TestFirebaseAuthentication:
    """Tests per a la classe FirebaseAuthentication"""
    
    def test_authenticate_with_middleware_data(self, api_request_factory, decoded_token):
        """Test que autentica utilitzant dades del middleware"""
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.firebase_user = decoded_token
        request.user_uid = 'test_uid_12345'
        
        result = auth_backend.authenticate(request)
        
        assert result is not None
        user, token = result
        assert user.uid == 'test_uid_12345'
        assert user.email == 'test@example.com'
        assert user.is_authenticated is True
        assert user.is_anonymous is False
        assert token == decoded_token
    
    def test_authenticate_without_header(self, api_request_factory):
        """Test que retorna None si no hi ha header Authorization"""
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        
        result = auth_backend.authenticate(request)
        
        assert result is None
    
    def test_authenticate_invalid_format_no_bearer(self, api_request_factory):
        """Test que llança excepció amb format invàlid"""
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = 'InvalidFormat token123'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Format del token invàlid' in str(exc_info.value)
    
    def test_authenticate_invalid_format_only_bearer(self, api_request_factory):
        """Test que llança excepció amb només 'Bearer'"""
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = 'Bearer'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Format del token invàlid' in str(exc_info.value)
    
    @patch('api.authentication.auth.verify_id_token')
    def test_authenticate_valid_token(self, mock_verify, api_request_factory, valid_token, decoded_token):
        """Test que autentica correctament amb token vàlid"""
        mock_verify.return_value = decoded_token
        
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        result = auth_backend.authenticate(request)
        
        assert result is not None
        user, token = result
        assert user.uid == 'test_uid_12345'
        assert user.email == 'test@example.com'
        assert user.is_authenticated is True
        assert token == decoded_token
        mock_verify.assert_called_once_with(valid_token)
    
    @patch('api.authentication.auth.verify_id_token')
    def test_authenticate_expired_token(self, mock_verify, api_request_factory, expired_token):
        """Test que llança excepció amb token expirat"""
        mock_verify.side_effect = auth.ExpiredIdTokenError('Token expired', Exception('cause'))
        
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {expired_token}'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Token expirat' in str(exc_info.value)
    
    @patch('api.authentication.auth.verify_id_token')
    def test_authenticate_revoked_token(self, mock_verify, api_request_factory, valid_token):
        """Test que llança excepció amb token revocat"""
        mock_verify.side_effect = auth.RevokedIdTokenError('Token revoked')
        
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Token revocat' in str(exc_info.value)
    
    @patch('api.authentication.auth.verify_id_token')
    def test_authenticate_invalid_token(self, mock_verify, api_request_factory, invalid_token):
        """Test que llança excepció amb token invàlid"""
        mock_verify.side_effect = auth.InvalidIdTokenError('Invalid token')
        
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {invalid_token}'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Token invàlid' in str(exc_info.value)
    
    @patch('api.authentication.auth.verify_id_token')
    def test_authenticate_generic_exception(self, mock_verify, api_request_factory, valid_token):
        """Test que llança excepció amb error genèric"""
        mock_verify.side_effect = Exception('Generic error')
        
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        with pytest.raises(exceptions.AuthenticationFailed) as exc_info:
            auth_backend.authenticate(request)
        
        assert 'Error verificant el token' in str(exc_info.value)
    
    def test_authenticate_header(self, api_request_factory):
        """Test que retorna el header WWW-Authenticate correcte"""
        auth_backend = FirebaseAuthentication()
        request = api_request_factory.get('/api/users/')
        
        result = auth_backend.authenticate_header(request)
        
        assert result == 'Bearer realm="api"'


# ============= TESTS PERMISSIONS =============

class TestIsOwnerOrReadOnly:
    """Tests per al permís IsOwnerOrReadOnly"""
    
    def test_has_permission_authenticated_user(self, api_request_factory, mock_firebase_user):
        """Test que permet accés a usuari autenticat"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.get('/api/users/')
        request.user = mock_firebase_user
        
        result = permission.has_permission(request, None)
        
        assert result is True
    
    def test_has_permission_unauthenticated_user(self, api_request_factory):
        """Test que denega accés a usuari no autenticat"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.get('/api/users/')
        request.user = None
        
        result = permission.has_permission(request, None)
        
        # El permís retorna None (que és Falsy) o False per usuari no autenticat
        assert not result
    
    def test_has_permission_user_without_is_authenticated(self, api_request_factory):
        """Test que denega accés a usuari sense atribut is_authenticated"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.get('/api/users/')
        request.user = Mock()
        del request.user.is_authenticated
        
        result = permission.has_permission(request, None)
        
        assert result is False
    
    def test_has_object_permission_safe_methods_get(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que permet lectura (GET) a qualsevol usuari autenticat"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.get('/api/users/test_uid/')
        request.user = mock_firebase_user
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is True
    
    def test_has_object_permission_safe_methods_options(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que permet OPTIONS a qualsevol usuari autenticat"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.options('/api/users/test_uid/')
        request.user = mock_firebase_user
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is True
    
    def test_has_object_permission_owner_can_write(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que permet escriptura al propietari"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.put('/api/users/test_uid/')
        request.user = mock_firebase_user
        
        # L'usuari i l'objecte tenen el mateix UID
        assert request.user.uid == mock_object_with_uid.uid
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is True
    
    def test_has_object_permission_non_owner_cannot_write(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que denega escriptura a no propietari"""
        permission = IsOwnerOrReadOnly()
        request = api_request_factory.put('/api/users/another_uid/')
        request.user = mock_firebase_user
        
        # Canvia l'UID de l'objecte per simular un altre usuari
        mock_object_with_uid.uid = 'another_uid'
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is False


class TestIsOwner:
    """Tests per al permís IsOwner"""
    
    def test_has_permission_authenticated_user(self, api_request_factory, mock_firebase_user):
        """Test que permet accés a usuari autenticat"""
        permission = IsOwner()
        request = api_request_factory.get('/api/users/')
        request.user = mock_firebase_user
        
        result = permission.has_permission(request, None)
        
        assert result is True
    
    def test_has_permission_unauthenticated_user(self, api_request_factory):
        """Test que denega accés a usuari no autenticat"""
        permission = IsOwner()
        request = api_request_factory.get('/api/users/')
        request.user = None
        
        result = permission.has_permission(request, None)
        
        # El permís retorna None (que és Falsy) o False per usuari no autenticat
        assert not result
    
    def test_has_object_permission_owner(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que permet accés al propietari"""
        permission = IsOwner()
        request = api_request_factory.get('/api/users/test_uid/')
        request.user = mock_firebase_user
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is True
    
    def test_has_object_permission_non_owner(self, api_request_factory, mock_firebase_user, mock_object_with_uid):
        """Test que denega accés a no propietari"""
        permission = IsOwner()
        request = api_request_factory.get('/api/users/another_uid/')
        request.user = mock_firebase_user
        
        # Canvia l'UID de l'objecte
        mock_object_with_uid.uid = 'another_uid'
        
        result = permission.has_object_permission(request, None, mock_object_with_uid)
        
        assert result is False
    
    def test_has_object_permission_object_without_uid(self, api_request_factory, mock_firebase_user):
        """Test que denega accés si l'objecte no té UID"""
        permission = IsOwner()
        request = api_request_factory.get('/api/users/test_uid/')
        request.user = mock_firebase_user
        
        # Objecte sense atribut uid
        obj = Mock(spec=[])
        
        result = permission.has_object_permission(request, None, obj)
        
        assert result is False


class TestIsSameUser:
    """Tests per al permís IsSameUser"""
    
    def test_has_permission_unauthenticated_user(self, api_request_factory, mock_view):
        """Test que denega accés a usuari no autenticat"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/')
        request.user = None
        
        result = permission.has_permission(request, mock_view)
        
        assert result is False
    
    def test_has_permission_user_without_is_authenticated(self, api_request_factory, mock_view):
        """Test que denega accés a usuari sense is_authenticated"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/')
        request.user = Mock()
        del request.user.is_authenticated
        
        result = permission.has_permission(request, mock_view)
        
        assert result is False
    
    def test_has_permission_same_user_with_uid_in_url(self, api_request_factory, mock_firebase_user, mock_view):
        """Test que permet accés quan l'UID de la URL coincideix amb l'usuari"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/test_uid_12345/')
        request.user = mock_firebase_user
        mock_view.kwargs = {'uid': 'test_uid_12345'}
        
        result = permission.has_permission(request, mock_view)
        
        assert result is True
    
    def test_has_permission_different_user_with_uid_in_url(self, api_request_factory, mock_firebase_user, mock_view):
        """Test que denega accés quan l'UID de la URL no coincideix"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/another_uid/')
        request.user = mock_firebase_user
        mock_view.kwargs = {'uid': 'another_uid'}
        
        result = permission.has_permission(request, mock_view)
        
        assert result is False
    
    def test_has_permission_no_uid_in_url(self, api_request_factory, mock_firebase_user, mock_view):
        """Test que permet accés quan no hi ha UID a la URL"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/')
        request.user = mock_firebase_user
        mock_view.kwargs = {}
        
        result = permission.has_permission(request, mock_view)
        
        assert result is True
    
    def test_has_permission_authenticated_collection_endpoint(self, api_request_factory, mock_firebase_user, mock_view):
        """Test que permet accés a endpoints de col·lecció si està autenticat"""
        permission = IsSameUser()
        request = api_request_factory.get('/api/users/')
        request.user = mock_firebase_user
        mock_view.kwargs = {}  # Sense UID
        
        result = permission.has_permission(request, mock_view)
        
        assert result is True


# ============= TESTS D'INTEGRACIÓ =============

class TestAuthenticationIntegration:
    """Tests d'integració entre middleware, authentication i permissions"""
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_full_authentication_flow(self, mock_verify, request_factory, valid_token, decoded_token):
        """Test del flux complet: middleware -> authentication -> permissions"""
        mock_verify.return_value = decoded_token
        
        # 1. Middleware processa la request
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/test_uid_12345/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        middleware_result = middleware.process_request(request)
        assert middleware_result is None
        assert hasattr(request, 'firebase_user')
        assert hasattr(request, 'user_uid')
        
        # 2. Authentication utilitza les dades del middleware
        auth_backend = FirebaseAuthentication()
        auth_result = auth_backend.authenticate(request)
        assert auth_result is not None
        user, token = auth_result
        
        # 3. Permissions comproven l'usuari
        permission = IsSameUser()
        mock_view = Mock()
        mock_view.kwargs = {'uid': 'test_uid_12345'}
        
        # Assigna l'usuari autenticat a la request
        request.user = user
        
        permission_result = permission.has_permission(request, mock_view)
        assert permission_result is True
    
    @patch('api.middleware.firebase_auth_middleware.auth.verify_id_token')
    def test_authentication_fails_for_different_user(self, mock_verify, request_factory, valid_token, decoded_token):
        """Test que l'autenticació falla quan l'usuari intenta accedir a dades d'un altre"""
        mock_verify.return_value = decoded_token
        
        # 1. Middleware processa la request
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/another_uid/')
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {valid_token}'
        
        middleware_result = middleware.process_request(request)
        assert middleware_result is None
        
        # 2. Authentication
        auth_backend = FirebaseAuthentication()
        auth_result = auth_backend.authenticate(request)
        user, token = auth_result
        
        # 3. Permissions denegen l'accés
        permission = IsSameUser()
        mock_view = Mock()
        mock_view.kwargs = {'uid': 'another_uid'}
        request.user = user
        
        permission_result = permission.has_permission(request, mock_view)
        assert permission_result is False
    
    def test_middleware_blocks_unauthenticated_request(self, request_factory):
        """Test que el middleware bloqueja requests sense autenticació"""
        middleware = FirebaseAuthenticationMiddleware(get_response=lambda r: None)
        request = request_factory.get('/api/users/test_uid/')
        
        result = middleware.process_request(request)
        
        assert isinstance(result, JsonResponse)
        assert result.status_code == status.HTTP_401_UNAUTHORIZED

