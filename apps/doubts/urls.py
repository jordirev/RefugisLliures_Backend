"""Rutes de `doubts`: s'inclouen des de `refugis_lliures/urls.py` sota `doubts/` (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.DoubtListAPIView.as_view(), name='doubt_list'),                                   # GET + POST
    path('<str:doubt_id>/', views.DoubtDetailAPIView.as_view(), name='doubt_detail'),                # DELETE
    path('<str:doubt_id>/answers/', views.AnswerListAPIView.as_view(), name='answer_list'),          # POST
    path('<str:doubt_id>/answers/<str:answer_id>/', views.AnswerReplyAPIView.as_view(),
         name='answer_reply'),                                                                       # POST + DELETE
]
