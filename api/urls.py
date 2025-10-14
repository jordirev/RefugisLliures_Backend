from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Imports específics per evitar conflictes
from .views.refugi_lliure_api import RefugiLliureApiView, refugi_lliure_list, refugi_lliure_detail, health_check

# Router per als ViewSets
router = DefaultRouter()
router.register(r'refugis', RefugiLliureApiView, basename='refugi')

urlpatterns = [
    path('health/', health_check, name='health_check'),
    
    # URLs amb ViewSet (recomanat)
    path('', include(router.urls)),
    
    # URLs alternatives amb function-based views
    path('refugis-alt/', refugi_lliure_list, name='refugi_list_alt'),
    path('refugis-alt/<int:refugi_id>/', refugi_lliure_detail, name='refugi_detail_alt'),
]
