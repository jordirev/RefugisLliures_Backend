"""
Views per a la gestió d'usuaris amb endpoints REST estàndard
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from urllib3 import request
from ..controllers.user_controller import UserController
from ..controllers.renovation_controller import RenovationController
from ..serializers.user_serializer import (
    MediaMetadataSerializer,
    UserRefugiSerializer,
    UserSerializer, 
    UserCreateSerializer, 
    UserUpdateSerializer,
)
from ..serializers.refugi_lliure_serializer import (
    UserRefugiInfoResponseSerializer,
)
from ..serializers.renovation_serializer import RenovationSerializer
from ..permissions import IsSameUser
from ..utils.swagger_examples import (
    EXAMPLE_USER_BASIC,
    EXAMPLE_USER_WITH_DATA,
    EXAMPLE_USER_UPDATED,
    EXAMPLE_USER_CREATE_REQUEST,
    EXAMPLE_USER_UPDATE_REQUEST,
    EXAMPLE_USER_REFUGI_REQUEST,
    EXAMPLE_USER_REFUGI_VISITED_REQUEST,
    EXAMPLE_USER_REFUGI_INFO_RESPONSE_2,
    EXAMPLE_USER_REFUGI_INFO_RESPONSE_3,
    EXAMPLE_USER_REFUGI_INFO_RESPONSE_1,
    EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_2,
    EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_3,
    EXAMPLE_AVATAR_UPLOAD_RESPONSE,
)
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_404_USER_NOT_FOUND,
    ERROR_404_USER_OR_REFUGI,
    ERROR_409_USER_EXISTS,
    ERROR_500_INTERNAL_ERROR,
    SUCCESS_204_NO_CONTENT,
    ERROR_400_INVALID_FILE_TYPE,
    ERROR_404_AVATAR_NOT_FOUND,
)

# Constants d'error per usar dins del codi (no Swagger)
UID_NOT_FOUND_ERROR = "No autenticat"
UID_NOT_FOUND_MESSAGE = "UID no trobat al token d'autenticació"
INTERNAL_SERVER_ERROR = "Error intern del servidor"


# Configurar logging
logger = logging.getLogger(__name__)

# ========== COLLECTION ENDPOINT: /users/ ==========

class UsersCollectionAPIView(APIView):
    """
    Gestiona col·lecció d'usuaris:
    - POST: Crear nou usuari (requereix autenticació)
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Crea un nou usuari. \nRequereix autenticació amb token JWT de Firebase.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description="Nom d'usuari"),
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description="Adreça de correu electrònic"),
                'avatar': openapi.Schema(type=openapi.TYPE_STRING, format='uri', description="URL de l'avatar de l'usuari"),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description="Idioma preferit (ca, es, en, fr)", default='ca')
            },
            example=EXAMPLE_USER_CREATE_REQUEST
        ),
        responses={
            201: openapi.Response(
                description='Usuari creat correctament',
                schema=UserSerializer,
                examples={
                    'application/json': EXAMPLE_USER_BASIC
                }
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            409: ERROR_409_USER_EXISTS
        }
    )
    def post(self, request):
        """Crear nou usuari amb el UID del token de Firebase"""
        try:
            uid = getattr(request, 'user_uid', None)
            if not uid:
                return Response({
                    'error': UID_NOT_FOUND_ERROR,
                    'message': UID_NOT_FOUND_MESSAGE
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Valida les dades d'entrada
            serializer = UserCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crea l'usuari amb el UID del token
            controller = UserController()
            success, user, error_message = controller.create_user(serializer.validated_data, uid)
            
            if not success:
                status_code = status.HTTP_409_CONFLICT if 'ja existeix' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna l'usuari creat
            user_serializer = UserSerializer(user)
            return Response(user_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error en create_user: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========== ITEM ENDPOINT: /users/{uid}/ ==========

class UserDetailAPIView(APIView):
    """
    Gestiona operacions sobre un usuari específic:
    - GET: Obtenir usuari per UID (requereix autenticació)
    - PATCH: Actualitzar usuari (requereix autenticació + ser el mateix usuari)
    - DELETE: Eliminar usuari (requereix autenticació + ser el mateix usuari)
    """
    
    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - GET: només IsAuthenticated
        - PATCH/DELETE: IsAuthenticated + IsSameUser
        """
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Obté un usuari per UID. \nRequereix autenticació amb token JWT de Firebase.",
        responses={
            200: openapi.Response(
                description='Usuari trobat',
                schema=UserSerializer,
                examples={
                    'application/json': EXAMPLE_USER_WITH_DATA
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_USER_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request, uid):
        """Obtenir usuari per UID"""
        try:
            controller = UserController()
            success, user, error_message = controller.get_user_by_uid(uid)
            
            if not success:
                return Response({
                    'error': error_message
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = UserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en get_user: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Actualitza les dades d'un usuari. \nRequereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description="Nom d'usuari"),
                'email': openapi.Schema(type=openapi.TYPE_STRING, format='email', description="Adreça de correu electrònic"),
                'avatar': openapi.Schema(type=openapi.TYPE_STRING, format='uri', description="URL de l'avatar de l'usuari"),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description="Idioma preferit (ca, es, en, fr)")
            },
            example=EXAMPLE_USER_UPDATE_REQUEST
        ),
        responses={
            200: openapi.Response(
                description='Usuari actualitzat correctament',
                schema=UserSerializer,
                examples={
                    'application/json': EXAMPLE_USER_UPDATED
                }
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def patch(self, request, uid):
        """Actualitzar usuari"""
        try:
            # Valida les dades d'entrada
            serializer = UserUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Actualitza l'usuari
            controller = UserController()
            success, user, error_message = controller.update_user(uid, serializer.validated_data)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna l'usuari actualitzat
            user_serializer = UserSerializer(user)
            return Response(user_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en update_user: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description="Elimina un usuari. \nRequereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        responses={
            204: SUCCESS_204_NO_CONTENT,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def delete(self, request, uid):
        """Eliminar usuari"""
        try:
            controller = UserController()
            success, error_message = controller.delete_user(uid)
            
            if not success:
                return Response({
                    'error': error_message
                }, status=status.HTTP_404_NOT_FOUND)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error en delete_user: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


# ========== ITEM ENDPOINT: /users/{uid}/favorite-refuges/ ==========

class UserFavouriteRefugesAPIView(APIView):
    """
    Gestiona operacions sobre els refugis preferits d'un usuari específic:
    - GET: Obtenir la informació dels refugis preferits de l'usuari (requereix autenticació + ser el mateix usuari)
    - POST: Afegir un refugi als preferits de l'usuari (requereix autenticació + ser el mateix usuari)
    """

    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - GET/POST/DELETE: IsAuthenticated + IsSameUser
        """
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(
        tags=['User Favourite Refuges'],
        operation_description="Obté la informació dels refugis preferits de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        responses={
            200: openapi.Response(
                description='Llista de refugis preferits',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_REFUGI_INFO_RESPONSE_2
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def get(self, request, uid):
        """Obté la informació dels refugis preferits de l'usuari"""
        try:
            controller = UserController()
            success, refugis_info, error_message = controller.get_refugis_preferits_info(uid)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista de refugis amb la seva informació
            data = {'count': len(refugis_info), 'results': refugis_info}
            serializer = UserRefugiInfoResponseSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en get_refugis_preferits: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        tags=['User Favourite Refuges'],
        operation_description="Afegeix un refugi als preferits de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refuge_id'],
            properties={
                'refuge_id': openapi.Schema(type=openapi.TYPE_STRING, description="Identificador únic del refugi")
            },
            example=EXAMPLE_USER_REFUGI_REQUEST
        ),
        responses={
            200: openapi.Response(
                description='Refugi afegit als preferits',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_REFUGI_INFO_RESPONSE_3
                }
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: "Usuari o refugi no trobat"
        }
    )
    def post(self, request, uid):
        """Afegeix un nou refugi als preferits de l'usuari"""
        try:
            # Valida les dades d'entrada
            serializer = UserRefugiSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            controller = UserController()
            refuge_id = serializer.validated_data['refuge_id']
            success, refugis_info, error_message = controller.add_refugi_preferit(uid, refuge_id)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista actualitzada amb la informació dels refugis
            data = {'count': len(refugis_info), 'results': refugis_info}
            response_serializer = UserRefugiInfoResponseSerializer(data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en post_refugis_preferits: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== ITEM ENDPOINT: /users/{uid}/favorite-refuges/{refuge_id}/ ==========

class UserFavouriteRefugesDetailAPIView(APIView):
    """
    Gestiona operacions sobre un refugi preferit específic d'un usuari:
    - DELETE: Eliminar un refugi dels preferits de l'usuari (requereix autenticació + ser el mateix usuari)
    """

    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - DELETE: IsAuthenticated + IsSameUser
        """
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(
        tags=['User Favourite Refuges'],
        operation_description="Elimina un refugi dels preferits de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        responses={
            200: openapi.Response(
                description='Refugi eliminat dels preferits',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_REFUGI_INFO_RESPONSE_1
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def delete(self, request, uid, refuge_id):
        """Elimina un refugi dels preferits de l'usuari"""
        try:
            controller = UserController()
            success, refugis_info, error_message = controller.remove_refugi_preferit(uid, refuge_id)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista actualitzada amb la informació dels refugis
            data = {'count': len(refugis_info), 'results': refugis_info}
            serializer = UserRefugiInfoResponseSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en delete_refugi_preferit: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== ITEM ENDPOINT: /users/{uid}/visited-refuges/ ==========

class UserVisitedRefugesAPIView(APIView):
    """
    Gestiona operacions sobre els refugis visitats d'un usuari específic:
    - GET: Obtenir la informació dels refugis visitats de l'usuari (requereix autenticació + ser el mateix usuari)
    - POST: Afegir un refugi als visitats de l'usuari (requereix autenticació + ser el mateix usuari)
    """

    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - GET/POST: IsAuthenticated + IsSameUser
        """
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(
        tags=['User Visited Refuges'],
        operation_description="Obté la informació dels refugis visitats de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        responses={
            200: openapi.Response(
                description='Llista de refugis visitats',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_2
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def get(self, request, uid):
        """Obté la informació dels refugis visitats de l'usuari"""
        try:
            controller = UserController()
            success, refugis_info, error_message = controller.get_refugis_visitats_info(uid)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista de refugis amb la seva informació
            data = {'count': len(refugis_info), 'results': refugis_info}
            serializer = UserRefugiInfoResponseSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en get_refugis_visitats: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        tags=['User Visited Refuges'],
        operation_description="Afegeix un refugi als visitats de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refuge_id'],
            properties={
                'refuge_id': openapi.Schema(type=openapi.TYPE_STRING, description="Identificador únic del refugi")
            },
            example=EXAMPLE_USER_REFUGI_VISITED_REQUEST
        ),
        responses={
            200: openapi.Response(
                description='Refugi afegit als visitats',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_VISITED_REFUGI_INFO_RESPONSE_3
                }
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_OR_REFUGI
        }
    )
    def post(self, request, uid):
        """Afegeix un nou refugi als visitats de l'usuari"""
        try:
            # Valida les dades d'entrada
            serializer = UserRefugiSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            controller = UserController()
            refuge_id = serializer.validated_data['refuge_id']
            success, refugis_info, error_message = controller.add_refugi_visitat(uid, refuge_id)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista actualitzada amb la informació dels refugis
            data = {'count': len(refugis_info), 'results': refugis_info}
            response_serializer = UserRefugiInfoResponseSerializer(data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en post_refugis_visitats: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== ITEM ENDPOINT: /users/{uid}/visited-refuges/{refuge_id}/ ==========

class UserVisitedRefugesDetailAPIView(APIView):
    """
    Gestiona operacions sobre un refugi visitat específic d'un usuari:
    - DELETE: Eliminar un refugi dels visitats de l'usuari (requereix autenticació + ser el mateix usuari)
    """

    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - DELETE: IsAuthenticated + IsSameUser
        """
        return [IsAuthenticated(), IsSameUser()]
    
    @swagger_auto_schema(
        tags=['User Visited Refuges'],
        operation_description="Elimina un refugi dels visitats de l'usuari. Requereix autenticació amb token JWT de Firebase i ser el mateix usuari.",
        responses={
            200: openapi.Response(
                description='Refugi eliminat dels visitats',
                schema=UserRefugiInfoResponseSerializer,
                examples={
                    'application/json': EXAMPLE_USER_REFUGI_INFO_RESPONSE_1
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND
        }
    )
    def delete(self, request, uid, refuge_id):
        """Elimina un refugi dels visitats de l'usuari"""
        try:
            controller = UserController()
            success, refugis_info, error_message = controller.remove_refugi_visitat(uid, refuge_id)
            
            if not success:
                status_code = status.HTTP_404_NOT_FOUND if 'no trobat' in error_message else status.HTTP_400_BAD_REQUEST
                return Response({
                    'error': error_message
                }, status=status_code)
            
            # Retorna la llista actualitzada amb la informació dels refugis
            data = {'count': len(refugis_info), 'results': refugis_info}
            serializer = UserRefugiInfoResponseSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en delete_refugi_visitat: {str(e)}")
            return Response({
                'error': INTERNAL_SERVER_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== USER AVATAR ENDPOINT: /users/{uid}/avatar/ ==========

class UserAvatarAPIView(APIView):
    """
    Gestiona operacions sobre l'avatar d'un usuari:
    - PATCH: Puja o actualitza l'avatar de l'usuari (requereix autenticació, només el mateix usuari)
    - DELETE: Elimina l'avatar de l'usuari (requereix autenticació, només el mateix usuari)
    """
    permission_classes = [IsAuthenticated, IsSameUser]
    parser_classes = [MultiPartParser, FormParser]
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Puja o actualitza l'avatar d'un usuari. "
            "El fitxer es guarda a R2 en la carpeta users-avatars/{uid}/. "
            "\n\nFormats acceptats: JPEG, JPG, PNG, WebP, HEIC, HEIF"
            "\n\nRequereix autenticació i només pot ser executat pel mateix usuari."
        ),
        manual_parameters=[
            openapi.Parameter(
                'uid',
                openapi.IN_PATH,
                description="UID de l'usuari",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'file',
                openapi.IN_FORM,
                description="Fitxer d'imatge de l'avatar",
                type=openapi.TYPE_FILE,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Avatar pujat correctament",
                schema=MediaMetadataSerializer,
                examples={
                    'application/json': EXAMPLE_AVATAR_UPLOAD_RESPONSE
                }
            ),
            400: ERROR_400_INVALID_FILE_TYPE,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_USER_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def patch(self, request, uid):
        """Puja o actualitza l'avatar d'un usuari"""
        try:
            # Verificar que hi ha fitxer
            if 'file' not in request.FILES:
                return Response({
                    'error': 'No s\'ha proporcionat cap fitxer'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            file=  request.FILES['file']
            
            # Pujar avatar
            controller = UserController()
            success, avatar_metadata, error_message = controller.upload_user_avatar(uid, file)
            
            if not success:
                if 'no trobat' in error_message:
                    return Response({
                        'error': error_message
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'no permès' in error_message or 'Content type' in error_message:
                    return Response({
                        'error': error_message
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({
                        'error': error_message
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            serializer = MediaMetadataSerializer(avatar_metadata)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error pujant avatar: {str(e)}")
            return Response({
                'error': 'Error pujant l\'avatar'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Elimina l'avatar d'un usuari. "
            "\n\nRequereix autenticació i només pot ser executat pel mateix usuari."
        ),
        manual_parameters=[
            openapi.Parameter(
                'uid',
                openapi.IN_PATH,
                description="UID de l'usuari",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            204: SUCCESS_204_NO_CONTENT,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_AVATAR_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request, uid):
        """Elimina l'avatar d'un usuari"""
        try:
            controller = UserController()
            success, error_message = controller.delete_user_avatar(uid)
            
            if not success:
                if 'no trobat' in error_message or 'no té cap avatar' in error_message:
                    return Response({
                        'error': error_message
                    }, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({
                        'error': error_message
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error eliminant avatar: {str(e)}")
            return Response({
                'error': 'Error eliminant l\'avatar'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
