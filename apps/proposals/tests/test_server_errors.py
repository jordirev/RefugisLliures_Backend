"""
Errors 500 de les vistes de propostes: `{error, error_id}`, `error_id` coincident amb el log (amb traça) i cap text
d'excepció (CLAUDE.md gotcha 14). Les vistes criden `selectors.x(...)` / `services.x(...)` com a atributs de mòdul.
Els errors de domini (404/409/400) no són 500 ni porten `error_id`.
"""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.proposals.tests.helpers import (
    MINE, PROPOSALS, admin_claims, api_get, api_post, approve_url, count_proposals, create_body, make_proposal,
    proposal_row, refuge_ids, reject_url, user_claims)

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


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_llista_d_admin_amb_error(client, world, caplog, exc):
    with patch('apps.proposals.selectors.list_proposals', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, PROPOSALS, admin_claims('adm')), caplog)


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_les_meves_amb_error(client, world, caplog, exc):
    with patch('apps.proposals.selectors.list_proposals', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, MINE, user_claims('u1')), caplog)


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_crear_amb_error(client, world, caplog, exc):
    with patch('apps.proposals.services.create_proposal', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, PROPOSALS, user_claims('u1'), create_body()), caplog)
    assert count_proposals() == 0


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_aprovar_amb_error(client, world, caplog, exc):
    pid = make_proposal()
    with patch('apps.proposals.services.approve_proposal', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, approve_url(pid), admin_claims('adm')), caplog)
    assert proposal_row(pid)['status'] == 'pending'


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_rebutjar_amb_error(client, world, caplog, exc):
    pid = make_proposal()
    with patch('apps.proposals.services.reject_proposal', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, reject_url(pid), admin_claims('adm'), {'reason': 'x'}), caplog)
    assert proposal_row(pid)['status'] == 'pending'


def test_aprovar_una_proposta_amb_dades_que_la_bd_rebutja_es_500_traçat_i_continua_pendent(client, world, caplog):
    """Una proposta que va saltar el serializer (nom de 300 car. > `varchar(255)`): 500 amb `error_id`, tot desfet."""
    pid = make_proposal(payload={'name': 'x' * 300, 'coord': {'lat': 42.0, 'long': 2.0}})
    n = len(refuge_ids())
    with caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, approve_url(pid), admin_claims('adm')), caplog)
    assert proposal_row(pid)['status'] == 'pending' and len(refuge_ids()) == n


def test_els_errors_de_domini_no_son_500_ni_porten_error_id(client, world):
    r = api_post(client, approve_url('00000000-0000-0000-0000-000000000000'), admin_claims('adm'))
    assert r.status_code == 404 and 'error_id' not in r.json()
    pid = make_proposal(status='approved')
    r = api_post(client, approve_url(pid), admin_claims('adm'))
    assert r.status_code == 409 and 'error_id' not in r.json()
