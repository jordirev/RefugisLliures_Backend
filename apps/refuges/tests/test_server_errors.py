"""Errors 500 de les vistes de refugis: missatge específic, `error_id` coincident amb el log i cap text d'excepció."""
import logging
from unittest.mock import patch

import pytest
from django.db import DatabaseError

from apps.refuges.tests.helpers import admin_claims, api_delete, api_get, make_media, make_refuge, make_user, user_claims

pytestmark = [pytest.mark.db_infra, pytest.mark.django_db, pytest.mark.views, pytest.mark.integration]

URL = '/api/refuges/'
SECRET = 'SELECT secret FROM host=db.neon.tech bucket=prod-bucket'


def assert_traced(response, message, caplog):
    assert response.status_code == 500
    body = response.json()
    assert body['error'] == message and set(body) == {'error', 'error_id'}
    assert SECRET not in response.content.decode() and 'Error:' not in body['error']
    assert any(body['error_id'] in r.getMessage() and r.exc_info for r in caplog.records), 'error_id al log amb traça'


def test_mapa_amb_error_de_bd(client, RM, caplog):
    with patch('apps.refuges.views.selectors.list_map_points', side_effect=DatabaseError(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, URL), 'Error de base de dades en obtenir el mapa de refugis', caplog)


def test_cerca_amb_error_de_bd(client, RM, caplog):
    with patch('apps.refuges.views.selectors.search_refuges', side_effect=DatabaseError(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, URL + '?type=orri'), 'Error de base de dades en cercar refugis', caplog)


def test_detall_amb_error_de_bd(client, RM, caplog):
    r = make_refuge()
    with patch('apps.refuges.views.selectors.get_refuge', side_effect=DatabaseError(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, f'{URL}{r.pk}/'), 'Error de base de dades en obtenir el refugi', caplog)


def test_detall_amb_error_en_generar_la_url(client, RM, caplog):
    make_user('u1')
    r = make_refuge()
    make_media(r, 'u1')
    with patch('apps.refuges.views._presigner', side_effect=RuntimeError(SECRET)), caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, f'{URL}{r.pk}/', user_claims('u2')), 'Error en generar la URL de la imatge',
                      caplog)


def test_llista_de_mitjans_amb_error_de_bd(client, RM, caplog):
    r = make_refuge()
    with patch('apps.refuges.views.selectors.get_refuge_media', side_effect=DatabaseError(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_get(client, f'{URL}{r.pk}/media/', user_claims('u1')),
                      'Error de base de dades en obtenir els mitjans del refugi', caplog)


def test_esborrat_quan_r2_llanca_una_excepcio_amb_dades_sensibles(client, RM, caplog):
    from apps.uploads.media.r2_media_service import R2MediaService
    make_user('u1')
    r = make_refuge()
    key = f'refugis-lliures/{r.pk}/a.webp'
    make_media(r, 'u1', key=key)
    with patch.object(R2MediaService, 'delete_file', side_effect=RuntimeError(SECRET)), caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, f'{URL}{r.pk}/media/{key}/', user_claims('u1')),
                      'Error en esborrar el fitxer a R2', caplog)


def test_esborrat_amb_error_de_bd(client, RM, caplog):
    make_user('u1')
    r = make_refuge()
    key = f'refugis-lliures/{r.pk}/b.webp'
    make_media(r, 'u1', key=key)
    with patch('apps.refuges.services.selectors.get_media_by_key', side_effect=DatabaseError(SECRET)), \
            caplog.at_level(logging.ERROR):
        assert_traced(api_delete(client, f'{URL}{r.pk}/media/{key}/', admin_claims()),
                      'Error de base de dades en esborrar el mitjà', caplog)
