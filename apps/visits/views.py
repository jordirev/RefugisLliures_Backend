"""
Vistes de `visits` (PostgreSQL): validen l'entrada, criden `selectors`/`services` i mapen les excepcions de domini.

Tots els endpoints són autenticats amb `HasProfile` just després d'`IsAuthenticated`. El UID surt sempre del token.
Errors 500: `server_error(...)` amb un missatge fix per punt (mai `str(e)`).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasProfile, IsSameUser
from apps.core.errors import server_error

from . import services
from .serializers import CreateRefugeVisitSerializer, RefugeVisitListSerializer, UpdateRefugeVisitSerializer

logger = logging.getLogger(__name__)

ERR_LIST_REFUGE = 'Error en obtenir les visites del refugi'
ERR_LIST_USER = "Error en obtenir les visites de l'usuari"
ERR_CREATE = 'Error en registrar la visita'
ERR_UPDATE = 'Error en actualitzar la visita'
ERR_DELETE = 'Error en esborrar el visitant de la visita'

MSG_BAD_DATE = 'Format de data invàlid. Utilitza YYYY-MM-DD'
MSG_PAST = 'La data de la visita ha de ser igual o posterior a avui'
MSG_ALREADY = 'Ja estàs registrat a aquesta visita'
MSG_NOT_REGISTERED = 'No estàs registrat a aquesta visita'

VISIT_SCHEMA = openapi.Schema(type=openapi.TYPE_OBJECT, properties={
    'date': openapi.Schema(type=openapi.TYPE_STRING, example='2026-07-18'),
    'refuge_id': openapi.Schema(type=openapi.TYPE_STRING, example='0190aaaa-0000-7000-8000-000000000001'),
    'total_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=12),
    'is_visitor': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
    'num_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=2),
})
LIST_SCHEMA = openapi.Schema(type=openapi.TYPE_OBJECT, properties={
    'result': openapi.Schema(type=openapi.TYPE_ARRAY, items=VISIT_SCHEMA)})


def _error(message, http_status):
    return Response({'error': message}, status=http_status)


class RefugeVisitsAPIView(APIView):
    """GET: visites actuals i futures d'un refugi."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=['Refuge Visits'],
        operation_description="Visites d'avui en endavant d'un refugi, per data ascendent.",
        responses={200: openapi.Response('Llista de visites', LIST_SCHEMA), 401: 'No autenticat',
                   404: 'Refugi no trobat', 500: 'Error intern del servidor'})
    def get(self, request, refuge_id):
        try:
            visits = services.get_refuge_visits(request.user_uid, refuge_id)
            return Response({'result': RefugeVisitListSerializer(visits, many=True).data})
        except services.RefugeNotFound as exc:
            return _error(str(exc), status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return server_error(ERR_LIST_REFUGE, exc, logger=logger)


class UserVisitsAPIView(APIView):
    """GET: totes les visites de l'usuari."""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Totes les visites de l'usuari, per data descendent.",
        responses={200: openapi.Response('Llista de visites', LIST_SCHEMA), 401: 'No autenticat',
                   403: 'No tens permís per accedir a aquestes dades', 500: 'Error intern del servidor'})
    def get(self, request, uid):
        try:
            visits = services.get_user_visits(request.user_uid)
            return Response({'result': RefugeVisitListSerializer(visits, many=True).data})
        except Exception as exc:
            return server_error(ERR_LIST_USER, exc, logger=logger)


class RefugeVisitDetailAPIView(APIView):
    """POST/PATCH/DELETE d'una visita `(refugi, data)`; la data és `YYYY-MM-DD`."""
    permission_classes = [IsAuthenticated, HasProfile]

    @swagger_auto_schema(
        tags=['Refuge Visits'], request_body=CreateRefugeVisitSerializer,
        operation_description="Crea la visita o hi afegeix l'usuari. La data és AAAA-MM-DD i no pot ser passada.",
        responses={201: openapi.Response('Visita creada', openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            'message': openapi.Schema(type=openapi.TYPE_STRING), 'visit': VISIT_SCHEMA})),
            400: 'Paràmetres invàlids o usuari ja registrat', 401: 'No autenticat', 404: 'Refugi no trobat',
            500: 'Error intern del servidor'})
    def post(self, request, refuge_id, visit_date):
        serializer = CreateRefugeVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(serializer.errors, status.HTTP_400_BAD_REQUEST)
        try:
            visit = services.create_visit(request.user_uid, refuge_id, visit_date,
                                          serializer.validated_data['num_visitors'])
        except services.RefugeNotFound as exc:
            return _error(str(exc), status.HTTP_404_NOT_FOUND)
        except services.InvalidDateFormat:
            return _error(MSG_BAD_DATE, status.HTTP_400_BAD_REQUEST)
        except services.VisitDateInPast:
            return _error(MSG_PAST, status.HTTP_400_BAD_REQUEST)
        except services.AlreadyRegistered:
            return _error(MSG_ALREADY, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return Response({'message': 'Visita creada correctament', 'visit': RefugeVisitListSerializer(visit).data},
                        status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        tags=['Refuge Visits'], request_body=UpdateRefugeVisitSerializer,
        operation_description="Canvia el nombre de visitants de l'usuari. La data és AAAA-MM-DD.",
        responses={200: openapi.Response('Visita actualitzada', openapi.Schema(
            type=openapi.TYPE_OBJECT, properties={'message': openapi.Schema(type=openapi.TYPE_STRING),
                                                  'visit': VISIT_SCHEMA})),
            400: 'Paràmetres invàlids o usuari no registrat', 401: 'No autenticat', 404: 'Visita o refugi no trobat',
            500: 'Error intern del servidor'})
    def patch(self, request, refuge_id, visit_date):
        serializer = UpdateRefugeVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return _error(serializer.errors, status.HTTP_400_BAD_REQUEST)
        try:
            visit = services.update_visit(request.user_uid, refuge_id, visit_date,
                                          serializer.validated_data['num_visitors'])
        except services.VisitNotFound:
            return _error('Visita o refugi no trobat', status.HTTP_404_NOT_FOUND)
        except services.NotRegistered:
            return _error(MSG_NOT_REGISTERED, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return server_error(ERR_UPDATE, exc, logger=logger)
        return Response({'message': 'Visita actualitzada correctament',
                         'visit': RefugeVisitListSerializer(visit).data})

    @swagger_auto_schema(
        tags=['Refuge Visits'],
        operation_description="Treu l'usuari de la visita. La data és AAAA-MM-DD.",
        responses={200: openapi.Response('Visitant eliminat', openapi.Schema(
            type=openapi.TYPE_OBJECT, properties={'message': openapi.Schema(type=openapi.TYPE_STRING)})),
            400: 'Usuari no registrat a la visita', 401: 'No autenticat', 404: 'Visita no trobada',
            500: 'Error intern del servidor'})
    def delete(self, request, refuge_id, visit_date):
        try:
            services.remove_visitor(request.user_uid, refuge_id, visit_date)
        except services.VisitNotFound:
            return _error('Visita no trobada', status.HTTP_404_NOT_FOUND)
        except services.NotRegistered:
            return _error(MSG_NOT_REGISTERED, status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return server_error(ERR_DELETE, exc, logger=logger)
        return Response({'message': 'Visitant eliminat correctament'})
