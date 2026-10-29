"""
Vistes d'`uploads`: pujada directa de mitjans (intents amb URL PUT prefirmada + confirmació).

POST /api/media/upload-intents/            IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed
POST /api/media/upload-intents/confirm/    IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed

Les vistes només validen l'entrada, criden els `services` i serialitzen. El context de RLS el fixa el hook de
`apps/core/rls_hook.py`. Ordre de comprovacions: permisos -> validació del cos (400) -> existència (404) -> propietat (403).
Els intents viuen a PostgreSQL (`moderation.upload_intents`); les rutes (`media_upload_intents`,
`media_upload_intents_confirm`) s'afegeixen des de `apps/uploads/urls.py` perquè comparteixen prefix amb les denúncies.
"""
import json
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked, coded_error, is_firebase_admin
from apps.core.swagger.error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_UPLOAD_FORBIDDEN,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR,
)
from apps.core.swagger.examples import (
    EXAMPLE_UPLOAD_CONFIRM_REQUEST,
    EXAMPLE_UPLOAD_CONFIRM_RESPONSE,
    EXAMPLE_UPLOAD_INTENT_REQUEST,
    EXAMPLE_UPLOAD_INTENT_RESPONSE,
)
from apps.core.errors import server_error

from . import services
from .serializers import (
    UploadConfirmResponseSerializer,
    UploadConfirmSerializer,
    UploadIntentCreateSerializer,
    UploadIntentResponseSerializer,
)

logger = logging.getLogger(__name__)

ERR_CREATE = 'Error en crear els intents de pujada'
ERR_CONFIRM = 'Error en confirmar les pujades'

NOT_OWNER_MESSAGE = "No ets el creador d'aquesta experiència"
TOO_MANY_PENDING_MESSAGE = (
    'Tens massa pujades pendents. Espera que acabin (o que caduquin) abans de començar-ne de noves')


def _invalid(serializer):
    return Response({'error': 'Dades invàlides', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class UploadIntentsAPIView(APIView):
    """Crea intents de pujada directa (URL PUT prefirmades a quarantine/)."""
    permission_classes = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]

    @swagger_auto_schema(
        tags=['Media Upload'],
        operation_description=(
            "Crea fins a 10 intents de pujada. Per a cada fitxer es retorna una URL PUT prefirmada "
            "(600 s) a `quarantine/{upload_id}` amb Content-Type i Content-Length signats. "
            "Després de pujar els bytes cal cridar `/api/media/upload-intents/confirm/`.\n\n"
            "Límits: imatge ≤ 15 MB (jpeg/png/webp/heic/heif), vídeo ≤ 50 MB (mp4/quicktime/webm); "
            "l'avatar només accepta una imatge.\n\n"
            "Requereix autenticació, edat confirmada i compte no bloquejat.\n\n"
            f"Quota: com a molt {services.MAX_PENDING_INTENTS} intents pendents (sense confirmar ni caducar) per "
            "usuari; si se supera, 429 `too_many_pending_uploads`.\n\n"
            f"Exemple de petició: `{json.dumps(EXAMPLE_UPLOAD_INTENT_REQUEST)}`"
        ),
        request_body=UploadIntentCreateSerializer,
        responses={
            201: openapi.Response('Intents creats', UploadIntentResponseSerializer,
                                  examples={'application/json': EXAMPLE_UPLOAD_INTENT_RESPONSE}),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_UPLOAD_FORBIDDEN,
            404: ERROR_404_REFUGI_NOT_FOUND,
            429: 'Massa intents de pujada pendents (`too_many_pending_uploads`)',
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def post(self, request):
        serializer = UploadIntentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        data = serializer.validated_data
        try:
            result = services.create_upload_intents(
                uid=getattr(request, 'user_uid', None),
                target=data['target'],
                files=[{'content_type': f['content_type'], 'size': f['size']} for f in data['files']],
                refuge_id=data.get('refuge_id'),
                experience_id=data.get('experience_id'),
                is_admin=is_firebase_admin(request),
            )
        except (services.RefugeNotFound, services.ExperienceNotFound) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except services.NotOwner:
            return Response(coded_error('not_owner', NOT_OWNER_MESSAGE), status=status.HTTP_403_FORBIDDEN)
        except services.InvalidRefuge as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except services.TooManyPendingUploads:
            return Response(coded_error('too_many_pending_uploads', TOO_MANY_PENDING_MESSAGE),
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return Response(result, status=status.HTTP_201_CREATED)


class UploadIntentsConfirmAPIView(APIView):
    """Confirma i processa fitxers pujats a quarantine/."""
    permission_classes = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]

    @swagger_auto_schema(
        tags=['Media Upload'],
        operation_description=(
            "Processa els fitxers pujats: comprova mida i tipus real (magic bytes + obertura), "
            "recodifica (WebP 2048 px + miniatura 400 px; vídeo sense metadades + pòster), elimina "
            "EXIF/GPS, passa la moderació per hash i publica amb clau UUID.\n\n"
            "`failed[].reason` ∈ missing_object | too_large | invalid_type | processing_error | moderation_blocked. "
            "Idempotent: confirmar dues vegades el mateix upload_id retorna el mateix MediaItem.\n\n"
            f"Exemple de petició: `{json.dumps(EXAMPLE_UPLOAD_CONFIRM_REQUEST)}`"
        ),
        request_body=UploadConfirmSerializer,
        responses={
            200: openapi.Response('Resultat del processament', UploadConfirmResponseSerializer,
                                  examples={'application/json': EXAMPLE_UPLOAD_CONFIRM_RESPONSE}),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_UPLOAD_FORBIDDEN,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def post(self, request):
        serializer = UploadConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            result = services.confirm_upload_intents(uid=getattr(request, 'user_uid', None),
                                                     upload_ids=serializer.validated_data['upload_ids'])
        except Exception as exc:
            return server_error(ERR_CONFIRM, exc, logger=logger)
        return Response(result, status=status.HTTP_200_OK)
