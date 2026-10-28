"""
Errors 500 de les vistes de moderació: `{error, error_id}`, `error_id` coincident amb el log (amb traça) i cap text
d'excepció (CLAUDE.md gotcha 14). Les vistes criden `selectors.x(...)` / `services.x(...)` com a atributs de mòdul:
`selectors.list_reports(status)`, `selectors.list_notices(uid)`, `services.create_report(...)`,
`services.resolve_report(...)`. Els errors de domini (400/403/404/409) no són 500 ni porten `error_id`.
"""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.moderation.tests.helpers import (
    ADMIN_REPORTS, REPORTS, ZERO_UUID, admin_claims, api_get, api_patch, api_post, make_media, make_report,
    media_key_for, notices_url, report_row, resolve_url, user_claims)

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


@pytest.fixture
def media(world):
    r = world[0]
    key = media_key_for(r)
    make_media(r, 'u1', key=key)
    return r, key


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_crear_denuncia_amb_error(client, media, caplog, exc):
    r, key = media
    with patch('apps.moderation.services.create_report', **boom(exc)), caplog.at_level(logging.ERROR):
        resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'my_image'})
    assert_traced(resp, caplog)


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_llistar_denuncies_amb_error(client, world, caplog, exc):
    with patch('apps.moderation.selectors.list_reports', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, ADMIN_REPORTS, admin_claims('adm')), caplog)


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_resoldre_amb_error(client, world, caplog, exc):
    rid = make_report(world[0], 'k', 'u2')
    with patch('apps.moderation.services.resolve_report', **boom(exc)), caplog.at_level(logging.ERROR):
        resp = api_patch(client, resolve_url(rid), admin_claims('adm'), {'action': 'remove', 'statement': 'x'})
    assert_traced(resp, caplog)
    assert report_row(rid)['status'] == 'pending'


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_avisos_amb_error(client, world, caplog, exc):
    with patch('apps.moderation.selectors.list_notices', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, notices_url('u1'), user_claims('u1')), caplog)


def test_els_missatges_son_especifics_per_punt(client, world, media, caplog):
    r, key = media
    messages = set()
    with caplog.at_level(logging.ERROR):
        with patch('apps.moderation.services.create_report', **boom()):
            messages.add(api_post(client, REPORTS, user_claims('u2'),
                                  {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'my_image'}).json()['error'])
        with patch('apps.moderation.selectors.list_reports', **boom()):
            messages.add(api_get(client, ADMIN_REPORTS, admin_claims('adm')).json()['error'])
        with patch('apps.moderation.selectors.list_notices', **boom()):
            messages.add(api_get(client, notices_url('u1'), user_claims('u1')).json()['error'])
    assert len(messages) == 3


def test_els_errors_de_domini_no_son_500_ni_porten_error_id(client, world):
    assert api_patch(client, resolve_url(ZERO_UUID), admin_claims('adm'),
                     {'action': 'remove', 'statement': 'x'}).json() == {'error': 'Report not found'}
    r = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': ZERO_UUID, 'media_key': 'k', 'reason': 'my_image'})
    assert r.status_code == 404 and 'error_id' not in r.json()
    r = api_post(client, REPORTS, user_claims('u2'), {'reason': 'x'})
    assert r.status_code == 400 and 'error_id' not in r.json()


def test_un_error_de_bd_inesperat_a_l_insert_es_500_i_no_un_409(client, media, caplog):
    """Només la violació de `media_reports_unique_reporter_uq` és un 409; qualsevol altre error d'integritat és 500."""
    from django.db import connection

    def wrapper(execute, sql_, params, many, context):
        if sql_.lstrip().upper().startswith('INSERT') and 'media_reports' in sql_:
            raise DatabaseError('fallada simulada: host=db.neon.tech')
        return execute(sql_, params, many, context)

    r, key = media
    with connection.execute_wrapper(wrapper), caplog.at_level(logging.ERROR):
        resp = api_post(client, REPORTS, user_claims('u2'), {'refuge_id': str(r.pk), 'media_key': key, 'reason': 'my_image'})
    assert resp.status_code == 500 and set(resp.json()) == {'error', 'error_id'} and 'neon' not in resp.content.decode()
