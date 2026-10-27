"""
Errors 500 de les vistes d'experiències: `{error, error_id}`, `error_id` coincident amb el log (amb traça) i cap text
d'excepció (CLAUDE.md gotcha 14). Les vistes criden `selectors.x(...)` / `services.x(...)` com a atributs de mòdul
(`apps.experiences.selectors.list_experiences`, `services.create_experience`, `services.update_experience`,
`services.delete_experience`). Avui els 500 eren `{error: 'Error obtenint les experiències'}` o `str(e)`.
"""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.experiences.tests.helpers import (
    EXPERIENCES, api_delete, api_get, api_patch, api_post, deleted_keys, exp_ids, exp_row, exp_url, fail_r2, list_url,
    make_exp_media, make_experience, media_keys_of, new_body, refuge_state, user_claims)

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
def test_llista_amb_error(client, world, caplog, exc):
    with patch('apps.experiences.selectors.list_experiences', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, list_url(world[0].pk), user_claims('u1')), caplog)


def test_llista_amb_error_en_generar_la_url_prefirmada(client, world, caplog, r2):
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/a.webp')
    from api.services.r2_media_service import R2MediaService
    with patch.object(R2MediaService, 'generate_presigned_url', side_effect=Exception(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, list_url(world[0].pk), user_claims('u1')), caplog)


@pytest.mark.parametrize('exc', [DatabaseError, RuntimeError])
def test_crear_amb_error(client, world, caplog, exc):
    with patch('apps.experiences.services.create_experience', **boom(exc)), caplog.at_level(logging.ERROR):
        assert_traced(api_post(client, EXPERIENCES, user_claims('u1'), new_body(world[0])), caplog)
    assert exp_ids() == [] and refuge_state(world[0])[:2] == (None, 0)


def test_editar_amb_error(client, world, caplog):
    e = make_experience(world[0], 'u1', comment='igual')
    with patch('apps.experiences.services.update_experience', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_patch(client, exp_url(e), user_claims('u1'), {'comment': 'x'}), caplog)
    assert exp_row(e)['comment'] == 'igual'


def test_esborrar_amb_error(client, world, caplog):
    e = make_experience(world[0], 'u1')
    with patch('apps.experiences.services.delete_experience', **boom()), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, exp_url(e), user_claims('u1')), caplog)
    assert exp_ids() == [e]


def test_esborrar_amb_r2_caigut_es_500_i_l_experiencia_i_els_mitjans_es_conserven(client, world, r2, caplog):
    """Mateix criteri que `delete_media`: si R2 no esborra el fitxer, es desfà l'esborrat de la fila (reintentable)."""
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/a.webp', thumb_key='k/a_thumb.webp')
    fail_r2(r2)
    with caplog.at_level(logging.ERROR):
        resp = api_delete(client, exp_url(e), user_claims('u1'))
    assert_traced(resp, caplog)
    assert exp_ids() == [e] and media_keys_of(e) == ['k/a.webp']


def test_esborrar_amb_r2_que_llanca_excepcio_tambe_es_500_i_conserva(client, world, r2, caplog):
    e = make_experience(world[0], 'u1')
    make_exp_media(world[0], 'u1', e, key='k/a.webp')
    r2.delete_file.side_effect = Exception(SECRET)
    r2.delete_files.side_effect = Exception(SECRET)
    with caplog.at_level(logging.ERROR):
        resp = api_delete(client, exp_url(e), user_claims('u1'))
    assert_traced(resp, caplog)
    assert exp_ids() == [e] and media_keys_of(e) == ['k/a.webp']


def test_esborrar_sense_mitjans_no_toca_r2(client, world, r2):
    e = make_experience(world[0], 'u1')
    assert api_delete(client, exp_url(e), user_claims('u1')).status_code == 200
    assert deleted_keys(r2) == []


def test_els_errors_de_domini_no_son_500_ni_porten_error_id(client, world):
    r = api_delete(client, exp_url('00000000-0000-0000-0000-000000000000'), user_claims('u1'))
    assert r.status_code == 404 and 'error_id' not in r.json()
