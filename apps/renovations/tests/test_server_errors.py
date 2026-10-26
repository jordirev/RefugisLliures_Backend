"""
Errors 500 de les vistes de reformes (chunk 5; gotcha 14): cos `{error, error_id}`, missatge específic del punt que ha
fallat, `error_id` coincident amb el del log (amb la traça) i cap text d'excepció a la resposta.

La fallada s'injecta amb `connection.execute_wrapper`, de manera que els tests no depenen de com el servei fa l'accés a
la BD: qualsevol sentència del tipus indicat sobre les taules de reformes llança una excepció amb text «secret».
"""
import logging

import pytest
from django.db import DatabaseError, connection

from apps.renovations.tests.helpers import (
    LINK, RENOVATIONS, api_delete, api_get, api_patch, api_post, count_renovations, day, expelled_of, make_renovation,
    new_body, participants_of, reno_url, refuge_reno_url, renovation_row, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SECRET = 'SELECT secret FROM host=db.neon.tech bucket=prod-bucket'


def failing(prefix, table, exc=DatabaseError):
    """Wrapper que fa fallar les sentències `prefix ...` que mencionen `table`."""
    def wrapper(execute, sql, params, many, context):
        text = sql if isinstance(sql, str) else str(sql)
        if text.lstrip().upper().startswith(prefix) and table in text:
            raise exc(SECRET)
        return execute(sql, params, many, context)
    return wrapper


def assert_traced(response, caplog):
    assert response.status_code == 500, response.content
    body = response.json()
    assert set(body) == {'error', 'error_id'} and body['error']
    assert SECRET not in response.content.decode() and 'DatabaseError' not in body['error']
    assert 'Error:' not in body['error']
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records), \
        "l'error_id ha d'aparèixer al log amb la traça"


@pytest.fixture
def scene(world):
    world.rid = make_renovation(world.refuge, 'u1', ini=day(5), fin=day(9), participants=['u2'])
    return world


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_llista_amb_error(client, scene, caplog, exc):
    with connection.execute_wrapper(failing('SELECT', 'renovations', exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, RENOVATIONS, user_claims('u3')), caplog)


def test_detall_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('SELECT', 'renovations')), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, reno_url(scene.rid), user_claims('u3')), caplog)


def test_llista_de_refugi_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('SELECT', 'renovations')), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, refuge_reno_url(scene.refuge.pk), user_claims('u3')), caplog)


def test_crear_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('INSERT', 'activity"."renovations')), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, RENOVATIONS, user_claims('u1'),
                           new_body(scene.refuge, ini_date=day(30).isoformat(), fin_date=day(31).isoformat())), caplog)
    assert count_renovations() == 1


def test_editar_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('UPDATE', 'activity"."renovations')), caplog.at_level(logging.ERROR):
        assert_traced(api_patch(client, reno_url(scene.rid), user_claims('u1'), {'description': 'x'}), caplog)
    assert renovation_row(scene.rid)['description'] == 'Pintar la cabana'


def test_esborrar_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('DELETE', 'activity"."renovations')), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, reno_url(scene.rid), user_claims('u1')), caplog)
    assert renovation_row(scene.rid) is not None


def test_unir_se_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('INSERT', 'renovation_participants')), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, reno_url(scene.rid, 'participants'), user_claims('u3'), None), caplog)
    assert participants_of(scene.rid) == ['u2']


def test_sortir_amb_error(client, scene, caplog):
    with connection.execute_wrapper(failing('DELETE', 'renovation_participants')), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, reno_url(scene.rid, 'participants', 'u2'), user_claims('u2')), caplog)
    assert participants_of(scene.rid) == ['u2'] and expelled_of(scene.rid) == []


def test_els_errors_de_domini_no_son_500(client, scene):
    """Control: 404/403/409 no passen pel camí d'`error_id`."""
    assert api_get(client, reno_url(scene.rid), user_claims('u3')).status_code == 200
    r = api_post(client, reno_url(scene.rid, 'participants'), user_claims('u2'), None)
    assert r.status_code == 409 and 'error_id' not in r.json()
    assert LINK not in r.content.decode()
