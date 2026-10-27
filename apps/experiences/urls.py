"""Rutes d'`experiences`: s'inclouen des d'`api/urls.py` sota `experiences/` (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.ExperienceListAPIView.as_view(), name='experience_list'),                              # GET + POST
    path('<str:experience_id>/', views.ExperienceDetailAPIView.as_view(), name='experience_detail'),      # PATCH + DELETE
]
