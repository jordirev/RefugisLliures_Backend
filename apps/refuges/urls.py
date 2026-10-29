"""Rutes de `refuges`: s'inclouen des de `refugis_lliures/urls.py` sota `refuges/` (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.RefugeCollectionAPIView.as_view(), name='refugi_lliure_collection'),
    path('<str:id>/', views.RefugeDetailAPIView.as_view(), name='refugi_lliure_detail'),
    path('<str:id>/media/', views.RefugeMediaListAPIView.as_view(), name='refugi_media'),
    path('<str:id>/media/<path:key>/', views.RefugeMediaDetailAPIView.as_view(), name='refugi_media_delete'),
]
