"""Health check amb Postgres: manté la forma JSON actual, hi afegeix `database` i no depèn d'R2 (TECH_DEBT B4)."""
from unittest.mock import patch

import pytest
from django.db.utils import OperationalError

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db]

URL = '/api/health/'
FIRESTORE_OK = {'firebase': True, 'firestore': True, 'collections_count': 7}


@pytest.fixture
def sense_r2(monkeypatch):
    """Si el health toca R2 (client/servei/variables) el test falla."""
    for v in ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_ENDPOINT', 'R2_BUCKET_NAME'):
        monkeypatch.delenv(v, raising=False)
    boom = AssertionError("el health check no ha de dependre d'R2")
    with patch('api.services.r2_media_service.get_refugi_media_service', side_effect=boom), \
            patch('boto3.client', side_effect=boom), \
            patch('boto3.session.Session.client', side_effect=boom):
        yield


@pytest.fixture
def firestore_ok():
    with patch('api.daos.refugi_lliure_dao.RefugiLliureDAO.health_check', return_value=FIRESTORE_OK):
        yield


def _db_falla_nomes_per_select_1():
    from django.db.backends.utils import CursorWrapper
    original = CursorWrapper.execute

    def execute(self, sql, params=None):
        if str(sql).strip().rstrip(';').strip().upper() == 'SELECT 1':
            raise OperationalError('connection refused (simulat)')
        return original(self, sql, params)

    return patch.object(CursorWrapper, 'execute', execute)


def test_health_ok_amb_database_i_forma_existent(client, sense_r2, firestore_ok):
    r = client.get(URL)
    assert r.status_code == 200
    j = r.json()
    assert j['status'] == 'healthy'
    assert j['database'] is True
    # forma existent intacta
    assert j['firebase'] is True and j['firestore'] is True and j['collections_count'] == 7
    assert isinstance(j['message'], str)


def test_health_executa_select_1(client, sense_r2, firestore_ok):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as q:
        client.get(URL)
    assert any(x['sql'].strip().upper() == 'SELECT 1' for x in q.captured_queries)


def test_health_503_si_la_base_de_dades_falla(client, sense_r2, firestore_ok):
    with _db_falla_nomes_per_select_1():
        r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert j['status'] == 'unhealthy'
    assert j['database'] is False
    assert 'message' in j


def test_health_no_filtra_detalls_de_connexio(client, sense_r2, firestore_ok):
    with _db_falla_nomes_per_select_1():
        body = client.get(URL).content.decode()
    assert 'postgres://' not in body and 'password' not in body.lower()


def test_health_no_requereix_r2_ni_variables_r2(client, sense_r2, firestore_ok):
    """B4: abans es creava el controller (i el client R2) per atendre el health."""
    assert client.get(URL).status_code == 200


def test_health_no_requereix_autenticacio(client, sense_r2, firestore_ok):
    assert client.get(URL).status_code == 200


def test_health_amb_firestore_caigut_segueix_informant_database(client, sense_r2):
    with patch('api.daos.refugi_lliure_dao.RefugiLliureDAO.health_check', side_effect=RuntimeError('firestore down')):
        r = client.get(URL)
    assert r.status_code == 503
    j = r.json()
    assert j['status'] == 'unhealthy'
    assert j.get('database') is True
