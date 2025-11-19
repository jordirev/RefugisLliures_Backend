from django.urls import path
from .views.health_check_views import HealthCheckAPIView
from .views.refugi_lliure_views import (
    RefugiDetailAPIView,
    RefugisCollectionAPIView
)
from .views.user_views import (
    UsersCollectionAPIView,
    UserDetailAPIView,
    UserRefugisPreferitsAPIView,
    UserRefugisPreferitsDetailAPIView,
    UserRefugisVisitatsAPIView,
    UserRefugisVisitatsDetailAPIView
)
from .views.cache_views import cache_stats, cache_clear, cache_invalidate

urlpatterns = [
    # Health check endpoint
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
    
    # Refugis endpoints 
    path('refugis/', RefugisCollectionAPIView.as_view(), name='refugis_collection'),
    path('refugis/<str:refugi_id>/', RefugiDetailAPIView.as_view(), name='refugi_detail'),
    
    # Users endpoints
    path('users/', UsersCollectionAPIView.as_view(), name='users_collection'),  # POST /users/ (crear)
    path('users/<str:uid>/', UserDetailAPIView.as_view(), name='user_detail'),  # GET + PATCH + DELETE /users/{uid}/
    path('users/<str:uid>/refugis-preferits/', UserRefugisPreferitsAPIView.as_view(), name='user_refugis_preferits'),  # GET + POST /users/{uid}/refugis-preferits/
    path('users/<str:uid>/refugis-preferits/<str:refugi_id>/', UserRefugisPreferitsDetailAPIView.as_view(), name='user_refugis_preferits_delete'),  # DELETE /users/{uid}/refugis-preferits/{refugi_id}/
    path('users/<str:uid>/refugis-visitats/', UserRefugisVisitatsAPIView.as_view(), name='user_refugis_visitats'),  # GET + POST /users/{uid}/refugis-visitats/
    path('users/<str:uid>/refugis-visitats/<str:refugi_id>/', UserRefugisVisitatsDetailAPIView.as_view(), name='user_refugis_visitats_delete'),  # DELETE /users/{uid}/refugis-visitats/{refugi_id}/
    
    # Cache management endpoints
    path('cache/stats/', cache_stats, name='cache_stats'),
    path('cache/clear/', cache_clear, name='cache_clear'),
    path('cache/invalidate/', cache_invalidate, name='cache_invalidate'),
]
