"""Rutes de `uploads`: s'inclouen des de `refugis_lliures/urls.py` a l'arrel de l'API (mateixos paths i `name=` d'abans)."""
from django.urls import path

from .views import UploadIntentsAPIView, UploadIntentsConfirmAPIView

urlpatterns = [
    # Pujada directa de mitjans (presigned PUT + confirm)
    path('media/upload-intents/', UploadIntentsAPIView.as_view(), name='media_upload_intents'),  # POST
    path('media/upload-intents/confirm/', UploadIntentsConfirmAPIView.as_view(), name='media_upload_intents_confirm'),  # POST
]
