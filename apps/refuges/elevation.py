"""
Altitud d'unes coordenades per a l'alta/edició de refugis.

La crida a Open-Elevation la fa el servidor (RGPD): el client mai contacta amb tercers i no hi exposa la seva IP.
Només s'envien al proveïdor les coordenades (cap identificador de l'usuari).
"""
import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

OPEN_ELEVATION_URL = 'https://api.open-elevation.com/api/v1/lookup'
TIMEOUT_SECONDS = 5


class ElevationUnavailable(Exception):
    """El proveïdor no respon o retorna una resposta que no es pot interpretar."""


def get_elevation(lat: float, lng: float, *, opener=urllib.request.urlopen) -> Optional[int]:
    """Altitud en metres (arrodonida) o `None` si el proveïdor no en té; `ElevationUnavailable` si falla."""
    url = f'{OPEN_ELEVATION_URL}?locations={lat:.6f},{lng:.6f}'
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'RefugisLliures/1.0'})
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode('utf-8'))
        results = data.get('results') or []
        if not results:
            return None
        return round(float(results[0]['elevation']))
    except Exception as exc:
        raise ElevationUnavailable('Open-Elevation no disponible') from exc
