"""
Health check del chunk 11 (D43): només PostgreSQL i Firebase Admin; sense Firestore, Redis ni R2.

Contracte de `GET /api/health/` (AllowAny):
- 200 `{status: 'healthy', message, firebase: true, database: true}` (exactament aquestes claus);
- 503 `{status: 'unhealthy', message, firebase, database}` si PostgreSQL no respon o Firebase Admin no
  està inicialitzat (comprovació local, `firebase_admin.get_app()`, sense crida de xarxa);
- ja no hi ha `firestore` ni `collections_count`; mai es filtra el text d'una excepció.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.db.utils import OperationalError

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db]

URL = '/api/health/'
KEYS = {'status', 'message', 'firebase', 'database'}
SECRET = 'SECRET-HOST-9f3a:5432 password=hunter2'


@pytest.fixture
def firebase_inicialitzat():
    """Simula una app de Firebase Admin ja inicialitzada (sense xarxa ni credencials)."""
    app = MagicMock(name='firebase_app')
    with patch('firebase_admin.get_app', return_value=app), \
            patch('firebase_admin._apps', {'[DEFAULT]': app}):
        yield


@pytest.fixture
def firebase_no_inicialitzat():
    with patch('firebase_admin.get_app', side_effect=ValueError(SECRET)), \
            patch('firebase_admin._apps', {}):
        yield


@pytest.fixture
def sense_xarxa_ni_r2(monkeypatch):
    """Si el health toca R2, Firestore o una crida d'Auth, el test falla."""
    for v in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_ENDPOINT', 'R2_BUCKET_NAME'):
        monkeypatch.delenv(v, raising=False)
    boom = AssertionError('el health check no ha de fer crides externes')
    with patch('boto3.client', side_effect=boom), \
            patch('boto3.session.Session.client', side_effect=boom), \
            patch('google.cloud.firestore.Client', side_effect=boom), \
            patch('firebase_admin.auth.get_user', side_effect=boom), \
            patch('firebase_admin.auth.list_users', side_effect=boom), \
            patch('firebase_admin.auth.verify_id_token', side_effect=boom):
        yield


def _db_falla_nomes_per_select_1():
    from django.db.backends.utils import CursorWrapper
    original = CursorWrapper.execute

    def execute(self, sql, params=None):
        if str(sql).strip().rstrip(';').strip().upper() == 'SELECT 1':
            raise OperationalError(SECRET)
        return original(self, sql, params)

    return patch.object(CursorWrapper, 'execute', execute)


def test_health_200_amb_les_claus_exactes(client, firebase_inicialitzat, sense_xarxa_ni_r2):
    r = client.get(URL)
    assert r.status_code == 200
    j = r.json()
    assert set(j) == KEYS
    assert j['status'] == 'healthy'
    assert j['firebase'] is True and j['database'] is True
    assert isinstance(j['message'], str) and j['message']


def test_health_ja_no_exposa_firestore_ni_collections_count(client, firebase_inicialitzat):
    j = client.get(URL).json()
    assert 'firestore' not in j and 'collections_count' not in j


def test_health_no_requereix_autenticacio(client, firebase_inicialitzat):
    assert client.get(URL).status_code == 200


def test_health_executa_select_1(client, firebase_inicialitzat):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as q:
        client.get(URL)
    assert any(x['sql'].strip().upper() == 'SELECT 1' for x in q.captured_queries)


def test_health_503_si_la_base_de_dades_falla(client, firebase_inicialitzat):
    with _db_falla_nomes_per_select_1():
        r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert set(j) == KEYS
    assert j['status'] == 'unhealthy'
    assert j['database'] is False


def test_health_503_i_no_500_si_la_comprovacio_de_bd_llanca_un_error_inesperat(client, firebase_inicialitzat):
    """Un error que no és de BD (p. ex. del driver) també és «BD no disponible»: 503 documentat, mai 500."""
    from unittest.mock import MagicMock
    broken = MagicMock()
    broken.cursor.side_effect = RuntimeError(SECRET)
    with patch('api.services.database_health.connection', broken):   # només la connexió del health check
        r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert set(j) == KEYS and j['database'] is False and SECRET not in r.content.decode()


def test_health_503_si_firebase_admin_no_esta_inicialitzat(client, firebase_no_inicialitzat):
    r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert set(j) == KEYS
    assert j['status'] == 'unhealthy'
    assert j['firebase'] is False
    assert j['database'] is True


def test_health_503_i_tot_fals_si_cau_tot(client, firebase_no_inicialitzat):
    with _db_falla_nomes_per_select_1():
        r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert j['status'] == 'unhealthy' and j['firebase'] is False and j['database'] is False


def test_health_no_filtra_el_text_de_les_excepcions(client, firebase_no_inicialitzat):
    with _db_falla_nomes_per_select_1():
        body = client.get(URL).content.decode()
    assert 'SECRET' not in body and 'hunter2' not in body and 'postgres://' not in body


def test_health_no_filtra_errors_inesperats_de_firebase(client):
    with patch('firebase_admin.get_app', side_effect=RuntimeError(SECRET)), \
            patch('firebase_admin._apps', {}):
        r = client.get(URL)
    assert r.status_code == 503
    assert 'SECRET' not in r.content.decode()


def test_health_no_usa_firestore_ni_r2(client, firebase_inicialitzat, sense_xarxa_ni_r2):
    assert client.get(URL).status_code == 200


def test_health_no_depen_de_redis(client, firebase_inicialitzat):
    """Sense cache externa: el health no ha de provar de connectar a cap Redis."""
    with patch('socket.create_connection', side_effect=AssertionError('xarxa')):
        assert client.get(URL).status_code == 200
