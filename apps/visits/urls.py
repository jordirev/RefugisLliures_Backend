"""Rutes de `visits`: s'inclouen des d'`api/urls.py` a l'arrel de l'API (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('refuges/<str:refuge_id>/visits/', views.RefugeVisitsAPIView.as_view(), name='refuge_visits'),
    path('refuges/<str:refuge_id>/visits/<str:visit_date>/', views.RefugeVisitDetailAPIView.as_view(),
         name='refuge_visit_detail'),                                                       # POST + PATCH + DELETE
    path('users/<str:uid>/visits/', views.UserVisitsAPIView.as_view(), name='user_visits'),
]
