"""
Vistes de `moderation`: denunciar un mitjà, llistar i resoldre denúncies (admins) i avisos de moderació de l'usuari.

POST  /api/media/reports/                        IsAuthenticated + HasProfile + IsNotBlocked + IsAgeConfirmed
GET   /api/admin/media-reports/                  IsAuthenticated + HasProfile + IsFirebaseAdmin
PATCH /api/admin/media-reports/{id}/             IsAuthenticated + HasProfile + IsFirebaseAdmin
GET   /api/users/{uid}/moderation-notices/       IsAuthenticated + HasProfile + IsSameUser (només el mateix usuari, D41)

Les vistes només validen l'entrada, criden `selectors.x(...)` / `services.x(...)` com a atributs de mòdul i serialitzen
(el context de RLS el fixa el hook de `api/rls_hook.py`). Ordre: permisos -> validació (400) -> existència (404) -> estat
(403/409). Els 500 porten `{error, error_id}` (`server_error`), mai el text de l'excepció.
"""
import json
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasProfile, IsAgeConfirmed, IsFirebaseAdmin, IsNotBlocked, IsSameUser, coded_error
from api.services import r2_media_service
from api.utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA, ERROR_401_UNAUTHORIZED, ERROR_403_ADMIN_ONLY, ERROR_403_FORBIDDEN,
    ERROR_403_REPORT_FORBIDDEN, ERROR_404_MEDIA_NOT_FOUND, ERROR_404_REPORT_NOT_FOUND, ERROR_409_ALREADY_REPORTED,
    ERROR_409_ALREADY_RESOLVED, ERROR_500_INTERNAL_ERROR)
from api.utils.swagger_examples import (
    EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_REQUEST, EXAMPLE_ADMIN_MEDIA_REPORT_RESOLVE_RESPONSE,
    EXAMPLE_ADMIN_MEDIA_REPORTS_LIST, EXAMPLE_MEDIA_REPORT_REQUEST, EXAMPLE_MEDIA_REPORT_RESPONSE,
    EXAMPLE_MODERATION_NOTICES)
from apps.audit import services as audit
from apps.core.errors import server_error

from . import selectors, services
from .serializers import (
    MediaReportCreateSerializer, MediaReportListQuerySerializer, MediaReportResolveSerializer,
    MediaReportResponseSerializer, ModerationNoticeSerializer, notice_to_dict, report_row_to_dict)

logger = logging.getLogger(__name__)

ERR_CREATE = 'Error de base de dades en crear la denúncia'
ERR_LIST = 'Error en obtenir les denúncies'
ERR_RESOLVE = 'Error de base de dades en resoldre la denúncia'
ERR_HOLD = "Error en conservar l'evidència a R2"
ERR_NOTICES = 'Error de base de dades en obtenir els avisos de moderació'

PRESIGN_SECONDS = 3600


def _uid(request):
    return getattr(request, 'user_uid', None) or getattr(getattr(request, 'user', None), 'uid', None)


def _invalid_data(errors):
    return Response({'error': 'Dades invàlides', 'details': errors}, status=status.HTTP_400_BAD_REQUEST)


# ========== /api/media/reports/ ==========

class MediaReportsAPIView(APIView):
    """Denúncia d'un mitjà per part d'un usuari"""
    permission_classes = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Denuncia un mitjà (de refugi o d'experiència). `details` és obligatori si `reason` = other (≤ 1000 "
            "caràcters). L'`id` és un UUID opac.\n\n"
            "Autoocultació immediata (prioritat alta): child_sexual_abuse, child_endangerment, "
            "sexual_nonconsensual, terrorism_extremism, my_image. La resta s'oculta a partir de 3 "
            "denunciants diferents.\n\n"
            "403 own_media si l'autor denuncia el seu propi mitjà · 409 already_reported si ja l'havia denunciat · "
            "404 si el mitjà és retirat o evidència retinguda.\n\n"
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
        serializer = MediaReportCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid_data(serializer.errors)
        data = serializer.validated_data
        try:
            result = services.create_report(
                reporter_uid=_uid(request), refuge_id=data['refuge_id'], media_key=data['media_key'],
                reason=data['reason'], details=data.get('details'))
        except services.RefugeNotFound:
            return Response({'error': 'Refugi not found'}, status=status.HTTP_404_NOT_FOUND)
        except services.MediaNotFound:
            return Response({'error': 'Media not found'}, status=status.HTTP_404_NOT_FOUND)
        except services.OwnMedia:
            return Response(coded_error('own_media', 'No pots denunciar un contingut que has publicat tu'),
                            status=status.HTTP_403_FORBIDDEN)
        except services.AlreadyReported:
            return Response(coded_error('already_reported', 'Ja has denunciat aquest contingut'),
                            status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return Response(result, status=status.HTTP_201_CREATED)


# ========== /api/admin/media-reports/ ==========

class AdminMediaReportsAPIView(APIView):
    """Llistat de denúncies per a moderadors"""
    permission_classes = [IsAuthenticated, HasProfile, IsFirebaseAdmin]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Llista les denúncies (prioritat alta primer, després per data). Cada denúncia porta `media` (MediaItem + "
            "status) si el mitjà encara existeix; l'evidència retinguda a moderation-hold/ no es previsualitza. "
            "`reporter_uid` és `system` en les automàtiques i `unknown` en les anonimitzades.\n\n"
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
        query = MediaReportListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _invalid_data(query.errors)
        report_status = query.validated_data['status']
        try:
            rows = selectors.list_reports(report_status)
            service = r2_media_service.get_refugi_media_service()
            reports = [report_row_to_dict(row, lambda key: service.generate_presigned_url(key, PRESIGN_SECONDS))
                       for row in rows]
            audit.audit_log_service.log(_uid(request), audit.ACTION_REPORTS_LIST, 'media_reports', report_status,
                                        {'count': len(reports)})
        except Exception as exc:
            return server_error(ERR_LIST, exc, logger=logger)
        return Response({'count': len(reports), 'reports': reports}, status=status.HTTP_200_OK)


class AdminMediaReportDetailAPIView(APIView):
    """Resolució d'una denúncia per un moderador"""
    permission_classes = [IsAuthenticated, HasProfile, IsFirebaseAdmin]

    @swagger_auto_schema(
        tags=['Media Moderation'],
        operation_description=(
            "Resol la denúncia (i totes les pendents del mateix mitjà, amb una sola decisió).\n"
            "- dismiss: el mitjà torna a ser visible\n"
            "- remove: status = removed\n"
            "- remove_and_strike: removed + 1 strike; amb 3 strikes o CSAM confirmat → user.is_blocked = true\n"
            "- CSAM confirmat: el fitxer es mou a moderation-hold/ (si R2 falla, 500 i res no canvia)\n\n"
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
        serializer = MediaReportResolveSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid_data(serializer.errors)
        try:
            result = services.resolve_report(
                report_id=id, action=serializer.validated_data['action'],
                statement=serializer.validated_data['statement'], admin_uid=_uid(request))
        except services.ReportNotFound:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
        except services.AlreadyResolved:
            return Response(coded_error('already_resolved', 'La denúncia ja està resolta'),
                            status=status.HTTP_409_CONFLICT)
        except services.EvidenceHoldError as exc:
            return server_error(ERR_HOLD, exc, logger=logger)
        except Exception as exc:
            return server_error(ERR_RESOLVE, exc, logger=logger)
        return Response(result, status=status.HTTP_200_OK)


# ========== /api/users/{uid}/moderation-notices/ ==========

class UserModerationNoticesAPIView(APIView):
    """GET: avisos de moderació de l'usuari (declaració de motius, art. 17 DSA)"""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Llista els avisos de moderació de l'usuari (més recents primer): ocultacions cautelars, "
            "retirades, strikes, bloquejos i restauracions, amb la motivació i la via de recurs. Només el mateix usuari."
        ),
        responses={
            200: openapi.Response(description='Avisos de moderació',
                                  examples={'application/json': EXAMPLE_MODERATION_NOTICES}),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            500: ERROR_500_INTERNAL_ERROR,
        }
    )
    def get(self, request, uid):
        try:
            notices = [notice_to_dict(n) for n in selectors.list_notices(uid)]
        except Exception as exc:
            return server_error(ERR_NOTICES, exc, logger=logger)
        return Response({'notices': ModerationNoticeSerializer(notices, many=True).data}, status=status.HTTP_200_OK)
