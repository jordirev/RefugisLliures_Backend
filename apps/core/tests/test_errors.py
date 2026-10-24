"""`server_error`: 500 amb missatge específic i `error_id`; el text de l'excepció no surt mai a la resposta."""
import logging
import uuid

import pytest

from apps.core.errors import server_error

pytestmark = [pytest.mark.unit]


def test_resposta_500_amb_missatge_i_error_id(caplog):
    with caplog.at_level(logging.ERROR):
        response = server_error('Error en esborrar el fitxer a R2', RuntimeError('host=secret.r2.example key=AKIA123'))
    assert response.status_code == 500
    assert set(response.data) == {'error', 'error_id'}
    assert response.data['error'] == 'Error en esborrar el fitxer a R2'
    assert uuid.UUID(response.data['error_id']).version == 7


def test_el_log_porta_el_mateix_error_id_i_la_traca(caplog):
    with caplog.at_level(logging.ERROR):
        response = server_error('Error de base de dades en cercar refugis', ValueError('SELECT * FROM secret'))
    (record,) = [r for r in caplog.records if response.data['error_id'] in r.getMessage()]
    assert 'Error de base de dades en cercar refugis' in record.getMessage()
    assert record.exc_info and record.exc_info[0] is ValueError          # traça completa al log


def test_el_text_de_l_excepcio_no_surt_a_la_resposta():
    response = server_error('Error en generar la URL de la imatge', RuntimeError('bucket=secret-bucket path=/etc/x'))
    body = str(response.data)
    assert 'secret-bucket' not in body and 'RuntimeError' not in body and '/etc/x' not in body


def test_dins_d_un_except_no_cal_passar_l_excepcio(caplog):
    with caplog.at_level(logging.ERROR):
        try:
            raise KeyError('dins')
        except KeyError:
            response = server_error('Error intern')
    assert caplog.records[-1].exc_info[0] is KeyError and response.status_code == 500


def test_cada_error_te_un_id_diferent():
    assert server_error('x').data['error_id'] != server_error('x').data['error_id']
