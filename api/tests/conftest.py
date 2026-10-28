"""
Fixtures i configuració compartida per als tests amb pytest
"""
# IMPORTANT: Configurar variables d'entorn ABANS de qualsevol import de mòduls de l'API
# Això és necessari perquè alguns mòduls llegeixen les variables a nivell de mòdul
import os
os.environ['TESTING'] = 'true'
os.environ['R2_ACCESS_KEY_ID'] = 'test_access_key'
os.environ['R2_SECRET_ACCESS_KEY'] = 'test_secret_key'
os.environ['R2_ENDPOINT'] = 'https://test.r2.cloudflarestorage.com'
os.environ['R2_BUCKET_NAME'] = 'test-bucket'

import pytest
from unittest.mock import Mock, MagicMock, patch
from api.utils.timezone_utils import get_madrid_now


# ============= CONFIGURACIÓ GLOBAL =============

DEPARTMENT = 'Ariège'


@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """
    Configuració global que s'executa una vegada al principi de tots els tests.
    Les variables d'entorn ja estan configurades a l'inici del mòdul.
    """
    yield
    # No fem cleanup de les variables d'entorn ja que altres tests podrien necessitar-les


@pytest.fixture
def multiple_users_data():
    """Múltiples usuaris per tests"""
    return [
        {
            'uid': 'uid_001',
            'username': 'user1',
            'language': 'ca',
            'created_at': get_madrid_now().isoformat()
        },
        {
            'uid': 'uid_002',
            'username': 'user2',
            'language': 'es',
            'created_at': get_madrid_now().isoformat()
        },
        {
            'uid': 'uid_003',
            'username': 'user3',
            'language': 'en',
            'created_at': get_madrid_now().isoformat()
        }
    ]


@pytest.fixture
def invalid_user_data():
    """Dades d'usuari invàlides per tests"""
    return [
        {'uid': ''},  # UID buit
        {'uid': 'test_uid', 'language': 'invalid_lang'}  # Idioma invàlid
    ]





# ============= FIXTURES DE REQUEST/RESPONSE =============

@pytest.fixture
def mock_request():
    """Mock d'un request de Django REST Framework"""
    request = MagicMock()
    request.user_uid = 'test_uid_12345'
    request.user = MagicMock()
    request.user.is_authenticated = True
    request.user.uid = 'test_uid_12345'
    request.data = {}
    request.GET = {}
    return request


@pytest.fixture
def mock_api_view_request():
    """Mock d'un request per APIView"""
    from rest_framework.test import APIRequestFactory
    factory = APIRequestFactory()
    request = factory.get('/')
    request.user_uid = 'test_uid_12345'
    return request


@pytest.fixture
def authenticated_client():
    """
    Client de test amb autenticació mockejada.
    Mockeja el middleware de Firebase i els permisos per permetre requests autenticades.
    """
    from rest_framework.test import APIClient
    
    with patch('api.middleware.firebase_auth_middleware.FirebaseAuthenticationMiddleware.process_request') as mock_middleware:
        # El middleware no fa res (simula autenticació exitosa)
        mock_middleware.return_value = None
        
        with patch('api.permissions.IsAuthenticated.has_permission') as mock_auth_permission:
            mock_auth_permission.return_value = True
            
            with patch('api.permissions.IsSameUser.has_permission') as mock_same_user_permission:
                mock_same_user_permission.return_value = True
                
                client = APIClient()
                # Afegeix els atributs que el middleware normalment afegiria
                yield client


@pytest.fixture
def mock_authenticated_request():
    """
    Mock de request amb autenticació completa per usar amb APIView directament.
    Inclou tots els atributs que el middleware i l'autenticació afegirien.
    """
    from rest_framework.test import APIRequestFactory
    
    factory = APIRequestFactory()
    
    def _create_request(method='get', path='/', data=None, uid='test_uid_12345'):
        if method.lower() == 'get':
            request = factory.get(path, data or {})
        elif method.lower() == 'post':
            request = factory.post(path, data or {}, format='json')
        elif method.lower() == 'patch':
            request = factory.patch(path, data or {}, format='json')
        elif method.lower() == 'delete':
            request = factory.delete(path)
        else:
            request = factory.get(path)
        
        # Afegeix els atributs que el middleware de Firebase afegeix
        request.user_uid = uid
        request.firebase_user = {'uid': uid}
        
        # Mock de l'usuari autenticat de DRF
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.uid = uid
        
        return request
    
    return _create_request







# ============= FIXTURES DE VALIDACIÓ =============

@pytest.fixture
def valid_languages():
    """Llista d'idiomes vàlids"""
    return ['ca', 'es', 'en', 'fr']


@pytest.fixture
def invalid_languages():
    """Llista d'idiomes invàlids"""
    return ['invalid', 'pt', 'de', 'it', '']


# ============= HELPERS =============

@pytest.fixture
def assert_user_equals():
    """Helper per comparar usuaris"""
    def _assert_equals(user1, user2):
        assert user1.uid == user2.uid
        assert user1.username == user2.username
        assert user1.language == user2.language
    return _assert_equals


# ============= FIXTURES COMPARTIDES =============
# L'aïllament (Firestore bloquejat, audit i permisos mockejats), la infraestructura Postgres (`django_db_setup`,
# `app_db`, `migrator_db`, marker `db_infra`) i el hook de RLS viuen al `conftest.py` de l'arrel perquè els
# tests de les apps (`apps/*/tests`) també els necessiten.
from apps.core.testing import fetch_all, fetch_one  # noqa: E402,F401  (reexportats per als tests existents)
