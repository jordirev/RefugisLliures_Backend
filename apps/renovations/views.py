"""
Vistes de `renovations`: llista, detall, creació/edició/esborrat i participants (+ la llista d'un refugi).

Fines: validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures), serialitzen i tradueixen
les excepcions de domini a HTTP. El context de RLS el fixa el hook d'`apps/core/rls_hook.py`.

Permisos (gotcha 15): `IsAuthenticated, HasProfile` a tot; l'**escriptura de contingut** (`POST /renovations/`,
`PATCH /renovations/{id}/`, unir-se) exigeix a més `IsNotBlocked` i `IsAgeConfirmed` (decisió del PO, 26/10). Els
`GET` i els `DELETE` (esborrar la reforma pròpia, sortir-ne o expulsar algú) no: un usuari bloquejat pot llegir i
esborrar el que és seu. Es decideix per mètode a `get_permissions()`.
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked
from apps.core.swagger.error_responses import (
    ERROR_400_ALREADY_PARTICIPANT,
    ERROR_400_CREATOR_CANNOT_JOIN,
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_EXPELLED,
    ERROR_403_NOT_CREATOR,
    ERROR_404_RENOVATION_NOT_FOUND,
    ERROR_409_OVERLAP,
    ERROR_500_INTERNAL_ERROR,
    SUCCESS_204_NO_CONTENT,
)
from apps.core.swagger.examples import (
    EXAMPLE_RENOVATION_1,
    EXAMPLE_RENOVATION_CREATE,
    EXAMPLE_RENOVATION_PARTICIPANT_REMOVED,
    EXAMPLE_RENOVATION_UPDATED,
    EXAMPLE_RENOVATION_WITH_PARTICIPANTS,
    EXAMPLE_RENOVATIONS_LIST,
)
from apps.core.errors import server_error

from . import selectors, services
from .serializers import RenovationCreateSerializer, RenovationSerializer, RenovationUpdateSerializer

logger = logging.getLogger(__name__)

TAGS = ['Renovations']

# Missatges de domini (els 4xx poden dir què ha passat; els 500 són textos fixos per punt, sense `str(e)`)
MSG_INVALID = 'Dades invàlides'
MSG_RENOVATION_NOT_FOUND = 'Reforma no trobada'
MSG_REFUGE_NOT_FOUND = 'Refugi no trobat'
MSG_NOT_CREATOR_EDIT = 'Només el creador pot editar la reforma'
MSG_NOT_CREATOR_DELETE = 'Només el creador pot eliminar la reforma'
MSG_INVALID_DATES = "La data d'inici no pot ser posterior a la data de finalització"
MSG_OVERLAP = 'Hi ha una altra reforma que se solapa temporalment en aquest refugi'
MSG_CREATOR_CANNOT_JOIN = 'El creador no pot unir-se a la seva pròpia reforma'
MSG_EXPELLED = "Has estat expulsat d'aquesta reforma i no pots tornar a unir-t'hi"
MSG_ALREADY_PARTICIPANT = "L'usuari ja és participant d'aquesta reforma"
MSG_NOT_ALLOWED = 'No tens permís per eliminar aquest participant'
MSG_NOT_PARTICIPANT = "L'usuari no és participant d'aquesta reforma"

ERR_LIST = 'Error de base de dades en obtenir les reformes'
ERR_REFUGE_LIST = 'Error de base de dades en obtenir les reformes del refugi'
ERR_DETAIL = 'Error de base de dades en obtenir la reforma'
ERR_CREATE = 'Error de base de dades en crear la reforma'
ERR_UPDATE = 'Error de base de dades en actualitzar la reforma'
ERR_DELETE = 'Error de base de dades en esborrar la reforma'
ERR_JOIN = 'Error de base de dades en afegir el participant'
ERR_LEAVE = 'Error de base de dades en treure el participant'

READ_PERMISSIONS = (IsAuthenticated, HasProfile)
WRITE_PERMISSIONS = (IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed)


def _permissions(request, write_methods):
    """Permisos de lectura, o d'escriptura de contingut si el mètode és d'`write_methods`."""
    classes = WRITE_PERMISSIONS if request.method in write_methods else READ_PERMISSIONS
    return [cls() for cls in classes]


def _json(renovation, http_status=status.HTTP_200_OK):
    return Response(RenovationSerializer(renovation).data, status=http_status)


def _validation_error(serializer):
    return Response({'error': MSG_INVALID, 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


def _overlap_response(exc):
    body = {'error': MSG_OVERLAP}
    if exc.renovation is not None:
        body['overlapping_renovation'] = RenovationSerializer(exc.renovation).data
    return Response(body, status=status.HTTP_409_CONFLICT)


def _id_param(name='id'):
    return openapi.Parameter(name, openapi.IN_PATH, description='ID de la reforma (UUID)', type=openapi.TYPE_STRING,
                             required=True)


def _truthy(value) -> bool:
    return str(value).strip().lower() in ('true', '1')


# ========== /renovations/ ==========

class RenovationListAPIView(APIView):
    """GET: reformes vigents (`fin_date >= avui`); POST: crea una reforma (bloquejats i menors no)."""

    def get_permissions(self):
        return _permissions(self.request, write_methods=('POST',))

    @swagger_auto_schema(
        tags=TAGS,
        operation_description='Obté les reformes vigents (les que no han acabat), ordenades per data d\'inici. '
                              '`group_link` només hi és per al creador, els participants i els admins.',
        responses={200: openapi.Response('Llista de reformes', RenovationSerializer(many=True),
                                         examples={'application/json': EXAMPLE_RENOVATIONS_LIST}),
                   401: ERROR_401_UNAUTHORIZED, 500: ERROR_500_INTERNAL_ERROR})
    def get(self, request):
        try:
            renovations = selectors.list_active_renovations()
            return Response(RenovationSerializer(renovations, many=True).data)
        except Exception as exc:
            return server_error(ERR_LIST, exc, logger=logger)

    @swagger_auto_schema(
        tags=TAGS,
        operation_description='Crea una reforma (reformes d\'un sol dia permeses; sense solapaments al refugi).',
        request_body=RenovationCreateSerializer,
        responses={201: openapi.Response('Reforma creada', RenovationSerializer,
                                         examples={'application/json': EXAMPLE_RENOVATION_CREATE}),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 409: ERROR_409_OVERLAP,
                   500: ERROR_500_INTERNAL_ERROR})
    def post(self, request):
        serializer = RenovationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(serializer)
        try:
            renovation = services.create_renovation(request.user_uid, **serializer.validated_data)
        except services.RefugeNotFound:
            return Response({'error': MSG_REFUGE_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        except services.OverlappingRenovation as exc:
            return _overlap_response(exc)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return _json(renovation, status.HTTP_201_CREATED)


# ========== /renovations/{id}/ ==========

class RenovationAPIView(APIView):
    """GET: detall; PATCH: edita (només el creador); DELETE: esborra (només el creador)."""

    def get_permissions(self):
        return _permissions(self.request, write_methods=('PATCH',))

    @swagger_auto_schema(
        tags=TAGS, operation_description='Obté una reforma (també les acabades).', manual_parameters=[_id_param()],
        responses={200: openapi.Response('Reforma', RenovationSerializer,
                                         examples={'application/json': EXAMPLE_RENOVATION_1}),
                   401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_RENOVATION_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR})
    def get(self, request, id):
        try:
            renovation = selectors.get_renovation(id)
        except Exception as exc:
            return server_error(ERR_DETAIL, exc, logger=logger)
        if renovation is None:
            return Response({'error': MSG_RENOVATION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        return _json(renovation)

    @swagger_auto_schema(
        tags=TAGS, operation_description='Edita els camps enviats (només el creador; ni tan sols un admin).',
        manual_parameters=[_id_param()], request_body=RenovationUpdateSerializer,
        responses={200: openapi.Response('Reforma actualitzada', RenovationSerializer,
                                         examples={'application/json': EXAMPLE_RENOVATION_UPDATED}),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_NOT_CREATOR,
                   404: ERROR_404_RENOVATION_NOT_FOUND, 409: ERROR_409_OVERLAP, 500: ERROR_500_INTERNAL_ERROR})
    def patch(self, request, id):
        serializer = RenovationUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(serializer)
        try:
            renovation = services.update_renovation(id, request.user_uid, **serializer.validated_data)
        except services.RenovationNotFound:
            return Response({'error': MSG_RENOVATION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        except services.NotRenovationCreator:
            return Response({'error': MSG_NOT_CREATOR_EDIT}, status=status.HTTP_403_FORBIDDEN)
        except services.InvalidDates:
            return Response({'error': MSG_INVALID_DATES}, status=status.HTTP_400_BAD_REQUEST)
        except services.OverlappingRenovation as exc:
            return _overlap_response(exc)
        except Exception as exc:
            return server_error(ERR_UPDATE, exc, logger=logger)
        return _json(renovation)

    @swagger_auto_schema(
        tags=TAGS, operation_description='Esborra la reforma (només el creador).', manual_parameters=[_id_param()],
        responses={204: SUCCESS_204_NO_CONTENT, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_NOT_CREATOR,
                   404: ERROR_404_RENOVATION_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, id):
        try:
            services.delete_renovation(id, request.user_uid)
        except services.RenovationNotFound:
            return Response({'error': MSG_RENOVATION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        except services.NotRenovationCreator:
            return Response({'error': MSG_NOT_CREATOR_DELETE}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return server_error(ERR_DELETE, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== /renovations/{id}/participants/ ==========

class RenovationParticipantsAPIView(APIView):
    """POST: l'usuari autenticat s'uneix a la reforma (bloquejats i menors no)."""

    def get_permissions(self):
        return _permissions(self.request, write_methods=('POST',))

    @swagger_auto_schema(
        tags=TAGS, operation_description="Afegeix l'usuari autenticat com a participant (el creador no pot; un "
                                         "expulsat no pot tornar-hi).",
        manual_parameters=[_id_param()],
        responses={200: openapi.Response('Reforma amb el nou participant', RenovationSerializer,
                                         examples={'application/json': EXAMPLE_RENOVATION_WITH_PARTICIPANTS}),
                   400: ERROR_400_CREATOR_CANNOT_JOIN, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_EXPELLED,
                   404: ERROR_404_RENOVATION_NOT_FOUND, 409: ERROR_400_ALREADY_PARTICIPANT,
                   500: ERROR_500_INTERNAL_ERROR})
    def post(self, request, id):
        try:
            renovation = services.add_participant(id, request.user_uid)
        except services.RenovationNotFound:
            return Response({'error': MSG_RENOVATION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        except services.CreatorCannotJoin:
            return Response({'error': MSG_CREATOR_CANNOT_JOIN}, status=status.HTTP_400_BAD_REQUEST)
        except services.UserExpelled:
            return Response({'error': MSG_EXPELLED}, status=status.HTTP_403_FORBIDDEN)
        except services.AlreadyParticipant:
            return Response({'error': MSG_ALREADY_PARTICIPANT}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return server_error(ERR_JOIN, exc, logger=logger)
        return _json(renovation)


class RenovationParticipantDetailAPIView(APIView):
    """DELETE: surt de la reforma (ell mateix) o l'expulsa el creador."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=TAGS, operation_description="Treu un participant: ell mateix (pot tornar) o el creador (l'expulsa; no "
                                         "podrà tornar).",
        manual_parameters=[_id_param(), openapi.Parameter('uid', openapi.IN_PATH, description='UID del participant',
                                                          type=openapi.TYPE_STRING, required=True)],
        responses={200: openapi.Response('Reforma sense el participant', RenovationSerializer,
                                         examples={'application/json': EXAMPLE_RENOVATION_PARTICIPANT_REMOVED}),
                   401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_NOT_CREATOR,
                   404: ERROR_404_RENOVATION_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, id, uid):
        try:
            renovation = services.remove_participant(id, uid, request.user_uid)
        except services.RenovationNotFound:
            return Response({'error': MSG_RENOVATION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        except services.NotAllowed:
            return Response({'error': MSG_NOT_ALLOWED}, status=status.HTTP_403_FORBIDDEN)
        except services.NotAParticipant:
            return Response({'error': MSG_NOT_PARTICIPANT}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return server_error(ERR_LEAVE, exc, logger=logger)
        return _json(renovation)


# ========== /refuges/{id}/renovations/ ==========

class RefugeRenovationsAPIView(APIView):
    """GET: reformes d'un refugi (totes; amb `?active_only=true` només les vigents)."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=TAGS,
        operation_description="Obté les reformes d'un refugi ordenades per data d'inici. `active_only` "
                              "(`true`/`1`) només retorna les vigents; per defecte, totes.",
        manual_parameters=[
            openapi.Parameter('id', openapi.IN_PATH, description='ID del refugi (UUID)', type=openapi.TYPE_STRING,
                              required=True),
            openapi.Parameter('active_only', openapi.IN_QUERY, description='Només les reformes vigents',
                              type=openapi.TYPE_BOOLEAN, required=False)],
        responses={200: openapi.Response('Llista de reformes', RenovationSerializer(many=True),
                                         examples={'application/json': EXAMPLE_RENOVATIONS_LIST}),
                   401: ERROR_401_UNAUTHORIZED, 404: openapi.Response('Refugi no trobat'),
                   500: ERROR_500_INTERNAL_ERROR})
    def get(self, request, id):
        active_only = _truthy(request.query_params.get('active_only', 'false'))
        try:
            renovations = selectors.list_refuge_renovations(id, active_only=active_only)
        except Exception as exc:
            return server_error(ERR_REFUGE_LIST, exc, logger=logger)
        if renovations is None:
            return Response({'error': MSG_REFUGE_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        return Response(RenovationSerializer(renovations, many=True).data)
