"""Rutes de `health`: s'inclouen des de `refugis_lliures/urls.py` sota `api/` (`GET /api/health/`)."""
from django.urls import path

from .views import HealthCheckAPIView

urlpatterns = [
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
]
