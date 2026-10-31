"""`GET /api/refuges/elevation/`: la consulta a Open-Elevation la fa el servidor (RGPD), sense BD."""
import io
import json
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.refuges import elevation
from apps.refuges.views import RefugeElevationAPIView


def _get(query, authenticated=True):
    request = APIRequestFactory().get('/api/refuges/elevation/', query)
    if authenticated:
        force_authenticate(request, user=MagicMock(is_authenticated=True, uid='u1', claims={}))
    return RefugeElevationAPIView.as_view()(request)


def _opener(payload=None, exc=None):
    def opener(request, timeout):
        if exc:
            raise exc
        return io.BytesIO(json.dumps(payload).encode())
    return opener


@pytest.mark.views
class TestElevationView:
    @patch('apps.refuges.views.elevation.get_elevation', return_value=2145)
    def test_retorna_l_altitud(self, mock_get):
        response = _get({'lat': '42.5', 'lng': '1.5'})
        assert response.status_code == 200 and response.data == {'elevation': 2145}
        mock_get.assert_called_once_with(42.5, 1.5)

    @pytest.mark.parametrize('query', [{}, {'lat': '42'}, {'lat': 'x', 'lng': '1'}, {'lat': '91', 'lng': '1'},
                                       {'lat': '1', 'lng': '181'}, {'lat': 'nan', 'lng': '1'}])
    def test_coordenades_invalides_400(self, query):
        assert _get(query).status_code == 400

    def test_anonim_401(self):
        assert _get({'lat': '42', 'lng': '1'}, authenticated=False).status_code in (401, 403)

    @patch('apps.refuges.views.elevation.get_elevation', side_effect=elevation.ElevationUnavailable('x'))
    def test_proveidor_caigut_500_tracat(self, _):
        response = _get({'lat': '42', 'lng': '1'})
        assert response.status_code == 500 and 'error_id' in response.data


@pytest.mark.unit
class TestElevationService:
    def test_arrodoneix(self):
        assert elevation.get_elevation(42.5, 1.5, opener=_opener({'results': [{'elevation': 2144.6}]})) == 2145

    def test_sense_resultats_es_none(self):
        assert elevation.get_elevation(42.5, 1.5, opener=_opener({'results': []})) is None

    def test_error_de_xarxa(self):
        with pytest.raises(elevation.ElevationUnavailable):
            elevation.get_elevation(42.5, 1.5, opener=_opener(exc=OSError('down')))

    def test_resposta_malformada(self):
        with pytest.raises(elevation.ElevationUnavailable):
            elevation.get_elevation(42.5, 1.5, opener=_opener({'results': [{}]}))
