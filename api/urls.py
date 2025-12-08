from django.urls import path
from .views.health_check_views import HealthCheckAPIView
from .views.refugi_lliure_views import (
    RefugiLliureDetailAPIView,
    RefugiLliureCollectionAPIView,
    RefugeRenovationsAPIView
)
from .views.refugi_media_views import (
    RefugiMediaAPIView,
    RefugiMediaDeleteAPIView
)
from .views.user_views import (
    UsersCollectionAPIView,
    UserDetailAPIView,
    UserFavouriteRefugesAPIView,
    UserFavouriteRefugesDetailAPIView,
    UserVisitedRefugesAPIView,
    UserVisitedRefugesDetailAPIView
)
from .views.renovation_views import (
    RenovationListAPIView,
    RenovationAPIView,
    RenovationParticipantsAPIView,
    RenovationParticipantDetailAPIView
)
from .views.cache_views import cache_stats, cache_clear, cache_invalidate

urlpatterns = [
    # Health check endpoint
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
    
    # Refugis endpoints 
    path('refuges/', RefugiLliureCollectionAPIView.as_view(), name='refugi_lliure_collection'),
    path('refuges/<str:refuge_id>/', RefugiLliureDetailAPIView.as_view(), name='refugi_lliure_detail'),
    path('refuges/<str:refuge_id>/renovations/', RefugeRenovationsAPIView.as_view(), name='refuge_renovations'),  # GET /refuges/{id}/renovations/
    
    # Refugi media endpoints
    path('refuges/<str:id>/media/', RefugiMediaAPIView.as_view(), name='refugi_media'),  # GET + POST /refuges/{id}/media/
    path('refuges/<str:id>/media/<path:key>/', RefugiMediaDeleteAPIView.as_view(), name='refugi_media_delete'),  # DELETE /refuges/{id}/media/{key}/
    
    # Users endpoints
    path('users/', UsersCollectionAPIView.as_view(), name='users_collection'),  # POST /users/ (crear)
    path('users/<str:uid>/', UserDetailAPIView.as_view(), name='user_detail'),  # GET + PATCH + DELETE /users/{uid}/
    path('users/<str:uid>/favorite-refuges/', UserFavouriteRefugesAPIView.as_view(), name='user_refugis_preferits'),  # GET + POST /users/{uid}/favorite-refuges/
    path('users/<str:uid>/favorite-refuges/<str:refuge_id>/', UserFavouriteRefugesDetailAPIView.as_view(), name='user_favourite_refuges_delete'),  # DELETE /users/{uid}/favorite-refuges/{refuge_id}/
    path('users/<str:uid>/visited-refuges/', UserVisitedRefugesAPIView.as_view(), name='user_visited_refuges'),  # GET + POST /users/{uid}/visited-refuges/
    path('users/<str:uid>/visited-refuges/<str:refuge_id>/', UserVisitedRefugesDetailAPIView.as_view(), name='user_visited_refuges_delete'),  # DELETE /users/{uid}/visited-refuges/{refuge_id}/
    
    # Renovations endpoints
    path('renovations/', RenovationListAPIView.as_view(), name='renovation_list'),  # GET + POST /renovations/
    path('renovations/<str:id>/', RenovationAPIView.as_view(), name='renovation_detail'),  # GET + PATCH + DELETE /renovations/{id}/
    path('renovations/<str:id>/participants/', RenovationParticipantsAPIView.as_view(), name='renovation_participants'),  # POST /renovations/{id}/participants/
    path('renovations/<str:id>/participants/<str:uid>/', RenovationParticipantDetailAPIView.as_view(), name='renovation_participant_detail'),  # DELETE /renovations/{id}/participants/{uid}/
    
    # Cache management endpoints
    path('cache/stats/', cache_stats, name='cache_stats'),
    path('cache/clear/', cache_clear, name='cache_clear'),
    path('cache/invalidate/', cache_invalidate, name='cache_invalidate'),
]
