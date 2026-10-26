"""
Errors 500 de les vistes de visites (CLAUDE.md gotcha 14): `{error: <missatge fix>, error_id}`, `error_id` al log amb la
traça i cap text de l'excepcio a la resposta. Missatges (contracte):

    GET  /refuges/{id}/visits/    «Error en obtenir les visites del refugi»      (`services.get_refuge_visits`)
    GET  /users/{uid}/visits/     «Error en obtenir les visites de l'usuari»     (`services.get_user_visits`)
    POST                          «Error en registrar la visita»                  (`services.create_visit`)
    PATCH                         «Error en actualitzar la visita»                (`services.update_visit`)
    DELETE                        «Error en esborrar el visitant de la visita»    (`services.remove_visitor`)

Les vistes han de fer `from . import services` (es mocka `apps.visits.views.services.<funcio>`).
"""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.visits.tests.helpers import (
    api_delete, api_get, api_patch, api_post, day, make_refuge, make_user, make_visit, participant_rows,
    refuge_visits_url, user_claims, user_visits_url, visit_url)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SECRET = 'SELECT secret FROM host=db.neon.tech bucket=prod-bucket'
P = 'apps.visits.views.services.'


def assert_traced(response, message, caplog):
    assert response.status_code == 500
    body = response.json()
    assert body['error'] == message and set(body) == {'error', 'error_id'}
    assert SECRET not in response.content.decode() and 'Error:' not in body['error']
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records), 'error_id al log amb traça'


@pytest.fixture
def scene():
    make_user('u1')
    return make_refuge()


CASES = [
    ('get_refuge_visits', 'Error en obtenir les visites del refugi', 'get', 'refuge', None),
    ('get_user_visits', "Error en obtenir les visites de l'usuari", 'get', 'user', None),
    ('create_visit', 'Error en registrar la visita', 'post', 'detail', {'num_visitors': 1}),
    ('update_visit', 'Error en actualitzar la visita', 'patch', 'detail', {'num_visitors': 1}),
    ('remove_visitor', 'Error en esborrar el visitant de la visita', 'delete', 'detail', None),
]


def do(client, r, kind, method, payload):
    path = {'refuge': refuge_visits_url(r.pk), 'user': user_visits_url('u1'),
            'detail': visit_url(r.pk, day(3))}[kind]
    fn = {'get': api_get, 'post': api_post, 'patch': api_patch, 'delete': api_delete}[method]
    return fn(client, path, user_claims('u1'), payload) if payload is not None else fn(client, path, user_claims('u1'))


@pytest.mark.parametrize('exc', [DatabaseError(SECRET), RuntimeError(SECRET)])
@pytest.mark.parametrize('func,message,method,kind,payload', CASES)
def test_error_inesperat_500_amb_error_id(client, scene, caplog, func, message, method, kind, payload, exc):
    with patch(P + func, side_effect=exc), caplog.at_level(logging.ERROR):
        assert_traced(do(client, scene, kind, method, payload), message, caplog)


def test_un_error_de_bd_no_deixa_escriptures_a_mitges(client, scene):
    """El POST fa atomic: si el participant falla no queda la visita orfena."""
    from apps.visits import services
    from apps.visits.tests.helpers import visit_rows
    with patch.object(services, 'create_visit', side_effect=DatabaseError(SECRET)):
        assert api_post(client, visit_url(scene.pk, day(3)), user_claims('u1'), {'num_visitors': 1}).status_code == 500
    assert visit_rows() == []


def test_les_excepcions_de_domini_no_son_500(client, scene):
    vid = make_visit(scene, day(3), {'u1': 1})
    assert api_post(client, visit_url(scene.pk, day(3)), user_claims('u1'), {'num_visitors': 1}).status_code == 400
    assert api_delete(client, visit_url(scene.pk, day(9)), user_claims('u1')).status_code == 404
    assert participant_rows(vid) == {'u1': 1}
