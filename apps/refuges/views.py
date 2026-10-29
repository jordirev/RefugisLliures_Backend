"""
Vistes de `refuges`: llista/cerca, detall, llista de mitjans i esborrat d'un mitjà.

Les vistes només validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures) i serialitzen.
El context de RLS (`app.uid`, `app.is_admin`) el fixa el hook de `apps/core/rls_hook.py` abans dels permisos.
El contracte JSON és el d'abans (IDs *string*, `coord: {lat, long}`, `info_comp` 0/1) llevat de `visitors` (només
admins) i `condition` (0-3, arrodonida half-to-even).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth.permissions import HasProfile, is_firebase_admin
from apps.audit import services as audit
from apps.uploads import r2_media_service
from apps.core.swagger.error_responses import (
    ERROR_400_INVALID_PARAMS,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_NOT_MEDIA_OWNER,
    ERROR_404_MEDIA_NOT_FOUND,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR,
)
from apps.core.swagger.examples import (
    EXAMPLE_REFUGI_COLOMERS_DETAILED,
    EXAMPLE_REFUGI_MEDIA_LIST,
    EXAMPLE_REFUGI_SEARCH_RESPONSE,
)

from apps.core.errors import server_error

from . import selectors, services
from .serializers import (
    RefugeMapResponseSerializer,
    RefugeMediaDeleteResponseSerializer,
    RefugeMediaListResponseSerializer,
    RefugiSearchFiltersSerializer,
    RefugiSearchResponseSerializer,
    RefugiSerializer,
    media_to_dict,
    refuge_to_dict,
)

logger = logging.getLogger(__name__)

PRESIGN_SECONDS = 3600          # URLs prefirmades vàlides 1 hora


def _viewer(request):
    """(autenticat, uid, admin) de qui fa la petició."""
    user = getattr(request, 'user', None)
    authenticated = bool(user and getattr(user, 'is_authenticated', False))
    return (authenticated, getattr(request, 'user_uid', None) if authenticated else None,
            authenticated and is_firebase_admin(request))


def _presigner():
    service = r2_media_service.get_refugi_media_service()
    return lambda key: service.generate_presigned_url(key, PRESIGN_SECONDS)


ERR_MAP = 'Error de base de dades en obtenir el mapa de refugis'
ERR_SEARCH = 'Error de base de dades en cercar refugis'
ERR_DETAIL = 'Error de base de dades en obtenir el refugi'
ERR_MEDIA_DB = 'Error de base de dades en obtenir els mitjans del refugi'
ERR_PRESIGN = 'Error en generar la URL de la imatge'
ERR_R2_DELETE = 'Error en esborrar el fitxer a R2'
ERR_DELETE = 'Error de base de dades en esborrar el mitjà'


class RefugeCollectionAPIView(APIView):
    """GET /api/refuges/: coordenades de tots els refugis (sense filtres) o refugis complets (amb filtres)."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Refuges'],
        operation_description=(
            "Obté una llista de refugis amb filtres opcionals. "
            "\n- Sense filtres: coordenades de tots els refugis. "
            "\n- Amb filtres: els refugis complets que els compleixen. "
            "\n- `name` cerca (parcial, sense accents ni majúscules) pel nom i l'àlies; "
            "`type` i `condition` accepten diversos valors separats per comes. "
            "\n\n**Autenticació:** opcional. Amb token, la resposta inclou `images_metadata` (i `visitors` per als admins)."
        ),
        manual_parameters=[
            openapi.Parameter('name', openapi.IN_QUERY, description='Nom del refugi (cerca parcial)',
                              type=openapi.TYPE_STRING, required=False),
            openapi.Parameter('type', openapi.IN_QUERY, description='Tipus de refugi (separats per comes)',
                              type=openapi.TYPE_ARRAY,
                              items=openapi.Items(type=openapi.TYPE_STRING),   # valors: catàleg refuges.refuge_types
                              required=False),
            openapi.Parameter('condition', openapi.IN_QUERY,
                              description='Condició (separades per comes). 0: pobre, 1: correcte, 2: bé, 3: excel·lent.',
                              type=openapi.TYPE_ARRAY,
                              items=openapi.Items(type=openapi.TYPE_STRING, enum=['0', '1', '2', '3']),
                              required=False),
            openapi.Parameter('altitude_min', openapi.IN_QUERY, description='Altitud mínima (m)',
                              type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('altitude_max', openapi.IN_QUERY, description='Altitud màxima (m)',
                              type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('places_min', openapi.IN_QUERY, description='Places mínimes',
                              type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('places_max', openapi.IN_QUERY, description='Places màximes',
                              type=openapi.TYPE_INTEGER, required=False),
        ],
        responses={
            200: openapi.Response(description='Llista de refugis o de coordenades',
                                  schema=RefugiSearchResponseSerializer,
                                  examples={'application/json': EXAMPLE_REFUGI_SEARCH_RESPONSE}),
            400: ERROR_400_INVALID_PARAMS,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def get(self, request):
        filters_serializer = RefugiSearchFiltersSerializer(data=request.GET)
        if not filters_serializer.is_valid():
            return Response({'error': 'Invalid query parameters', 'details': filters_serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        filters = filters_serializer.validated_data
        if not selectors.has_active_filters(filters):
            try:
                rows = selectors.list_map_points()
            except Exception as exc:
                return server_error(ERR_MAP, exc, logger=logger)
            points = [{'id': str(p['id']), 'name': p['name'], 'coord': {'lat': p['lat'], 'long': p['lng']},
                       'geohash': p['geohash']} for p in rows]
            return Response(RefugeMapResponseSerializer({'count': len(points), 'results': points}).data)

        authenticated, uid, admin = _viewer(request)
        try:
            refuges = selectors.search_refuges(filters, viewer_uid=uid, authenticated=authenticated, is_admin=admin)
        except Exception as exc:
            return server_error(ERR_SEARCH, exc, logger=logger)
        try:
            presign = _presigner() if authenticated else None
            visitors = selectors.get_visitor_uids_by_refuge([r.pk for r in refuges]) if admin else None
            results = [
                refuge_to_dict(
                    r,
                    media=[media_to_dict(m, presign) for m in selectors.media_of(r)] if authenticated else None,
                    visitors=visitors.get(r.pk, []) if admin else None)
                for r in refuges]
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)
        return Response(RefugiSearchResponseSerializer(
            {'count': len(results), 'results': results}, context={'is_authenticated': authenticated}).data)


class RefugeDetailAPIView(APIView):
    """GET /api/refuges/{id}/: detall d'un refugi."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Refuges'],
        operation_description=(
            "Obté els detalls complets d'un refugi per ID. "
            "\n\n**Autenticació:** opcional. Amb token, la resposta inclou `images_metadata` (i `visitors` per als admins)."
        ),
        manual_parameters=[openapi.Parameter('id', openapi.IN_PATH, description='Identificador del refugi (UUID)',
                                             type=openapi.TYPE_STRING, required=True)],
        responses={
            200: openapi.Response(description='Detalls del refugi', schema=RefugiSerializer,
                                  examples={'application/json': EXAMPLE_REFUGI_COLOMERS_DETAILED}),
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def get(self, request, id):
        try:
            refuge = selectors.get_refuge(id)
        except Exception as exc:
            return server_error(ERR_DETAIL, exc, logger=logger)
        if refuge is None:
            return Response({'error': 'Refugi not found'}, status=status.HTTP_404_NOT_FOUND)
        authenticated, uid, admin = _viewer(request)
        media = None
        if authenticated:
            try:
                rows = selectors.get_refuge_media(refuge.pk, uid, admin)
            except Exception as exc:
                return server_error(ERR_MEDIA_DB, exc, logger=logger)
            try:
                presign = _presigner()
                media = [media_to_dict(m, presign) for m in rows]
            except Exception as exc:
                return server_error(ERR_PRESIGN, exc, logger=logger)
        data = refuge_to_dict(refuge, media=media, visitors=selectors.get_visitor_uids(refuge.pk) if admin else None)
        return Response(RefugiSerializer(data, context={'is_authenticated': authenticated}).data)


class RefugeMediaListAPIView(APIView):
    """GET /api/refuges/{id}/media/: mitjans del refugi (la pujada és `POST /api/media/upload-intents/` + confirm)."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=['Refuge Media'],
        operation_description=(
            "Obté els mitjans (imatges i vídeos) d'un refugi amb URLs prefirmades, en forma MediaItem. "
            "Els mitjans ocults o retirats només els veuen el seu autor i els admins. Requereix autenticació."
        ),
        manual_parameters=[openapi.Parameter('id', openapi.IN_PATH, description='ID del refugi',
                                             type=openapi.TYPE_STRING, required=True)],
        responses={
            200: openapi.Response(description='Llista de mitjans', schema=RefugeMediaListResponseSerializer,
                                  examples={'application/json': EXAMPLE_REFUGI_MEDIA_LIST}),
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def get(self, request, id):
        _, uid, admin = _viewer(request)
        try:
            if not selectors.refuge_exists(id):
                return Response({'error': 'Refugi not found'}, status=status.HTTP_404_NOT_FOUND)
            rows = selectors.get_refuge_media(id, uid, admin)
        except Exception as exc:
            return server_error(ERR_MEDIA_DB, exc, logger=logger)
        try:
            presign = _presigner()
            media = [media_to_dict(m, presign) for m in rows]
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)
        # Registre d'accés a mitjans (art. 32 RGPD)
        audit.audit_log_service.log(uid, audit.ACTION_MEDIA_LIST, 'refuge', str(id), {'count': len(media)})
        return Response(RefugeMediaListResponseSerializer({'media': media}).data)


class RefugeMediaDetailAPIView(APIView):
    """DELETE /api/refuges/{id}/media/{key}/: esborra un mitjà (autor o admin)."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=['Refuge Media'],
        operation_description=(
            "Elimina un mitjà d'un refugi (fila i fitxer a R2). Requereix autenticació i ser l'autor del mitjà "
            "o administrador. Si R2 no pot esborrar el fitxer, la fila es conserva (500)."
        ),
        manual_parameters=[
            openapi.Parameter('id', openapi.IN_PATH, description='ID del refugi', type=openapi.TYPE_STRING,
                              required=True),
            openapi.Parameter('key', openapi.IN_PATH, description='Clau del mitjà (path complet a R2)',
                              type=openapi.TYPE_STRING, required=True),
        ],
        responses={
            200: openapi.Response(description='Mitjà eliminat', schema=RefugeMediaDeleteResponseSerializer),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_NOT_MEDIA_OWNER,
            404: ERROR_404_MEDIA_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR,
        },
    )
    def delete(self, request, id, key):
        _, uid, admin = _viewer(request)
        try:
            services.delete_media(refuge_id=id, key=key, actor_uid=uid, is_admin=admin)
        except services.MediaForbidden as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except services.MediaNotFound as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except services.MediaStorageError as exc:
            return server_error(ERR_R2_DELETE, exc, logger=logger)
        except Exception as exc:
            return server_error(ERR_DELETE, exc, logger=logger)
        return Response({'success': True, 'message': 'Mitjà eliminat correctament', 'key': key})
