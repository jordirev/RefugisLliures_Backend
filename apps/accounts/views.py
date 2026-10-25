"""
Vistes de `accounts`: usuaris i les seves llistes de preferits/visitats (PostgreSQL).

Les vistes només validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures) i serialitzen.
El context de RLS (`app.uid`, `app.is_admin`) el fixa el hook de `api/rls_hook.py` abans dels permisos.
Tot endpoint autenticat llevat de `POST /users/` exigeix `HasProfile` (403 `profile_required`).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasProfile, IsSameUser, coded_error
from api.services import r2_media_service
from api.utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_403_UNDERAGE,
    ERROR_404_AVATAR_NOT_FOUND,
    ERROR_404_USER_NOT_FOUND,
    ERROR_404_USER_OR_REFUGI,
    ERROR_409_USER_EXISTS,
    ERROR_500_INTERNAL_ERROR,
    SUCCESS_204_NO_CONTENT,
)
from api.utils.swagger_examples import (
    EXAMPLE_AGE_CONFIRMATION_REQUEST,
    EXAMPLE_USER_BASIC,
    EXAMPLE_USER_CREATE_REQUEST,
    EXAMPLE_USER_UPDATE_REQUEST,
    EXAMPLE_USER_UPDATED,
    EXAMPLE_USER_WITH_DATA,
)
from apps.core.errors import server_error

from . import selectors, services
from .serializers import (
    AgeConfirmationSerializer,
    PublicUserSerializer,
    RefugeIdSerializer,
    UserCreateSerializer,
    UserRefugeInfoSerializer,
    UserRefugeListSerializer,
    UserSerializer,
    UserUpdateSerializer,
    own_profile_to_dict,
    public_profile_to_dict,
    refuge_summary_to_dict,
)

logger = logging.getLogger(__name__)

UNDERAGE_MESSAGE = "Cal tenir 16 anys o més per utilitzar l'aplicació"
NOT_AUTHENTICATED = {'error': 'No autenticat', 'message': "UID no trobat al token d'autenticació"}

ERR_PROFILE_DB = "Error de base de dades en obtenir l'usuari"
ERR_COUNTS = "Error en obtenir els comptadors de l'usuari a Firestore"
ERR_PRESIGN = "Error en generar la URL de l'avatar"
ERR_CREATE = "Error de base de dades en crear l'usuari"
ERR_UPDATE = "Error de base de dades en actualitzar l'usuari"
ERR_DELETE_USER = "Error en esborrar l'usuari"
ERR_AVATAR_R2 = "Error en esborrar l'avatar a R2"
ERR_AVATAR_DB = "Error de base de dades en esborrar l'avatar"
ERR_AGE = "Error de base de dades en confirmar l'edat"
ERR_LIST_DB = 'Error de base de dades en obtenir els refugis de la llista'
ERR_LIST_WRITE = 'Error de base de dades en modificar la llista de refugis'
ERR_LIST_PRESIGN = 'Error en generar la URL de la imatge'


def _invalid(serializer):
    return Response({'error': 'Dades invàlides', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


def _avatar_presigner():
    service = r2_media_service.get_user_avatar_service()
    return lambda key: service.generate_presigned_url(key, 3600)


def _refuge_presigner():
    service = r2_media_service.get_refugi_media_service()
    return lambda key: service.generate_presigned_url(key, 3600)


def _own_profile_response(user, uid, http_status=status.HTTP_200_OK):
    """Perfil propi serialitzat (comptadors de Firestore, D19, i URL prefirmada de l'avatar)."""
    try:
        counts = selectors.get_legacy_counts(uid)
    except Exception as exc:
        return server_error(ERR_COUNTS, exc, logger=logger)
    try:
        return Response(own_profile_to_dict(user, counts, _avatar_presigner()), status=http_status)
    except Exception as exc:
        return server_error(ERR_PRESIGN, exc, logger=logger)


def _fetch_own_profile(uid):
    """`(user, None)` o `(None, Response)` amb l'error."""
    try:
        user = selectors.get_own_profile(uid)
    except Exception as exc:
        return None, server_error(ERR_PROFILE_DB, exc, logger=logger)
    if user is None:
        return None, Response({'error': f'Usuari amb UID {uid} no trobat'}, status=status.HTTP_404_NOT_FOUND)
    return user, None


# ========== /users/ ==========

class UsersCollectionAPIView(APIView):
    """POST /api/users/: crea l'usuari amb l'UID del token (l'únic endpoint autenticat sense `HasProfile`)."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Crea l'usuari amb l'UID del token de Firebase (i el seu perfil públic, en una transacció). "
            "\nL'idioma per defecte és `en`; es valida contra el catàleg d'idiomes. "
            "\nRequereix autenticació amb token JWT de Firebase."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description="Nom d'usuari"),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='Idioma (ca, es, en, fr), per defecte en'),
                'birth_date': openapi.Schema(
                    type=openapi.TYPE_STRING, format='date',
                    description="Data de naixement YYYY-MM-DD (opcional). Si es dona i l'usuari té < 16 anys → 403 "
                                "underage. No es desa: només age_confirmed_at i age_threshold."),
            },
            example=EXAMPLE_USER_CREATE_REQUEST),
        responses={
            201: openapi.Response(description='Usuari creat correctament', schema=UserSerializer,
                                  examples={'application/json': EXAMPLE_USER_BASIC}),
            400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_UNDERAGE,
            409: ERROR_409_USER_EXISTS, 500: ERROR_500_INTERNAL_ERROR,
        })
    def post(self, request):
        uid = getattr(request, 'user_uid', None)
        if not uid:
            return Response(NOT_AUTHENTICATED, status=status.HTTP_401_UNAUTHORIZED)
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        data = serializer.validated_data
        try:
            user = services.create_user(uid=uid, username=data.get('username', ''), language=data.get('language'),
                                        birth_date=data.get('birth_date'))
        except services.UserUnderage:
            return Response(coded_error('underage', UNDERAGE_MESSAGE), status=status.HTTP_403_FORBIDDEN)
        except services.UserAlreadyExists as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        # Usuari nou: sense llistes, fotos ni activitat a Firestore (no cal consultar-lo).
        zero = {'num_shared_experiences': 0, 'num_renovated_refuges': 0}
        try:
            return Response(own_profile_to_dict(user, zero, _avatar_presigner()), status=status.HTTP_201_CREATED)
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)


# ========== /users/{uid}/ ==========

class UserDetailAPIView(APIView):
    """GET (perfil propi complet o públic d'un altre), PATCH i DELETE (només el mateix usuari) de `/api/users/{uid}/`."""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), HasProfile()]
        return [IsAuthenticated(), HasProfile(), IsSameUser()]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Obté un usuari per UID. El **propi** perfil és complet; el d'un altre usuari (també per a un admin) "
            "només porta `uid`, `username` i `avatar_metadata`. \nRequereix autenticació."),
        responses={
            200: openapi.Response(description='Usuari trobat (perfil propi complet)', schema=UserSerializer,
                                  examples={'application/json': EXAMPLE_USER_WITH_DATA}),
            401: ERROR_401_UNAUTHORIZED, 404: ERROR_404_USER_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR,
        })
    def get(self, request, uid):
        if uid == request.user_uid:
            user, error = _fetch_own_profile(uid)
            return error or _own_profile_response(user, uid)
        try:
            profile = selectors.get_public_profile(uid)
        except Exception as exc:
            return server_error(ERR_PROFILE_DB, exc, logger=logger)
        if profile is None:
            return Response({'error': f'Usuari amb UID {uid} no trobat'}, status=status.HTTP_404_NOT_FOUND)
        try:
            return Response(public_profile_to_dict(profile, _avatar_presigner()))
        except Exception as exc:
            return server_error(ERR_PRESIGN, exc, logger=logger)

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Actualitza el nom d'usuari i/o l'idioma. Almenys un camp. "
                               "\nRequereix autenticació i ser el mateix usuari."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'username': openapi.Schema(type=openapi.TYPE_STRING, description="Nom d'usuari"),
                        'language': openapi.Schema(type=openapi.TYPE_STRING, description='Idioma preferit')},
            example=EXAMPLE_USER_UPDATE_REQUEST),
        responses={
            200: openapi.Response(description='Usuari actualitzat', schema=UserSerializer,
                                  examples={'application/json': EXAMPLE_USER_UPDATED}),
            400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR,
        })
    def patch(self, request, uid):
        serializer = UserUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            services.update_user(uid, **serializer.validated_data)
        except services.UserNotFound:
            return Response({'error': f'Usuari amb UID {uid} no trobat'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return server_error(ERR_UPDATE, exc, logger=logger)
        user, error = _fetch_own_profile(uid)
        return error or _own_profile_response(user, uid)

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Elimina l'usuari: passos de Firestore (dominis encara no migrats), fitxers d'R2 (avatar i fotos) i, al "
            "final, la fila de PostgreSQL (cascada: perfil, avatar, preferits, visitats). Si un pas falla, 500 i "
            "l'usuari es conserva (reintentable). \nRequereix autenticació i ser el mateix usuari."),
        responses={204: SUCCESS_204_NO_CONTENT, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_USER_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, uid):
        try:
            services.delete_user(uid)
        except services.UserNotFound:
            return Response({'error': f'Usuari amb UID {uid} no trobat'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:                    # inclou `UserDeletionError`: el detall només va al log
            return server_error(ERR_DELETE_USER, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== /users/{uid}/avatar/ ==========

class UserAvatarAPIView(APIView):
    """DELETE /api/users/{uid}/avatar/ (l'avatar es puja amb `POST /api/media/upload-intents/` + confirm)."""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Elimina l'avatar (fila i fitxers d'R2). \nRequereix autenticació i ser el mateix usuari.",
        manual_parameters=[openapi.Parameter('uid', openapi.IN_PATH, description="UID de l'usuari",
                                             type=openapi.TYPE_STRING, required=True)],
        responses={204: SUCCESS_204_NO_CONTENT, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_AVATAR_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, uid):
        try:
            services.delete_avatar(uid)
        except services.AvatarNotFound as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except services.AvatarStorageError as exc:
            return server_error(ERR_AVATAR_R2, exc, logger=logger)
        except Exception as exc:
            return server_error(ERR_AVATAR_DB, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ========== /users/{uid}/age-confirmation/ ==========

class UserAgeConfirmationAPIView(APIView):
    """PATCH /api/users/{uid}/age-confirmation/: només es desa `age_confirmed_at` i `age_threshold`."""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Confirma l'edat a partir de la data de naixement (YYYY-MM-DD). Amb < 16 anys retorna 403 "
            "{error: 'underage'}. La data NO es desa (minimització): només age_confirmed_at i age_threshold=16."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT, required=['birth_date'],
            properties={'birth_date': openapi.Schema(type=openapi.TYPE_STRING, format='date')},
            example=EXAMPLE_AGE_CONFIRMATION_REQUEST),
        responses={
            200: openapi.Response(description='Edat confirmada', schema=UserSerializer,
                                  examples={'application/json': EXAMPLE_USER_WITH_DATA}),
            400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_UNDERAGE,
            404: ERROR_404_USER_NOT_FOUND, 500: ERROR_500_INTERNAL_ERROR,
        })
    def patch(self, request, uid):
        serializer = AgeConfirmationSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            services.confirm_age(uid, serializer.validated_data['birth_date'])
        except services.UserUnderage:
            return Response(coded_error('underage', UNDERAGE_MESSAGE), status=status.HTTP_403_FORBIDDEN)
        except services.UserNotFound:
            return Response({'error': f'Usuari amb UID {uid} no trobat'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return server_error(ERR_AGE, exc, logger=logger)
        user, error = _fetch_own_profile(uid)
        return error or _own_profile_response(user, uid)


# ========== /users/{uid}/favorite-refuges/ i /users/{uid}/visited-refuges/ ==========

class _RefugeListAPIView(APIView):
    """GET (llista) i POST (afegeix, idempotent) d'una llista de refugis de l'usuari; només el propi usuari."""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]
    kind = None            # 'favourite' | 'visited'
    add = None             # nom de la funció de `services`

    def _list(self, request, uid):
        try:
            rows = selectors.list_refuges(self.kind, uid)
        except Exception as exc:
            return server_error(ERR_LIST_DB, exc, logger=logger)
        try:
            presign = _refuge_presigner()
            results = [refuge_summary_to_dict(r, m, presign) for r, m in rows]
        except Exception as exc:
            return server_error(ERR_LIST_PRESIGN, exc, logger=logger)
        return Response({'count': len(results), 'results': results})

    def _add(self, request, uid):
        serializer = RefugeIdSerializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        try:
            getattr(services, self.add)(uid, serializer.validated_data['refuge_id'])
            found = selectors.get_refuge_with_first_media(serializer.validated_data['refuge_id'])
        except services.RefugeNotFound as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return server_error(ERR_LIST_WRITE, exc, logger=logger)
        try:
            return Response(refuge_summary_to_dict(found[0], found[1], _refuge_presigner()))
        except Exception as exc:
            return server_error(ERR_LIST_PRESIGN, exc, logger=logger)


class UserFavouriteRefugesAPIView(_RefugeListAPIView):
    kind, add = 'favourite', 'add_favourite'

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Refugis preferits de l'usuari (en ordre d'afegit), amb la primera foto visible. "
                               "\nRequereix autenticació i ser el mateix usuari."),
        responses={200: openapi.Response(description='Preferits', schema=UserRefugeListSerializer),
                   401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN, 500: ERROR_500_INTERNAL_ERROR})
    def get(self, request, uid):
        return self._list(request, uid)

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Afegeix un refugi als preferits (idempotent: `ON CONFLICT DO NOTHING`) i en retorna "
                               "el resum. \nRequereix autenticació i ser el mateix usuari."),
        request_body=RefugeIdSerializer,
        responses={200: openapi.Response(description='Refugi afegit', schema=UserRefugeInfoSerializer),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_USER_OR_REFUGI, 500: ERROR_500_INTERNAL_ERROR})
    def post(self, request, uid):
        return self._add(request, uid)


class UserVisitedRefugesAPIView(_RefugeListAPIView):
    kind, add = 'visited', 'add_visited'

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Refugis visitats de l'usuari (en ordre d'afegit), amb la primera foto visible. "
                               "\nRequereix autenticació i ser el mateix usuari."),
        responses={200: openapi.Response(description='Visitats', schema=UserRefugeListSerializer),
                   401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN, 500: ERROR_500_INTERNAL_ERROR})
    def get(self, request, uid):
        return self._list(request, uid)

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Afegeix un refugi als visitats (idempotent) i en retorna el resum. "
                               "\nRequereix autenticació i ser el mateix usuari."),
        request_body=RefugeIdSerializer,
        responses={200: openapi.Response(description='Refugi afegit', schema=UserRefugeInfoSerializer),
                   400: ERROR_400_INVALID_DATA, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_USER_OR_REFUGI, 500: ERROR_500_INTERNAL_ERROR})
    def post(self, request, uid):
        return self._add(request, uid)


class _RefugeListDetailAPIView(APIView):
    """DELETE d'un refugi de la llista: 204 idempotent; refugi inexistent o ID invàlid, 404 (D23)."""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]
    remove = None

    def delete(self, request, uid, refuge_id):
        try:
            getattr(services, self.remove)(uid, refuge_id)
        except services.RefugeNotFound as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return server_error(ERR_LIST_WRITE, exc, logger=logger)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserFavouriteRefugesDetailAPIView(_RefugeListDetailAPIView):
    remove = 'remove_favourite'

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Treu un refugi dels preferits (204 també si no hi era). "
                               "\nRequereix autenticació i ser el mateix usuari."),
        responses={204: SUCCESS_204_NO_CONTENT, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_USER_OR_REFUGI, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, uid, refuge_id):
        return super().delete(request, uid, refuge_id)


class UserVisitedRefugesDetailAPIView(_RefugeListDetailAPIView):
    remove = 'remove_visited'

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=("Treu un refugi dels visitats (204 també si no hi era). "
                               "\nRequereix autenticació i ser el mateix usuari."),
        responses={204: SUCCESS_204_NO_CONTENT, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_USER_OR_REFUGI, 500: ERROR_500_INTERNAL_ERROR})
    def delete(self, request, uid, refuge_id):
        return super().delete(request, uid, refuge_id)
