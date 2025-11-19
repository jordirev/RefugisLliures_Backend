"""Exports de les views de l'API.

Després de la refactorització a APIView, exposem les classes que s'han
creat per a cada endpoint perquè altres mòduls (p. ex. `api.urls`) puguin
importar-les de manera neta.
"""

# Views d'usuaris
from .user_views import UsersCollectionAPIView, UserDetailAPIView

# Views de health check
from .health_check_views import HealthCheckAPIView

# Views de refugis
from .refugi_lliure_views import (
	RefugiLliureCollectionAPIView,
	RefugiLliureDetailAPIView,
)

__all__ = [
	'UsersCollectionAPIView',
	'UserDetailAPIView',
	'HealthCheckAPIView',
	'RefugiLliureCollectionAPIView',
	'RefugiLliureDetailAPIView',
]