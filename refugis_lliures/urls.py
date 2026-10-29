"""
URL configuration for refugis_lliures project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from apps.renovations.urls import refuge_urlpatterns as refuge_renovations_urlpatterns

# Configuració de Swagger
schema_view = get_schema_view(
   openapi.Info(
      title="Refugis Lliures API",
      default_version='v1',
      description="API per a la gestió de refugis de muntanya i usuaris. Els endpoints d'usuaris requereixen autenticació amb token JWT de Firebase.",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@refugislliures.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   # Configuració de seguretat per a l'autenticació
   # Només endpoints de users/* requereixen autenticació
   # Els endpoints health/, refuges/ i refuges/{id}/ són públics
)

# Rutes de l'API sota `/api/`: cada feature exposa les seves a `apps/<feature>/urls.py`
api_urlpatterns = [
    path('', include('apps.health.urls')),                                      # /health/
    path('refuges/', include('apps.refuges.urls')),                             # /refuges/, /refuges/{id}/, media
    path('refuges/', include(refuge_renovations_urlpatterns)),                  # /refuges/{id}/renovations/
    path('', include('apps.visits.urls')),                                      # /refuges/{id}/visits/..., /users/{uid}/visits/
    path('', include('apps.uploads.urls')),                                     # /media/upload-intents/[confirm/]
    path('', include('apps.moderation.urls')),                                  # /media/reports/, /admin/media-reports/, /users/{uid}/moderation-notices/
    path('experiences/', include('apps.experiences.urls')),
    path('doubts/', include('apps.doubts.urls')),
    path('users/', include('apps.accounts.urls')),
    path('renovations/', include('apps.renovations.urls')),
    path('', include('apps.proposals.urls')),                                   # /refuges-proposals/..., /my-refuges-proposals/
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api_urlpatterns)),
    
    # Swagger/OpenAPI documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
