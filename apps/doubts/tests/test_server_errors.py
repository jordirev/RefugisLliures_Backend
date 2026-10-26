"""
Errors 500 de les vistes de dubtes: `{error, error_id}`, `error_id` coincident amb el log (amb traça) i cap text
d'excepció (CLAUDE.md gotcha 14). Les vistes criden `selectors.x(...)` / `services.x(...)` com a atributs de mòdul.
El missatge de cada punt és fix i el decideix l'implementador (només es comprova que existeix i que no filtra el secret).
"""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.doubts.tests.helpers import (
    DOUBTS, answer_url, answers_url, api_delete, api_get, api_post, doubt_ids, doubt_url, list_url, make_answer,
    make_doubt, user_claims)

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration,
              pytest.mark.real_permissions]

SECRET = 'SELECT secret FROM host=db.neon.tech bucket=prod-bucket'


def assert_traced(response, caplog):
    assert response.status_code == 500, response.content
    body = response.json()
    assert set(body) == {'error', 'error_id'} and body['error'] and isinstance(body['error'], str)
    assert SECRET not in response.content.decode() and 'DatabaseError' not in body['error']
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records), 'error_id al log amb traça'


def boom(exc=DatabaseError):
    return {'side_effect': exc(SECRET)}


def test_llista_amb_error_de_bd(client, world, caplog):
    with patch('apps.doubts.selectors.list_doubts', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, list_url(world[0].pk), user_claims('u1')), caplog)


def test_llista_amb_error_inesperat(client, world, caplog):
    with patch('apps.doubts.selectors.list_doubts', **boom(RuntimeError)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, list_url(world[0].pk), user_claims('u1')), caplog)


def test_crear_dubte_amb_error_de_bd(client, world, caplog):
    with patch('apps.doubts.services.create_doubt', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, DOUBTS, user_claims('u1'),
                               {'refuge_id': str(world[0].pk), 'message': 'x'}), caplog)
    assert doubt_ids() == []


def test_esborrar_dubte_amb_error_de_bd(client, world, caplog):
    d = make_doubt(world[0], 'u1')
    with patch('apps.doubts.services.delete_doubt', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, doubt_url(d), user_claims('u1')), caplog)
    assert doubt_ids() == [d]


def test_crear_resposta_amb_error_de_bd(client, world, caplog):
    d = make_doubt(world[0], 'u1')
    with patch('apps.doubts.services.create_answer', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, answers_url(d), user_claims('u2'), {'message': 'x'}), caplog)


def test_replicar_amb_error_de_bd(client, world, caplog):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u2')
    with patch('apps.doubts.services.create_answer', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, answer_url(d, a), user_claims('u3'), {'message': 'x'}), caplog)


def test_esborrar_resposta_amb_error_de_bd(client, world, caplog):
    d = make_doubt(world[0], 'u1')
    a = make_answer(d, 'u2')
    with patch('apps.doubts.services.delete_answer', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, answer_url(d, a), user_claims('u2')), caplog)


def test_els_errors_de_domini_no_son_500_ni_porten_error_id(client, world):
    r = api_delete(client, doubt_url('00000000-0000-0000-0000-000000000000'), user_claims('u1'))
    assert r.status_code == 404 and 'error_id' not in r.json()
