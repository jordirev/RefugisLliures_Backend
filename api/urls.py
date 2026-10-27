from django.urls import include, path
from .views.health_check_views import HealthCheckAPIView
from .views.user_views import UserModerationNoticesAPIView
from apps.uploads.views import UploadIntentsAPIView, UploadIntentsConfirmAPIView
from .views.media_views import (
    MediaReportsAPIView,
    AdminMediaReportsAPIView,
    AdminMediaReportDetailAPIView,
)
from apps.renovations.views import RefugeRenovationsAPIView
from .views.refuge_proposal_views import (
    RefugeProposalCollectionAPIView,
    RefugeProposalApproveAPIView,
    RefugeProposalRejectAPIView,
    MyRefugeProposalCollectionAPIView
)
from .views.cache_views import cache_stats, cache_clear, cache_invalidate

urlpatterns = [
    # Health check endpoint
    path('health/', HealthCheckAPIView.as_view(), name='health_check'),
    
    # Refugis endpoints 
    # /refuges/, /refuges/{id}/, /refuges/{id}/media/, /refuges/{id}/media/{key}/ → app `refuges` (migrada a PostgreSQL)
    path('refuges/', include('apps.refuges.urls')),
    path('refuges/<str:id>/renovations/', RefugeRenovationsAPIView.as_view(), name='refuge_renovations'),  # GET /refuges/{id}/renovations/
    
    # /refuges/{id}/visits/, /refuges/{id}/visits/{date}/, /users/{uid}/visits/ → app `visits` (PostgreSQL)
    path('', include('apps.visits.urls')),
    
    # Pujada directa de mitjans (presigned PUT + confirm) i moderació
    path('media/upload-intents/', UploadIntentsAPIView.as_view(), name='media_upload_intents'),  # POST
    path('media/upload-intents/confirm/', UploadIntentsConfirmAPIView.as_view(), name='media_upload_intents_confirm'),  # POST
    path('media/reports/', MediaReportsAPIView.as_view(), name='media_reports'),  # POST
    path('admin/media-reports/', AdminMediaReportsAPIView.as_view(), name='admin_media_reports'),  # GET (admins)
    path('admin/media-reports/<str:id>/', AdminMediaReportDetailAPIView.as_view(), name='admin_media_report_detail'),  # PATCH (admins)

    # Refuge experience endpoints
    # /experiences/, /experiences/{id}/ → app `experiences` (PostgreSQL)
    path('experiences/', include('apps.experiences.urls')),
    
    # Refuge doubts endpoints
    # /doubts/, /doubts/{id}/, /doubts/{id}/answers/, /doubts/{id}/answers/{answer_id}/ → app `doubts` (PostgreSQL)
    path('doubts/', include('apps.doubts.urls')),

    # Users endpoints
    # /users/, /users/{uid}/, avatar, age-confirmation i les llistes de preferits/visitats → app `accounts` (PostgreSQL)
    path('users/', include('apps.accounts.urls')),
    path('users/<str:uid>/moderation-notices/', UserModerationNoticesAPIView.as_view(), name='user_moderation_notices'),  # GET
    
    # Renovations endpoints
    # /renovations/, /renovations/{id}/, /renovations/{id}/participants/[{uid}/] → app `renovations` (PostgreSQL)
    path('renovations/', include('apps.renovations.urls')),
    
    # Refuge proposal endpoints
    path('refuges-proposals/', RefugeProposalCollectionAPIView.as_view(), name='refuge_proposal_collection'),  # POST /refuges-proposals/ (crear) + GET /refuges-proposals/ (llistar - només admins)
    path('my-refuges-proposals/', MyRefugeProposalCollectionAPIView.as_view(), name='my_refuge_proposal_collection'),  # GET /my-refuges-proposals/ (llistar les pròpies propostes)
    path('refuges-proposals/<str:id>/approve/', RefugeProposalApproveAPIView.as_view(), name='refuge_proposal_approve'),  # POST /refuges-proposals/{id}/approve/ (només admins)
    path('refuges-proposals/<str:id>/reject/', RefugeProposalRejectAPIView.as_view(), name='refuge_proposal_reject'),  # POST /refuges-proposals/{id}/reject/ (només admins)
    
    # Cache management endpoints
    path('cache/stats/', cache_stats, name='cache_stats'),
    path('cache/clear/', cache_clear, name='cache_clear'),
    path('cache/invalidate/', cache_invalidate, name='cache_invalidate'),
]
