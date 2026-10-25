"""Exports de les views de l'API.

Després de la refactorització a APIView, exposem les classes que s'han
creat per a cada endpoint perquè altres mòduls (p. ex. `api.urls`) puguin
importar-les de manera neta.
"""

# Views de health check
from .health_check_views import HealthCheckAPIView

__all__ = [
	'HealthCheckAPIView',
]