from django.urls import path
from .views import health_check, refugi_detail, search_refugis, refugi_coordinates
from .views.user_views import (
    users_collection,
    user_detail, 
    search_user_by_email
)

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # Refugis endpoints (ordre important - més específiques primer)
    path('refugis/search/', search_refugis, name='search_refugis'),
    path('refugis/', refugi_coordinates, name='refugi_coordinates'),
    path('refugis/<str:refugi_id>/', refugi_detail, name='refugi_detail'),
    
    # Users endpoints (REST estàndard)
    path('users/search/', search_user_by_email, name='search_user_by_email'),  # GET /users/search/?email=
    path('users/', users_collection, name='users_collection'),  # GET /users/ (llistar) + POST /users/ (crear)
    path('users/<str:uid>/', user_detail, name='user_detail'),  # GET + PUT + DELETE /users/{uid}/
]
