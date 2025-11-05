"""Exports de les views de l'API.

Després de la refactorització a APIView, exposem les classes que s'han
creat per a cada endpoint perquè altres mòduls (p. ex. `api.urls`) puguin
importar-les de manera neta.
"""

# Views d'usuaris
from .user_views import UsersCollectionAPIView, UserDetailAPIView

# Views de refugis
from .refugi_lliure_views import (
	HealthCheckAPIView,
	RefugisCollectionAPIView,
	RefugiDetailAPIView,
)

__all__ = [
	'UsersCollectionAPIView',
	'UserDetailAPIView',
	'HealthCheckAPIView',
	'RefugisCollectionAPIView',
	'RefugiDetailAPIView',
]