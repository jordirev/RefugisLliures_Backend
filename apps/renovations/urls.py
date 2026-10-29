"""Rutes de `renovations`: s'inclouen des de `refugis_lliures/urls.py` sota `renovations/` (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.RenovationListAPIView.as_view(), name='renovation_list'),                                   # GET + POST
    path('<str:id>/', views.RenovationAPIView.as_view(), name='renovation_detail'),                             # GET + PATCH + DELETE
    path('<str:id>/participants/', views.RenovationParticipantsAPIView.as_view(), name='renovation_participants'),   # POST
    path('<str:id>/participants/<str:uid>/', views.RenovationParticipantDetailAPIView.as_view(),
         name='renovation_participant_detail'),                                                                 # DELETE
]

# GET /refuges/{id}/renovations/ (s'inclou sota `refuges/` des de `refugis_lliures/urls.py`)
refuge_urlpatterns = [
    path('<str:id>/renovations/', views.RefugeRenovationsAPIView.as_view(), name='refuge_renovations'),
]
