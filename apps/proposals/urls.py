"""Rutes de `proposals`: s'inclouen des d'`api/urls.py` a l'arrel (mateixos paths i `name=` d'abans)."""
from django.urls import path

from . import views

urlpatterns = [
    path('refuges-proposals/', views.ProposalCollectionAPIView.as_view(),
         name='refuge_proposal_collection'),                                     # POST (crear) + GET (llistar; admin)
    path('my-refuges-proposals/', views.MyProposalCollectionAPIView.as_view(),
         name='my_refuge_proposal_collection'),                                  # GET (les pròpies)
    path('refuges-proposals/<str:proposal_id>/approve/', views.ProposalApproveAPIView.as_view(),
         name='refuge_proposal_approve'),                                        # POST (admin)
    path('refuges-proposals/<str:proposal_id>/reject/', views.ProposalRejectAPIView.as_view(),
         name='refuge_proposal_reject'),                                         # POST (admin)
]
