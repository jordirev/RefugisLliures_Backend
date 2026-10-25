"""Rutes de `accounts`: s'inclouen des d'`api/urls.py` sota `users/` (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.UsersCollectionAPIView.as_view(), name='users_collection'),                     # POST
    path('<str:uid>/', views.UserDetailAPIView.as_view(), name='user_detail'),                      # GET + PATCH + DELETE
    path('<str:uid>/avatar/', views.UserAvatarAPIView.as_view(), name='user_avatar'),               # DELETE
    path('<str:uid>/age-confirmation/', views.UserAgeConfirmationAPIView.as_view(),
         name='user_age_confirmation'),                                                             # PATCH
    path('<str:uid>/favorite-refuges/', views.UserFavouriteRefugesAPIView.as_view(),
         name='user_refugis_preferits'),                                                            # GET + POST
    path('<str:uid>/favorite-refuges/<str:refuge_id>/', views.UserFavouriteRefugesDetailAPIView.as_view(),
         name='user_favourite_refuges_delete'),                                                     # DELETE
    path('<str:uid>/visited-refuges/', views.UserVisitedRefugesAPIView.as_view(), name='user_visited_refuges'),
    path('<str:uid>/visited-refuges/<str:refuge_id>/', views.UserVisitedRefugesDetailAPIView.as_view(),
         name='user_visited_refuges_delete'),
]
