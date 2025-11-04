"""
Views per a la gestió d'usuaris amb endpoints REST estàndard
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.user_controller import UserController
from ..serializers.user_serializer import (
    UserSerializer, 
    UserCreateSerializer, 
    UserUpdateSerializer,
)
from ..permissions import IsSameUser
from ..permissions import IsSameUser

# Configurar logging
logger = logging.getLogger(__name__)

# ========== COLLECTION ENDPOINT: /users/ ==========

@swagger_auto_schema(
    methods=['post'],
    operation_description="Crea un nou usuari. Requereix autenticació amb token JWT de Firebase.",
    operation_description="Crea un nou usuari. Requereix autenticació amb token JWT de Firebase.",
    request_body=UserCreateSerializer,
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        201: UserSerializer,
        400: 'Dades invàlides',
        401: 'No autoritzat',
        401: 'No autoritzat',
        409: 'Usuari ja existeix'
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def users_collection(request):
    """
    Gestiona col·lecció d'usuaris:
    - POST: Crear nou usuari
    """
    if request.method == 'POST':
        return _create_user(request)

def _create_user(request):
    """Crear nou usuari amb el UID del token de Firebase"""
    try:
        # Obté el UID del token de Firebase (assignat pel middleware)
        uid = getattr(request, 'user_uid', None)
        if not uid:
            return Response({
                'error': 'UID no trobat al token d\'autenticació'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Valida les dades d'entrada
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Dades invàlides',
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
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========== ITEM ENDPOINT: /users/{uid}/ ==========

@swagger_auto_schema(
    methods=['get'],
    operation_description="Obté un usuari per UID. Requereix autenticació amb token JWT de Firebase.",
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        200: UserSerializer,
        401: 'No autoritzat',
        403: 'Permís denegat',
        404: 'Usuari no trobat'
    }
)
@swagger_auto_schema(
    methods=['patch'],
    operation_description="Actualitza les dades d'un usuari. Requereix autenticació amb token JWT de Firebase.",
    request_body=UserUpdateSerializer,
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        200: UserSerializer,
        400: 'Dades invàlides',
        401: 'No autoritzat',
        403: 'Permís denegat',
        401: 'No autoritzat',
        403: 'Permís denegat',
        404: 'Usuari no trobat'
    }
)
@swagger_auto_schema(
    methods=['delete'],
    operation_description="Elimina un usuari. Requereix autenticació amb token JWT de Firebase.",
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    operation_description="Elimina un usuari. Requereix autenticació amb token JWT de Firebase.",
    manual_parameters=[
        openapi.Parameter(
            'Authorization',
            openapi.IN_HEADER,
            description="Token JWT de Firebase (format: Bearer <token>)",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    responses={
        204: 'Usuari eliminat correctament',
        401: 'No autoritzat',
        403: 'Permís denegat',
        401: 'No autoritzat',
        403: 'Permís denegat',
        404: 'Usuari no trobat'
    }
)
@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsSameUser])
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsSameUser])
def user_detail(request, uid):
    """
    Gestiona operacions sobre un usuari específic:
    - GET: Obtenir usuari per UID
    - PATCH: Actualitzar usuari  
    - DELETE: Eliminar usuari
    
    Requereix autenticació i que l'usuari accedeixi a les seves pròpies dades
    
    Requereix autenticació i que l'usuari accedeixi a les seves pròpies dades
    """
    
    if request.method == 'GET':
        return _get_user(request, uid)
    elif request.method == 'PATCH':
        return _update_user(request, uid)
    elif request.method == 'DELETE':
        return _delete_user(request, uid)

def _get_user(request, uid):
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
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _update_user(request, uid):
    """Actualitzar usuari"""
    try:
        # Valida les dades d'entrada
        serializer = UserUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Dades invàlides',
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
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _delete_user(request, uid):
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
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)