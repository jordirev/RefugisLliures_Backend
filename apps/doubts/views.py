"""
Vistes de `doubts`: dubtes d'un refugi i les seves respostes (arbre pla per `parent_answer_id`).

Les vistes només validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures) i serialitzen.
El context de RLS el fixa el hook de `api/rls_hook.py`. Dubtes i respostes exigeixen `IsAuthenticated, HasProfile`
i, per a les escriptures de contingut (POST), també `IsNotBlocked` i `IsAgeConfirmed` (decisió del PO, 26/10). GET i
DELETE del que és propi no els exigeixen: un usuari bloquejat pot llegir i esborrar el seu contingut (RGPD). La propietat la comprova el service (403 `not_owner`).
Ordre de comprovacions: permisos -> validació del cos (400) -> existència (404) -> propietat (403).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked, coded_error, is_firebase_admin
from api.utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_404_ANSWER_NOT_FOUND,
    ERROR_404_DOUBT_NOT_FOUND,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR,
)
from api.utils.swagger_examples import EXAMPLE_ANSWER_DETAIL, EXAMPLE_DOUBT_DETAIL, EXAMPLE_DOUBT_LIST
from apps.core.errors import server_error
from apps.refuges import selectors as refuge_selectors

from . import selectors, services
from .serializers import AnswerSerializer, CreateAnswerSerializer, CreateDoubtSerializer, DoubtSerializer

logger = logging.getLogger(__name__)

PERMISSIONS = [IsAuthenticated, HasProfile]
WRITE_PERMISSIONS = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]


class _ContentPermissionsMixin:
    """POST (escriptura de contingut): bloqueig i edat; la resta de mètodes només perfil."""

    def get_permissions(self):
        classes = WRITE_PERMISSIONS if self.request.method == 'POST' else PERMISSIONS
        return [permission() for permission in classes]

ERR_LIST = 'Error de base de dades en obtenir els dubtes'
ERR_CREATE_DOUBT = 'Error de base de dades en crear el dubte'
ERR_DELETE_DOUBT = 'Error de base de dades en esborrar el dubte'
ERR_CREATE_ANSWER = 'Error de base de dades en crear la resposta'
ERR_DELETE_ANSWER = 'Error de base de dades en esborrar la resposta'

NOT_OWNER_DOUBT = "No ets el creador d'aquest dubte"
NOT_OWNER_ANSWER = "No ets el creador d'aquesta resposta"


def _not_found(message):
    return Response({'error': message}, status=status.HTTP_404_NOT_FOUND)


def _invalid(serializer):
    return Response({'error': 'Dades invàlides', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


def _not_owner(message):
    return Response(coded_error('not_owner', message), status=status.HTTP_403_FORBIDDEN)


def _actor(request):
    return getattr(request, 'user_uid', None), is_firebase_admin(request)


def _path_param(name, description):
    return openapi.Parameter(name, openapi.IN_PATH, description=description, type=openapi.TYPE_STRING, required=True)


class DoubtListAPIView(_ContentPermissionsMixin, APIView):
    """GET /api/doubts/?refuge_id={id} i POST /api/doubts/."""

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Obté els dubtes d'un refugi amb totes les seves respostes. Dubtes per data de creació descendent; "
            "respostes (llista plana, l'arbre es munta amb `parent_answer_id`) per data ascendent. Requereix autenticació."
        ),
        manual_parameters=[openapi.Parameter('refuge_id', openapi.IN_QUERY, description='ID del refugi (UUID)',
                                             type=openapi.TYPE_STRING, required=True)],
        responses={200: openapi.Response(description='Llista de dubtes amb les seves respostes',
                                         examples={'application/json': EXAMPLE_DOUBT_LIST}),
                   401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_REFUGI_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR},
    )
    def get(self, request):
        refuge_id = request.query_params.get('refuge_id')
        if not refuge_id:
            return Response(
                {'error': 'El refuge_id es requerit. El path per a cridar al endpoint és /api/doubts/?refuge_id=refuge_id'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            if not refuge_selectors.refuge_exists(refuge_id):
                return _not_found('Refuge not found')
            doubts = selectors.list_doubts(refuge_id)
        except Exception as exc:
            return server_error(ERR_LIST, exc, logger=logger)
        return Response(DoubtSerializer(doubts, many=True).data)

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=("Crea un dubte. El `refuge_id` va al cos i el creador és l'usuari del token. "
                               "Requereix autenticació."),
        request_body=CreateDoubtSerializer,
        responses={201: openapi.Response(description='Dubte creat', examples={'application/json': EXAMPLE_DOUBT_DETAIL}),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_REFUGI_NOT_FOUND,
                   500: ERROR_500_INTERNAL_ERROR},
    )
    def post(self, request):
        serializer = CreateDoubtSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        uid, _ = _actor(request)
        try:
            doubt = services.create_doubt(refuge_id=serializer.validated_data['refuge_id'], creator_uid=uid,
                                          message=serializer.validated_data['message'])
        except services.RefugeNotFound as exc:
            return _not_found(str(exc))
        except Exception as exc:
            return server_error(ERR_CREATE_DOUBT, exc, logger=logger)
        return Response(DoubtSerializer(doubt).data, status=status.HTTP_201_CREATED)


class DoubtDetailAPIView(_ContentPermissionsMixin, APIView):
    """DELETE /api/doubts/{doubt_id}/: el creador o un admin (esborra també les respostes)."""

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=("Elimina un dubte i totes les seves respostes (cascada de la BD). Només el creador "
                               "del dubte o un administrador. Requereix autenticació."),
        manual_parameters=[_path_param('doubt_id', 'ID del dubte')],
        responses={204: openapi.Response(description='Dubte eliminat'), 401: ERROR_401_UNAUTHORIZED,
                   403: ERROR_403_FORBIDDEN, 404: ERROR_404_DOUBT_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR},
    )
    def delete(self, request, doubt_id):
        uid, admin = _actor(request)
        try:
            services.delete_doubt(doubt_id=doubt_id, actor_uid=uid, is_admin=admin)
        except services.DoubtNotFound as exc:
            return _not_found(str(exc))
        except services.NotOwner:
            return _not_owner(NOT_OWNER_DOUBT)
        except Exception as exc:
            return server_error(ERR_DELETE_DOUBT, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnswerListAPIView(_ContentPermissionsMixin, APIView):
    """POST /api/doubts/{doubt_id}/answers/: resposta directa al dubte."""

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description="Crea una resposta a un dubte. El creador és l'usuari del token. Requereix autenticació.",
        manual_parameters=[_path_param('doubt_id', 'ID del dubte')],
        request_body=CreateAnswerSerializer,
        responses={201: openapi.Response(description='Resposta creada',
                                         examples={'application/json': EXAMPLE_ANSWER_DETAIL}),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_DOUBT_NOT_FOUND,
                   500: ERROR_500_INTERNAL_ERROR},
    )
    def post(self, request, doubt_id):
        serializer = CreateAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        uid, _ = _actor(request)
        try:
            answer = services.create_answer(doubt_id=doubt_id, creator_uid=uid,
                                            message=serializer.validated_data['message'])
        except services.DoubtNotFound as exc:
            return _not_found(str(exc))
        except Exception as exc:
            return server_error(ERR_CREATE_ANSWER, exc, logger=logger)
        return Response(AnswerSerializer(answer).data, status=status.HTTP_201_CREATED)


class AnswerReplyAPIView(_ContentPermissionsMixin, APIView):
    """POST /api/doubts/{doubt_id}/answers/{answer_id}/ (rèplica) i DELETE (resposta i subarbre)."""

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=("Crea una rèplica a una resposta del dubte (`parent_answer_id` = `answer_id` de la URL; "
                               "ha de ser del mateix dubte). Requereix autenticació."),
        manual_parameters=[_path_param('doubt_id', 'ID del dubte'), _path_param('answer_id', 'ID de la resposta pare')],
        request_body=CreateAnswerSerializer,
        responses={201: openapi.Response(description='Resposta creada',
                                         examples={'application/json': EXAMPLE_ANSWER_DETAIL}),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_DOUBT_NOT_FOUND,
                   500: ERROR_500_INTERNAL_ERROR},
    )
    def post(self, request, doubt_id, answer_id):
        serializer = CreateAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        uid, _ = _actor(request)
        try:
            answer = services.create_answer(doubt_id=doubt_id, creator_uid=uid,
                                            message=serializer.validated_data['message'], parent_answer_id=answer_id)
        except (services.DoubtNotFound, services.AnswerNotFound) as exc:
            return _not_found(str(exc))
        except Exception as exc:
            return server_error(ERR_CREATE_ANSWER, exc, logger=logger)
        return Response(AnswerSerializer(answer).data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=("Elimina una resposta i tot el seu subarbre de rèpliques (cascada de la BD). Només el "
                               "creador de la resposta o un administrador. Requereix autenticació."),
        manual_parameters=[_path_param('doubt_id', 'ID del dubte'), _path_param('answer_id', 'ID de la resposta')],
        responses={204: openapi.Response(description='Resposta eliminada'), 401: ERROR_401_UNAUTHORIZED,
                   403: ERROR_403_FORBIDDEN, 404: ERROR_404_ANSWER_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR},
    )
    def delete(self, request, doubt_id, answer_id):
        uid, admin = _actor(request)
        try:
            services.delete_answer(doubt_id=doubt_id, answer_id=answer_id, actor_uid=uid, is_admin=admin)
        except (services.DoubtNotFound, services.AnswerNotFound) as exc:
            return _not_found(str(exc))
        except services.NotOwner:
            return _not_owner(NOT_OWNER_ANSWER)
        except Exception as exc:
            return server_error(ERR_DELETE_ANSWER, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)
