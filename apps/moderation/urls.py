"""Rutes de `moderation`: s'inclouen des d'`api/urls.py` a l'arrel (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('media/reports/', views.MediaReportsAPIView.as_view(), name='media_reports'),                    # POST
    path('admin/media-reports/', views.AdminMediaReportsAPIView.as_view(), name='admin_media_reports'),  # GET (admins)
    path('admin/media-reports/<str:id>/', views.AdminMediaReportDetailAPIView.as_view(),
         name='admin_media_report_detail'),                                                               # PATCH (admins)
    path('users/<str:uid>/moderation-notices/', views.UserModerationNoticesAPIView.as_view(),
         name='user_moderation_notices'),                                                                 # GET (el mateix usuari)
]
