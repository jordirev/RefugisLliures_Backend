from django.urls import path
from .views import health_check, refugi_detail, search_refugis, refugi_coordinates

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # Refugis endpoints (ordre important - més específiques primer)
    path('refugis/search/', search_refugis, name='search_refugis'),
    path('refugis/', refugi_coordinates, name='refugi_coordinates'),
    path('refugis/<str:refugi_id>/', refugi_detail, name='refugi_detail'),
]
