"""
Views de pujada directa de mitjans, denúncies i moderació (feature images).

POST  /api/media/upload-intents/            IsAuthenticated + IsNotBlocked + IsAgeConfirmed
POST  /api/media/upload-intents/confirm/    IsAuthenticated + IsNotBlocked + IsAgeConfirmed
POST  /api/media/reports/                   IsAuthenticated + IsNotBlocked + IsAgeConfirmed
GET   /api/admin/media-reports/             IsAuthenticated + IsFirebaseAdmin
PATCH /api/admin/media-reports/{id}/        IsAuthenticated + IsFirebaseAdmin
"""
import json
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..controllers.media_upload_controller import (
    MediaUploadController, ERROR_NOT_OWNER, ERROR_INVALID_PREFIX,
)
from ..controllers.media_report_controller import (
    MediaReportController, ERROR_OWN_MEDIA, ERROR_ALREADY_REPORTED, ERROR_ALREADY_RESOLVED,
)
from ..permissions import (
    IsAgeConfirmed, IsNotBlocked, IsFirebaseAdmin, is_firebase_admin, coded_error,
)
from ..serializers.media_serializer import (
    UploadIntentCreateSerializer, UploadIntentResponseSerializer, UploadConfirmSerializer,
    UploadConfirmResponseSerializer, MediaReportCreateSerializer, MediaReportResponseSerializer,
    MediaReportListQuerySerializer, MediaReportResolveSerializer,
)
from ..utils.swagger_examples import (
    EXAMPLE_UPLOAD_INTENT_REQUEST, EXAMPLE_UPLOAD_INTENT_RESPONSE, EXAMPLE_UPLOAD_CONFIRM_REQUEST,
    EXAMPLE_UPLOAD_CONFIRM_RESPONSE, EXAMPLE_MEDIA_REPORT_REQUEST, EXAMPLE_MEDIA_REPORT_RESPONSE,
    EXAMPLE_ADMIN_MEDIA_REPORTS_LIST, EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_REQUEST,
    EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_RESPONSE,
)
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA, ERROR_401_UNAUTHORIZED, ERROR_403_ADMIN_ONLY, ERROR_403_UPLOAD_FORBIDDEN,
    ERROR_403_REPORT_FORBIDDEN, ERROR_404_REFUGI_NOT_FOUND, ERROR_404_MEDIA_NOT_FOUND,
    ERROR_404_REPORT_NOT_FOUND, ERROR_409_ALREADY_REPORTED, ERROR_409_ALREADY_RESOLVED,
    ERROR_500_INTERNAL_ERROR,
)

logger = logging.getLogger(__name__)

INTERNAL_SERVER_ERROR = "Error intern del servidor"


def _uid(request):
    return getattr(request, 'user_uid', None) or getattr(getattr(request, 'user', None), 'uid', None)


def _invalid_data(errors):
    return Response({'error': 'Dades invàlides', 'details': errors}, status=status.HTTP_400_BAD_REQUEST)


# ========== /api/media/upload-intents/ ==========

class UploadIntentsAPIView(APIView):
    """Crea intents de pujada directa (URL PUT prefirmades a quarantine/)"""
    permission_classes = [IsAuthenticated, IsNotBlocked, IsAgeConfirmed]

    @swagger_auto_schema(
        tags=['Media Upload'],
        operation_description=(
            "Crea fins a 10 intents de pujada. Per a cada fitxer es retorna una URL PUT prefirmada "
            "(600 s) a `quarantine/{upload_id}` amb Content-Type i Content-Length signats. "
            "Després de pujar els bytes cal cridar `/api/media/upload-intents/confirm/`.\n\n"
            "Límits: imatge ≤ 15 MB (jpeg/png/webp/heic/heif), vídeo ≤ 50 MB (mp4/quicktime/webm); "
            "l'avatar només accepta una imatge.\n\n"
            "Requereix autenticació, edat confirmada i compte no bloquejat.\n\n"
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
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def post(self, request):
        try:
            serializer = UploadIntentCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return _invalid_data(serializer.errors)
            data = serializer.validated_data

            result, error = MediaUploadController().create_upload_intents(
                uid=_uid(request),
                target=data['target'],
                files=[{'content_type': f['content_type'], 'size': f['size']} for f in data['files']],
                refuge_id=data.get('refuge_id'),
                experience_id=data.get('experience_id'),
                is_admin=is_firebase_admin(request),
            )
            if error:
                if error == ERROR_NOT_OWNER:
                    return Response(coded_error('not_owner', "No ets el creador d'aquesta experiència"),
                                    status=status.HTTP_403_FORBIDDEN)
                if 'not found' in error.lower():
                    return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
                if error.startswith(ERROR_INVALID_PREFIX):
                    return Response({'error': error[len(ERROR_INVALID_PREFIX):].strip()},
                                    status=status.HTTP_400_BAD_REQUEST)
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creant intents de pujada: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadIntentsConfirmAPIView(APIView):
    """Confirma i processa fitxers pujats a quarantine/"""
    permission_classes = [IsAuthenticated, IsNotBlocked, IsAgeConfirmed]

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
        try:
            serializer = UploadConfirmSerializer(data=request.data)
            if not serializer.is_valid():
                return _invalid_data(serializer.errors)

            result, error = MediaUploadController().confirm_upload_intents(
                _uid(request), serializer.validated_data['upload_ids']
            )
            if error:
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error confirmant pujades: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== /api/media/reports/ ==========

class MediaReportsAPIView(APIView):
    """Denúncia d'un mitjà per part d'un usuari"""
    permission_classes = [IsAuthenticated, IsNotBlocked, IsAgeConfirmed]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Denuncia un mitjà. `details` és obligatori si `reason` = other (≤ 1000 caràcters).\n\n"
            "Autoocultació immediata (prioritat alta): child_sexual_abuse, child_endangerment, "
            "sexual_nonconsensual, terrorism_extremism, my_image. La resta s'oculta a partir de 3 "
            "denunciants diferents.\n\n"
            "403 own_media si l'autor denuncia el seu propi mitjà · 409 already_reported si ja l'havia denunciat.\n\n"
            f"Exemple de petició: `{json.dumps(EXAMPLE_MEDIA_REPORT_REQUEST, ensure_ascii=False)}`"
        ),
        request_body=MediaReportCreateSerializer,
        responses={
            201: openapi.Response('Denúncia creada', MediaReportResponseSerializer,
                                  examples={'application/json': EXAMPLE_MEDIA_REPORT_RESPONSE}),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_REPORT_FORBIDDEN,
            404: ERROR_404_MEDIA_NOT_FOUND,
            409: ERROR_409_ALREADY_REPORTED,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def post(self, request):
        try:
            serializer = MediaReportCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return _invalid_data(serializer.errors)
            data = serializer.validated_data

            result, error = MediaReportController().create_report(
                reporter_uid=_uid(request),
                refuge_id=data['refuge_id'],
                media_key=data['media_key'],
                reason=data['reason'],
                details=data.get('details'),
            )
            if error:
                if error == ERROR_OWN_MEDIA:
                    return Response(coded_error('own_media', "No pots denunciar un contingut que has publicat tu"),
                                    status=status.HTTP_403_FORBIDDEN)
                if error == ERROR_ALREADY_REPORTED:
                    return Response(coded_error('already_reported', "Ja has denunciat aquest contingut"),
                                    status=status.HTTP_409_CONFLICT)
                if 'not found' in error.lower():
                    return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
                if error.startswith('invalid:'):
                    return Response({'error': error[len('invalid:'):].strip()}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creant denúncia: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== /api/admin/media-reports/ ==========

class AdminMediaReportsAPIView(APIView):
    """Llistat de denúncies per a moderadors"""
    permission_classes = [IsAuthenticated, IsFirebaseAdmin]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Llista les denúncies (prioritat alta primer). Cada denúncia porta `media` (MediaItem + status) "
            "si el mitjà encara existeix; l'evidència retinguda a moderation-hold/ no es previsualitza.\n\n"
            "Requereix ser administrador."
        ),
        manual_parameters=[
            openapi.Parameter('status', openapi.IN_QUERY, type=openapi.TYPE_STRING,
                              enum=['pending', 'resolved'], default='pending', required=False),
        ],
        responses={
            200: openapi.Response('Llista de denúncies',
                                  examples={'application/json': EXAMPLE_ADMIN_MEDIA_REPORTS_LIST}),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_ADMIN_ONLY,
            500: ERROR_500_INTERNAL_ERROR,
        }
    )
    def get(self, request):
        try:
            query = MediaReportListQuerySerializer(data=request.query_params)
            if not query.is_valid():
                return _invalid_data(query.errors)
            reports, error = MediaReportController().list_reports(query.validated_data['status'], _uid(request))
            if error:
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'count': len(reports), 'reports': reports}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error llistant denúncies: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminMediaReportDetailAPIView(APIView):
    """Resolució d'una denúncia per un moderador"""
    permission_classes = [IsAuthenticated, IsFirebaseAdmin]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Resol la denúncia (i totes les pendents del mateix mitjà).\n"
            "- dismiss: el mitjà torna a ser visible\n"
            "- remove: status = removed\n"
            "- remove_and_strike: removed + 1 strike; amb 3 strikes o CSAM confirmat → user.is_blocked = true\n\n"
            "`statement` és la declaració de motius que rep l'usuari afectat (art. 17 DSA).\n\n"
            "Requereix ser administrador.\n\n"
            f"Exemple de petició: `{json.dumps(EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_REQUEST, ensure_ascii=False)}`"
        ),
        request_body=MediaReportResolveSerializer,
        responses={
            200: openapi.Response('Denúncia resolta',
                                  examples={'application/json': EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_RESPONSE}),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_ADMIN_ONLY,
            404: ERROR_404_REPORT_NOT_FOUND,
            409: ERROR_409_ALREADY_RESOLVED,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def patch(self, request, id):
        try:
            serializer = MediaReportResolveSerializer(data=request.data)
            if not serializer.is_valid():
                return _invalid_data(serializer.errors)
            result, error = MediaReportController().resolve_report(
                report_id=id,
                action=serializer.validated_data['action'],
                statement=serializer.validated_data['statement'],
                admin_uid=_uid(request),
            )
            if error:
                if error == ERROR_ALREADY_RESOLVED:
                    return Response(coded_error('already_resolved', "La denúncia ja està resolta"),
                                    status=status.HTTP_409_CONFLICT)
                if 'not found' in error.lower():
                    return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
                return Response({'error': error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error resolent denúncia: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
