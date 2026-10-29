"""
Vistes d'`experiences`: llista, creació, edició i esborrat d'experiències d'un refugi.

Les vistes només validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures) i serialitzen.
El context de RLS el fixa el hook de `apps/core/rls_hook.py`. Totes exigeixen `IsAuthenticated, HasProfile`; les escriptures de
contingut (POST i PATCH) hi afegeixen `IsNotBlocked` i `IsAgeConfirmed` (decisió del PO, 26/10). GET i DELETE del que és
propi no els exigeixen: un usuari bloquejat pot llegir i esborrar les seves experiències (RGPD; D38). La propietat la
comprova el service (403 `not_owner`).
Ordre de comprovacions: permisos -> validació del cos (400) -> existència (404) -> propietat (403).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth.permissions import HasProfile, IsAgeConfirmed, IsNotBlocked, coded_error, is_firebase_admin
from apps.uploads.media import r2_media_service
from apps.core.swagger.error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_500_INTERNAL_ERROR,
)
from apps.core.errors import server_error
from apps.refuges import selectors as refuge_selectors

from . import selectors, services
from .serializers import (
    ExperienceCreateSerializer,
    ExperienceListResponseSerializer,
    ExperienceUpdateSerializer,
    ExperienceWrapperSerializer,
    experience_to_dict,
)

logger = logging.getLogger(__name__)

PRESIGN_SECONDS = 3600          # URLs prefirmades vàlides 1 hora

PERMISSIONS = [IsAuthenticated, HasProfile]
WRITE_PERMISSIONS = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]

ERR_LIST = "Error de base de dades en obtenir les experiències"
ERR_PRESIGN = 'Error en generar la URL de la imatge'
ERR_CREATE = "Error de base de dades en crear l'experiència"
ERR_UPDATE = "Error de base de dades en actualitzar l'experiència"
ERR_DELETE = "Error de base de dades en esborrar l'experiència"
ERR_R2_DELETE = "Error en esborrar els fitxers de l'experiència a R2"

NOT_OWNER_MESSAGE = "No ets el creador d'aquesta experiència"
DELETED_MESSAGE = 'Experiència eliminada correctament'


def _presigner():
    service = r2_media_service.get_refugi_media_service()
    return lambda key: service.generate_presigned_url(key, PRESIGN_SECONDS)


def _actor(request):
    return getattr(request, 'user_uid', None), is_firebase_admin(request)


def _not_found(message):
    return Response({'error': message}, status=status.HTTP_404_NOT_FOUND)


def _invalid(serializer):
    return Response({'error': 'Dades invàlides', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


def _not_owner():
    return Response(coded_error('not_owner', NOT_OWNER_MESSAGE), status=status.HTTP_403_FORBIDDEN)


class _ContentPermissionsMixin:
    """POST/PATCH (escriptura de contingut): bloqueig i edat; la resta de mètodes només perfil."""

    parser_classes = [JSONParser]

    def get_permissions(self):
        classes = WRITE_PERMISSIONS if self.request.method in ('POST', 'PATCH') else PERMISSIONS
        return [permission() for permission in classes]


def _path_param(name, description):
    return openapi.Parameter(name, openapi.IN_PATH, description=description, type=openapi.TYPE_STRING, required=True)


class ExperienceListAPIView(_ContentPermissionsMixin, APIView):
    """GET /api/experiences/?refuge_id={id} i POST /api/experiences/."""

    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=("Obté les experiències d'un refugi per data de modificació descendent, amb els seus "
                               "mitjans (URLs prefirmades). Requereix autenticació."),
        manual_parameters=[openapi.Parameter('refuge_id', openapi.IN_QUERY, description='ID del refugi (UUID)',
                                             type=openapi.TYPE_STRING, required=True)],
        responses={200: openapi.Response(description="Llista d'experiències", schema=ExperienceListResponseSerializer),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED,
                   404: openapi.Response(description='Refugi no trobat'), 500: ERROR_500_INTERNAL_ERROR},
    )
    def get(self, request):
        refuge_id = request.query_params.get('refuge_id')
        if not refuge_id:
            return Response({'error': 'El refuge_id és requerit. El path és /api/experiences/?refuge_id=refuge_id'},
                            status=status.HTTP_400_BAD_REQUEST)
        uid, admin = _actor(request)
        try:
            if not refuge_selectors.refuge_exists(refuge_id):
                return _not_found('Refuge not found')
            experiences = selectors.list_experiences(refuge_id, uid, admin)
        except Exception as exc:
            return server_error(ERR_LIST, exc, logger=logger)
        try:
            presign = _presigner()
            data = [experience_to_dict(e, e.media_list, presign) for e in experiences]
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)
        return Response({'experiences': data})

    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=("Crea una experiència (`refuge_id`, `comment`, `condition` 0-3) i la fa comptar a la "
                               "mitjana de condició del refugi. Les fotos es pugen després amb "
                               "POST /api/media/upload-intents/ (target=experience) + confirm. Requereix autenticació."),
        request_body=ExperienceCreateSerializer,
        responses={201: openapi.Response(description='Experiència creada', schema=ExperienceWrapperSerializer),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED,
                   404: openapi.Response(description='Refugi no trobat'), 500: ERROR_500_INTERNAL_ERROR},
    )
    def post(self, request):
        serializer = ExperienceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        uid, _ = _actor(request)
        data = serializer.validated_data
        try:
            experience = services.create_experience(refuge_id=data['refuge_id'], creator_uid=uid,
                                                    comment=data['comment'], condition=data['condition'])
        except services.RefugeNotFound as exc:
            return _not_found(str(exc))
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return Response({'experience': experience_to_dict(experience, [], None)}, status=status.HTTP_201_CREATED)


class ExperienceDetailAPIView(_ContentPermissionsMixin, APIView):
    """PATCH i DELETE /api/experiences/{experience_id}/: el creador o un admin."""

    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=("Edita el comentari i/o la condició d'una experiència. Només el creador o un admin. "
                               "Per treure fotos: DELETE /api/refuges/{id}/media/{key}/. Requereix autenticació."),
        manual_parameters=[_path_param('experience_id', "ID de l'experiència")],
        request_body=ExperienceUpdateSerializer,
        responses={200: openapi.Response(description='Experiència actualitzada', schema=ExperienceWrapperSerializer),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: openapi.Response(description='Experiència no trobada'), 500: ERROR_500_INTERNAL_ERROR},
    )
    def patch(self, request, experience_id):
        serializer = ExperienceUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        uid, admin = _actor(request)
        try:
            experience = services.update_experience(experience_id=experience_id, actor_uid=uid, is_admin=admin,
                                                    **serializer.validated_data)
        except services.ExperienceNotFound as exc:
            return _not_found(str(exc))
        except services.NotOwner:
            return _not_owner()
        except Exception as exc:
            return server_error(ERR_UPDATE, exc, logger=logger)
        try:
            media = selectors.get_experience_media(experience.pk, uid, admin)
        except Exception as exc:
            return server_error(ERR_LIST, exc, logger=logger)
        try:
            data = experience_to_dict(experience, media, _presigner())
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)
        return Response({'experience': data})

    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=("Elimina una experiència i els seus mitjans (també a R2). Només el creador o un admin; "
                               "un usuari bloquejat pot esborrar la seva. No toca la mitjana del refugi. "
                               "Requereix autenticació."),
        manual_parameters=[_path_param('experience_id', "ID de l'experiència")],
        responses={200: openapi.Response(description='Experiència eliminada'), 401: ERROR_401_UNAUTHORIZED,
                   403: ERROR_403_FORBIDDEN, 404: openapi.Response(description='Experiència no trobada'),
                   500: ERROR_500_INTERNAL_ERROR},
    )
    def delete(self, request, experience_id):
        uid, admin = _actor(request)
        try:
            services.delete_experience(experience_id=experience_id, actor_uid=uid, is_admin=admin)
        except services.ExperienceNotFound as exc:
            return _not_found(str(exc))
        except services.NotOwner:
            return _not_owner()
        except services.MediaStorageError as exc:
            return server_error(ERR_R2_DELETE, exc, logger=logger)
        except Exception as exc:
            return server_error(ERR_DELETE, exc, logger=logger)
        return Response({'success': True, 'message': DELETED_MESSAGE})
