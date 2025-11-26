"""
Fixtures i configuració compartida per als tests amb pytest
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from api.models.user import User
from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria, RefugiSearchFilters
from api.utils.timezone_utils import get_madrid_now


# ============= CONFIGURACIÓ GLOBAL =============

EMAIL = 'test@example.com'
DEPARTMENT = 'Ariège'


@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """
    Configuració global que s'executa una vegada al principi de tots els tests.
    Assegura que Firebase no s'inicialitza durant els tests.
    """
    import os
    os.environ['TESTING'] = 'true'
    yield
    # Cleanup
    if 'TESTING' in os.environ:
        del os.environ['TESTING']


# ============= FIXTURES D'USUARIS =============

@pytest.fixture
def sample_user_data():
    """Dades d'usuari de mostra per tests"""
    return {
        'uid': 'test_uid_12345',
        'username': 'testuser',
        'email': EMAIL,
        'avatar': 'https://example.com/avatar.jpg',
        'language': 'ca',
        'favourite_refuges': [],
        'visited_refuges': [],
        'renovations': [],
        'num_uploaded_photos': 0,
        'num_shared_experiences': 0,
        'num_renovated_refuges': 0,
        'created_at': get_madrid_now().isoformat()
    }


@pytest.fixture
def sample_user(sample_user_data):
    """Instància de User per tests"""
    return User.from_dict(sample_user_data)


@pytest.fixture
def multiple_users_data():
    """Múltiples usuaris per tests"""
    return [
        {
            'uid': 'uid_001',
            'username': 'user1',
            'email': 'user1@example.com',
            'language': 'ca',
            'created_at': get_madrid_now().isoformat()
        },
        {
            'uid': 'uid_002',
            'username': 'user2',
            'email': 'user2@example.com',
            'language': 'es',
            'created_at': get_madrid_now().isoformat()
        },
        {
            'uid': 'uid_003',
            'username': 'user3',
            'email': 'user3@example.com',
            'language': 'en',
            'created_at': get_madrid_now().isoformat()
        }
    ]


@pytest.fixture
def invalid_user_data():
    """Dades d'usuari invàlides per tests"""
    return [
        {'uid': '', 'email': EMAIL},  # UID buit
        {'uid': 'test_uid', 'email': ''},  # Email buit
        {'uid': 'test_uid', 'email': 'invalid_email'},  # Email sense @
        {'uid': 'test_uid', 'email': EMAIL, 'language': 'invalid_lang'}  # Idioma invàlid
    ]


# ============= FIXTURES DE REFUGIS =============

@pytest.fixture
def sample_coordinates():
    """Coordenades de mostra"""
    return Coordinates(long=1.5, lat=42.5)


@pytest.fixture
def sample_info_complementaria():
    """Informació complementària de mostra"""
    return InfoComplementaria(
        cheminee=1,
        poele=0,
        couvertures=1,
        latrines=1,
        bois=1,
        eau=0,
        matelas=1,
        couchage=5,
        lits=2
    )


@pytest.fixture
def sample_refugi_data(sample_coordinates, sample_info_complementaria):
    """Dades de refugi de mostra"""
    return {
        'id': 'refugi_001',
        'name': 'Refugi Test',
        'coord': sample_coordinates.to_dict(),
        'altitude': 2000,
        'places': 10,
        'remarque': 'Comentari de prova',
        'info_comp': sample_info_complementaria.to_dict(),
        'description': 'Descripció del refugi de prova',
        'links': ['https://example.com'],
        'type': 'garde',
        'modified_at': get_madrid_now().isoformat(),
        'region': 'Pirineus',
        'departement': DEPARTMENT
    }


@pytest.fixture
def sample_refugi(sample_refugi_data):
    """Instància de Refugi per tests"""
    return Refugi.from_dict(sample_refugi_data)


@pytest.fixture
def multiple_refugis_data():
    """Múltiples refugis per tests"""
    return [
        {
            'id': 'refugi_001',
            'name': 'Refugi A',
            'coord': {'long': 1.5, 'lat': 42.5},
            'altitude': 2000,
            'places': 10,
            'remarque': '',
            'info_comp': {
                'cheminee': 1, 'poele': 0, 'couvertures': 1,
                'latrines': 1, 'bois': 1, 'eau': 0,
                'matelas': 1, 'couchage': 5, 'lits': 2,
                'bas_flancs': 0, 'mezzanine/etage': 0, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'garde',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': DEPARTMENT
        },
        {
            'id': 'refugi_002',
            'name': 'Refugi B',
            'coord': {'long': 1.6, 'lat': 42.6},
            'altitude': 2500,
            'places': 15,
            'remarque': '',
            'info_comp': {
                'cheminee': 0, 'poele': 1, 'couvertures': 1,
                'latrines': 1, 'bois': 0, 'eau': 1,
                'matelas': 0, 'couchage': 8, 'lits': 4,
                'bas_flancs': 0, 'mezzanine/etage': 1, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'no guardat',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': 'Haute-Garonne'
        },
        {
            'id': 'refugi_003',
            'name': 'Refugi C',
            'coord': {'long': 1.7, 'lat': 42.7},
            'altitude': 1800,
            'places': 6,
            'remarque': '',
            'info_comp': {
                'cheminee': 1, 'poele': 1, 'couvertures': 0,
                'latrines': 0, 'bois': 1, 'eau': 1,
                'matelas': 1, 'couchage': 4, 'lits': 1,
                'bas_flancs': 0, 'mezzanine/etage': 0, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'garde',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': DEPARTMENT
        }
    ]


@pytest.fixture
def invalid_refugi_data():
    """Dades de refugi invàlides per tests"""
    return [
        {'id': '', 'name': 'Test', 'coord': {'long': 1.5, 'lat': 42.5}},  # ID buit
        {'id': 'test_001', 'name': '', 'coord': {'long': 1.5, 'lat': 42.5}},  # Name buit
        {'id': 'test_001', 'name': 'Test', 'coord': None},  # Coordenades null
    ]


# ============= FIXTURES DE FILTRES =============

@pytest.fixture
def sample_search_filters():
    """Filtres de cerca de mostra"""
    return RefugiSearchFilters(
        name='Refugi Test',
        region='Pirineus',
        departement=DEPARTMENT,
        type='garde',
        places_min=5,
        places_max=15,
        altitude_min=1500,
        altitude_max=2500,
        cheminee=1,
        eau=1
    )


# ============= MOCKS DE FIRESTORE =============

@pytest.fixture
def mock_firestore_db():
    """Mock de la base de dades Firestore"""
    mock_db = MagicMock()
    
    # Mock collection
    mock_collection = MagicMock()
    mock_db.collection.return_value = mock_collection
    
    # Mock document
    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref
    
    # Mock document snapshot
    mock_doc_snapshot = MagicMock()
    mock_doc_snapshot.exists = True
    mock_doc_snapshot.id = 'test_id'
    mock_doc_ref.get.return_value = mock_doc_snapshot
    
    return mock_db


@pytest.fixture
def mock_firestore_service(mock_firestore_db):
    """Mock del FirestoreService"""
    with patch('api.services.firestore_service.FirestoreService') as MockFirestoreService:
        mock_instance = MockFirestoreService.return_value
        mock_instance.get_db.return_value = mock_firestore_db
        yield mock_instance


@pytest.fixture
def mock_cache_service():
    """Mock del CacheService"""
    with patch('api.services.cache_service.cache_service') as mock_cache:
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.generate_key.return_value = 'test_cache_key'
        mock_cache.get_timeout.return_value = 300
        yield mock_cache


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
        request.firebase_user = {'uid': uid, 'email': f'{uid}@example.com'}
        
        # Mock de l'usuari autenticat de DRF
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.uid = uid
        
        return request
    
    return _create_request


# ============= FIXTURES DE CONTROLLERS =============

@pytest.fixture
def mock_user_controller():
    """Mock del UserController"""
    with patch('api.controllers.user_controller.UserController') as MockController:
        yield MockController.return_value


@pytest.fixture
def mock_refugi_controller():
    """Mock del RefugiLliureController"""
    with patch('api.controllers.refugi_lliure_controller.RefugiLliureController') as MockController:
        yield MockController.return_value


# ============= FIXTURES DE DAOs =============

@pytest.fixture
def mock_user_dao():
    """Mock del UserDAO"""
    with patch('api.daos.user_dao.UserDAO') as MockDAO:
        yield MockDAO.return_value


@pytest.fixture
def mock_refugi_dao():
    """Mock del RefugiLliureDao"""
    with patch('api.daos.refugi_lliure_dao.RefugiLliureDao') as MockDAO:
        yield MockDAO.return_value


# ============= FIXTURES DE MAPPERS =============

@pytest.fixture
def user_mapper():
    """Instància real del UserMapper (no mockejada)"""
    from api.mappers.user_mapper import UserMapper
    return UserMapper()


@pytest.fixture
def refugi_mapper():
    """Instància real del RefugiLliureMapper (no mockejada)"""
    from api.mappers.refugi_lliure_mapper import RefugiLliureMapper
    return RefugiLliureMapper()


# ============= FIXTURES DE VALIDACIÓ =============

@pytest.fixture
def valid_emails():
    """Llista d'emails vàlids per tests"""
    return [
        EMAIL,
        'user.name@domain.co.uk',
        'first.last+tag@example.com',
        'test_user@test-domain.com'
    ]


@pytest.fixture
def invalid_emails():
    """Llista d'emails invàlids per tests"""
    return [
        'invalid_email',
        '@example.com',
        'test@',
        'test @example.com',
        '',
        None
    ]


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
        assert user1.email == user2.email
        assert user1.username == user2.username
        assert user1.language == user2.language
    return _assert_equals


@pytest.fixture
def assert_refugi_equals():
    """Helper per comparar refugis"""
    def _assert_equals(refugi1, refugi2):
        assert refugi1.id == refugi2.id
        assert refugi1.name == refugi2.name
        assert refugi1.coord.long == refugi2.coord.long
        assert refugi1.coord.lat == refugi2.coord.lat
        assert refugi1.altitude == refugi2.altitude
        assert refugi1.places == refugi2.places
    return _assert_equals
