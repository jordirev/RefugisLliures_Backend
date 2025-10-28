from django.urls import path
from .views.refugi_lliure_views import health_check, refugi_detail, refugis_collection
from .views.user_views import (
    users_collection,
    user_detail
)
from .views.cache_views import cache_stats, cache_clear, cache_invalidate

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # Refugis endpoints 
    path('refugis/', refugis_collection, name='refugis_collection'),
    path('refugis/<str:refugi_id>/', refugi_detail, name='refugi_detail'),
    
    # Users endpoints (REST estàndard)
    path('users/', users_collection, name='users_collection'),  # GET /users/ (llistar) + POST /users/ (crear)
    path('users/<str:uid>/', user_detail, name='user_detail'),  # GET + PUT + DELETE /users/{uid}/
    
    # Cache management endpoints
    path('cache/stats/', cache_stats, name='cache_stats'),
    path('cache/clear/', cache_clear, name='cache_clear'),
    path('cache/invalidate/', cache_invalidate, name='cache_invalidate'),
]
