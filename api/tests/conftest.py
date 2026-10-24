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
from api.models.user import User
from api.models.refugi_lliure import Refugi, Coordinates, InfoComplementaria, RefugiSearchFilters
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


# ============= FIXTURES D'USUARIS =============

@pytest.fixture
def sample_user_data():
    """Dades d'usuari de mostra per tests"""
    return {
        'uid': 'test_uid_12345',
        'username': 'testuser',
        'avatar': 'https://example.com/avatar.jpg',
        'language': 'ca',
        'favourite_refuges': [],
        'visited_refuges': [],
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
        'departement': DEPARTMENT,
        'condition': 2
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
                'bas_flancs': 0, 'mezzanine_etage': 0, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'garde',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': DEPARTMENT,
            'condition': 2
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
                'bas_flancs': 0, 'mezzanine_etage': 1, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'no guardat',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': 'Haute-Garonne',
            'condition': 1
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
                'bas_flancs': 0, 'mezzanine_etage': 0, 'manque_un_mur': 0
            },
            'description': '',
            'links': [],
            'type': 'garde',
            'modified_at': '',
            'region': 'Pirineus',
            'departement': DEPARTMENT,
            'condition': 2
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
        type=['garde'],
        condition=[2],
        places_min=5,
        places_max=15,
        altitude_min=1500,
        altitude_max=2500
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
        request.firebase_user = {'uid': uid}
        
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


# ============= AÏLLAMENT (feature images) =============
# 1) Cap test pot inicialitzar Firebase real (env/ pot contenir credencials de producció).
# 2) El registre d'auditoria es mocka per defecte (marker `real_audit_log` per provar-lo).
# 3) Les comprovacions IsNotBlocked / IsAgeConfirmed retornen un usuari confirmat i no
#    bloquejat per defecte (marker `real_permissions` per provar-les).

@pytest.fixture(autouse=True)
def _block_real_firestore():
    from api.services.firestore_service import FirestoreService

    def _forbidden(self):
        raise RuntimeError("Els tests no poden connectar-se a Firestore real: mocka FirestoreService")

    with patch.object(FirestoreService, '_initialize_firebase', _forbidden), \
            patch('firebase_admin.get_app', side_effect=ValueError('no app')):
        FirestoreService._db = None
        yield


@pytest.fixture(autouse=True)
def _mock_audit_log(request):
    if request.node.get_closest_marker('real_audit_log'):
        yield None
        return
    with patch('api.services.audit_log_service.AuditLogService.log', return_value=True) as mock_log:
        yield mock_log


@pytest.fixture(autouse=True)
def _mock_permission_user_lookup(request):
    if request.node.get_closest_marker('real_permissions'):
        yield None
        return
    user = User(uid='perm_user', username='perm', age_confirmed_at='2025-01-01T00:00:00+01:00',
                age_threshold=16, is_blocked=False)
    with patch('api.permissions.get_user_for_permissions', return_value=user) as mock_lookup:
        yield mock_lookup


# ============= INFRAESTRUCTURA POSTGRES (chunk 1) =============
# Els tests marcats `db_infra` necessiten el Postgres local (scripts/dev/setup_local_postgres.sh) i
# les variables TEST_DATABASE_URL_APP / TEST_DATABASE_URL_MIGRATOR. Només se salten si falten.
# Contracte per a l'implementador:
#   - alias `default` = rol `app` (ATOMIC_REQUESTS=True) i alias `migrator` = rol `migrator`;
#   - la fixture `django_db_setup` (pytest-django) s'ha de sobreescriure perquè apliqui les migracions amb
#     `migrator` sobre la BD de proves i deixi la connexió `default` com a `app` (sense crear `test_*`).

_PG_ENV_VARS = ('TEST_DATABASE_URL_APP', 'TEST_DATABASE_URL_MIGRATOR')


def pytest_collection_modifyitems(config, items):
    missing = [v for v in _PG_ENV_VARS if not os.environ.get(v)]
    if not missing:
        return
    skip = pytest.mark.skip(
        reason=f"Postgres local no configurat: falta {', '.join(missing)} "
               f"(executa scripts/dev/setup_local_postgres.sh i exporta les URLs)")
    for item in items:
        if item.get_closest_marker('db_infra'):
            item.add_marker(skip)


@pytest.fixture
def app_db(django_db_setup, django_db_blocker):
    """Connexió Django `default` (rol app) en autocommit, fora de la transacció de pytest-django.

    Cal per provar el context RLS local a la transacció: dins d'un `django_db` normal tot el test és
    una sola transacció i `set_config(..., true)` no moriria en sortir d'un `atomic()` intern.
    """
    from django.db import connections
    with django_db_blocker.unblock():
        conn = connections['default']
        assert conn.vendor == 'postgresql', f"`default` ha de ser Postgres, és {conn.vendor}"
        assert not conn.in_atomic_block
        yield conn


@pytest.fixture
def migrator_db(django_db_setup, django_db_blocker):
    """Connexió Django `migrator` (propietària dels objectes de domini), en autocommit."""
    from django.db import connections
    with django_db_blocker.unblock():
        if 'migrator' not in connections.databases:
            pytest.fail("L'alias de BD `migrator` no està definit a settings.DATABASES")
        yield connections['migrator']


def fetch_all(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(conn, sql, params=None):
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


@pytest.fixture(scope='session')
def django_db_setup(django_test_environment, django_db_blocker):
    """Sobreescriu la fixture de pytest-django (§6.5, §7 del disseny).

    Amb el Postgres local configurat (`TEST_DATABASE_URL_*`) no es crea cap `test_*`: s'apliquen les migracions
    amb el rol `migrator` sobre la BD de proves (idempotent) i la connexió `default` es manté com a `app`,
    de manera que la RLS s'aplica als tests. Sense Postgres es manté el comportament per defecte (SQLite).
    """
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections

    if 'migrator' in settings.DATABASES:
        # Els grants de sota només són per a la BD efímera de proves: mai contra un Postgres remot (p. ex. Neon).
        from refugis_lliures.settings import _LOCAL_DB_HOSTS
        host = settings.DATABASES['migrator'].get('HOST') or ''
        if host not in _LOCAL_DB_HOSTS and not host.endswith('.localhost'):
            pytest.exit(f'Els tests només poden córrer contra un Postgres local (HOST={host!r}).', returncode=2)
        with django_db_blocker.unblock():
            call_command('migrate', database='migrator', interactive=False, verbosity=0)
            # Només per als tests: alguns creen un `django.contrib.auth.User` per a `force_authenticate`. Aquestes
            # taules de Django (a `public`, del migrator) no formen part del disseny de domini ni dels grants de
            # producció (§7.2): el rol `app` hi accedeix només a la BD de proves.
            with connections['migrator'].cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user")
                for (table,) in cur.fetchall():
                    cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON public."{table}" TO app')
                cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' "
                            "AND sequenceowner = current_user")
                for (seq,) in cur.fetchall():
                    cur.execute(f'GRANT USAGE, SELECT ON SEQUENCE public."{seq}" TO app')
        yield
        with django_db_blocker.unblock():
            connections.close_all()
    else:
        from django.test.utils import setup_databases, teardown_databases
        with django_db_blocker.unblock():
            db_cfg = setup_databases(verbosity=0, interactive=False)
        yield
        with django_db_blocker.unblock():
            teardown_databases(db_cfg, verbosity=0)


@pytest.fixture(autouse=True)
def _rls_hook_sense_bd(request):
    """Els tests sense BD (vistes amb controllers mockejats) no poden executar el `set_config` del hook de RLS.

    El hook té els seus propis tests (marker `rls`) i els de BD (`django_db`, `db_infra`) l'executen de debò.
    """
    if any(request.node.get_closest_marker(m) for m in ('rls', 'django_db', 'db_infra')):
        yield
        return
    with patch('api.rls_hook.apply_context'):
        yield
