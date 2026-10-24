"""Hook per petició (§7.3): `set_config` a APIView.initial, dins la transacció, derivat del token verificat."""
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.response import Response

from api.views.health_check_views import HealthCheckAPIView

pytestmark = [pytest.mark.db_infra, pytest.mark.rls, pytest.mark.django_db]

VERIFY = 'api.middleware.firebase_auth_middleware.auth.verify_id_token'
HEALTH = '/api/health/'


def _quien(self, request, *a, **kw):
    """Vista de prova (substitueix `get` del health): torna el context RLS que veu la BD."""
    from django.db import connection as c
    with c.cursor() as cur:
        cur.execute('SELECT core.uid(), core.is_admin(), core.is_system()')
        uid, adm, sys_ = cur.fetchone()
    return Response({'uid': uid, 'is_admin': adm, 'is_system': sys_,
                     'in_atomic': connection.in_atomic_block})


@pytest.fixture
def quien():
    with patch.object(HealthCheckAPIView, 'get', _quien):
        yield


def _get(client, claims=None, path=HEALTH, **extra):
    if claims is None:
        return client.get(path, **extra)
    with patch(VERIFY, return_value=claims):
        return client.get(path, HTTP_AUTHORIZATION='Bearer tok', **extra)


def test_anonim_uid_null_i_no_admin(client, quien):
    r = _get(client)
    assert r.status_code == 200
    assert (r.json()['uid'], r.json()['is_admin'], r.json()['is_system']) == (None, False, False)


def test_usuari_autenticat_fixa_uid(client, quien):
    j = _get(client, {'uid': 'u-normal', 'role': 'user'}).json()
    assert (j['uid'], j['is_admin'], j['is_system']) == ('u-normal', False, False)


def test_admin_nomes_si_el_claim_role_es_admin(client, quien):
    j = _get(client, {'uid': 'u-adm', 'role': 'admin'}).json()
    assert (j['uid'], j['is_admin']) == ('u-adm', True)


@pytest.mark.parametrize('claims', [
    {'uid': 'u', 'role': 'ADMIN'},
    {'uid': 'u', 'role': 'administrator'},
    {'uid': 'u', 'admin': True},
    {'uid': 'u', 'is_admin': True},
    {'uid': 'u', 'role': ['admin']},
    {'uid': 'u'},
])
def test_claims_que_no_son_role_admin_no_donen_admin(client, quien, claims):
    assert _get(client, claims).json()['is_admin'] is False


def test_admin_no_es_pot_falsificar_amb_capcaleres_query_ni_cos(client, quien):
    claims = {'uid': 'u-normal', 'role': 'user'}
    j = _get(client, claims, path=HEALTH + '?is_admin=true&role=admin&app.is_admin=true',
             HTTP_X_IS_ADMIN='true', HTTP_X_ROLE='admin', HTTP_X_USER_ROLE='admin', HTTP_X_UID='altre').json()
    assert j['is_admin'] is False
    assert j['uid'] == 'u-normal', "l'uid ve només del token verificat"


def test_anonim_no_pot_falsificar_uid_ni_admin_amb_capcaleres(client, quien):
    j = _get(client, None, path=HEALTH + '?uid=victima&is_admin=true', HTTP_X_UID='victima', HTTP_X_IS_ADMIN='true').json()
    assert (j['uid'], j['is_admin']) == (None, False)


def test_is_system_sempre_false_en_una_peticio(client, quien):
    """Encara que la transacció envoltant tingués is_system=true, la petició el reinicia."""
    from apps.core.rls import system_context
    with system_context():
        j = _get(client, {'uid': 'u1', 'role': 'admin'}).json()
    assert j['is_system'] is False


def test_el_context_no_es_filtra_entre_peticions_consecutives(client, quien):
    a = _get(client, {'uid': 'u-adm', 'role': 'admin'}).json()
    b = _get(client).json()
    c = _get(client, {'uid': 'u2', 'role': 'user'}).json()
    assert (a['uid'], a['is_admin']) == ('u-adm', True)
    assert (b['uid'], b['is_admin']) == (None, False)
    assert (c['uid'], c['is_admin']) == ('u2', False)


def test_uid_hostil_es_parametritza(client, quien):
    raro = "u'); DROP TABLE x;--"
    assert _get(client, {'uid': raro, 'role': 'user'}).json()['uid'] == raro


def test_la_peticio_s_executa_dins_d_una_transaccio(client, quien):
    assert _get(client).json()['in_atomic'] is True


def test_una_sola_sentencia_set_config_per_peticio(client, quien):
    with CaptureQueriesContext(connection) as q:
        _get(client, {'uid': 'u1', 'role': 'admin'})
    cfg = [x['sql'] for x in q.captured_queries if 'set_config' in x['sql']]
    assert len(cfg) == 1, cfg
    sql = cfg[0]
    for setting in ('app.uid', 'app.is_admin', 'app.is_system'):
        assert setting in sql
    assert sql.replace(' ', '').count(',true)') == 3, \
        "els tres set_config han de ser locals a la transacció (is_local = true)"


def test_set_config_s_executa_abans_de_la_vista(client, quien):
    with CaptureQueriesContext(connection) as q:
        _get(client, {'uid': 'u1', 'role': 'user'})
    sqls = [x['sql'] for x in q.captured_queries]
    i_cfg = next(i for i, s in enumerate(sqls) if 'set_config' in s)
    i_view = next(i for i, s in enumerate(sqls) if 'core.uid()' in s)
    assert i_cfg < i_view


def test_token_invalid_no_arriba_a_la_vista_ni_fixa_context(client, quien):
    from firebase_admin import auth
    with patch(VERIFY, side_effect=auth.InvalidIdTokenError('mal')):
        r = client.get(HEALTH, HTTP_AUTHORIZATION='Bearer dolent')
    assert r.status_code == 401
