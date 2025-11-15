from django.urls import path
from .views.health_check_views import HealthCheckAPIView
from .views.refugi_lliure_views import (
    RefugiDetailAPIView,
    RefugisCollectionAPIView
)
from .views.user_views import (
    UsersCollectionAPIView,
    UserDetailAPIView
)
from .views.cache_views import cache_stats, cache_clear, cache_invalidate

urlpatterns = [
    # Health check endpoint
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
    
    # Refugis endpoints 
    path('refugis/', RefugisCollectionAPIView.as_view(), name='refugis_collection'),
    path('refugis/<str:refugi_id>/', RefugiDetailAPIView.as_view(), name='refugi_detail'),
    
    # Users endpoints (REST estàndard)
    path('users/', UsersCollectionAPIView.as_view(), name='users_collection'),  # POST /users/ (crear)
    path('users/<str:uid>/', UserDetailAPIView.as_view(), name='user_detail'),  # GET + PATCH + DELETE /users/{uid}/
    
    # Cache management endpoints
    path('cache/stats/', cache_stats, name='cache_stats'),
    path('cache/clear/', cache_clear, name='cache_clear'),
    path('cache/invalidate/', cache_invalidate, name='cache_invalidate'),
]
