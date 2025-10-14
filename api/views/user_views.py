"""
Views per a la gestió d'usuaris amb endpoints REST estàndard
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.user_controller import UserController
from ..serializers.user_serializer import (
    UserSerializer, 
    UserCreateSerializer, 
    UserUpdateSerializer,
    PaginationQuerySerializer
)

# Configurar logging
logger = logging.getLogger(__name__)

# ========== COLLECTION ENDPOINT: /users/ ==========

@swagger_auto_schema(
    methods=['get'],
    operation_description="Obté una llista d'usuaris amb paginació",
    manual_parameters=[
        openapi.Parameter('limit', openapi.IN_QUERY, description="Nombre màxim d'usuaris a retornar (màx: 100)", 
                         type=openapi.TYPE_INTEGER, default=20),
        openapi.Parameter('offset', openapi.IN_QUERY, description="Nombre d'usuaris a saltar", 
                         type=openapi.TYPE_INTEGER, default=0)
    ],
    responses={
        200: openapi.Response(
            description="Llista d'usuaris",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'users': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    'total_count': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'limit': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'offset': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'has_next': openapi.Schema(type=openapi.TYPE_BOOLEAN)
                }
            )
        )
    }
)
@swagger_auto_schema(
    methods=['post'],
    operation_description="Crea un nou usuari",
    request_body=UserCreateSerializer,
    responses={
        201: UserSerializer,
        400: 'Dades invàlides',
        409: 'Usuari ja existeix'
    }
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def users_collection(request):
    """
    Gestiona col·lecció d'usuaris:
    - GET: Llistar usuaris amb paginació  
    - POST: Crear nou usuari
    """
    
    if request.method == 'GET':
        return _list_users(request)
    elif request.method == 'POST':
        return _create_user(request)

def _list_users(request):
    """Llistar usuaris amb paginació"""
    try:
        # Valida paràmetres de paginació
        pagination_data = {
            'limit': request.GET.get('limit', 20),
            'offset': request.GET.get('offset', 0)
        }
        
        pagination_serializer = PaginationQuerySerializer(data=pagination_data)
        if not pagination_serializer.is_valid():
            return Response({
                'error': 'Paràmetres de paginació invàlids',
                'details': pagination_serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        limit = pagination_serializer.validated_data['limit']
        offset = pagination_serializer.validated_data['offset']
        
        # Obté els usuaris
        controller = UserController()
        success, users, error_message = controller.list_users(limit, offset)
        
        if not success:
            return Response({
                'error': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Serialitza els usuaris
        users_serializer = UserSerializer(users, many=True)
        
        # Prepara la resposta amb metadades de paginació
        response_data = {
            'users': users_serializer.data,
            'total_count': len(users),
            'limit': limit,
            'offset': offset,
            'has_next': len(users) == limit
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en list_users: {str(e)}")
        return Response({
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def _create_user(request):
    """Crear nou usuari"""
    try:
        # Valida les dades d'entrada
        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Dades invàlides',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Crea l'usuari
        controller = UserController()
        success, user, error_message = controller.create_user(serializer.validated_data)
        
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
    operation_description="Obté un usuari per UID",
    responses={
        200: UserSerializer,
        404: 'Usuari no trobat'
    }
)
@swagger_auto_schema(
    methods=['put'],
    operation_description="Actualitza les dades d'un usuari",
    request_body=UserUpdateSerializer,
    responses={
        200: UserSerializer,
        400: 'Dades invàlides',
        404: 'Usuari no trobat'
    }
)
@swagger_auto_schema(
    methods=['delete'],
    operation_description="Elimina un usuari",
    responses={
        204: 'Usuari eliminat correctament',
        404: 'Usuari no trobat'
    }
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([AllowAny])
def user_detail(request, uid):
    """
    Gestiona operacions sobre un usuari específic:
    - GET: Obtenir usuari per UID
    - PUT: Actualitzar usuari  
    - DELETE: Eliminar usuari
    """
    
    if request.method == 'GET':
        return _get_user(request, uid)
    elif request.method == 'PUT':
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

# ========== SEARCH ENDPOINT: /users/search/ ==========

@swagger_auto_schema(
    method='get',
    operation_description="Cerca un usuari per email",
    manual_parameters=[
        openapi.Parameter('email', openapi.IN_QUERY, description="Email de l'usuari a cercar", 
                         type=openapi.TYPE_STRING, required=True)
    ],
    responses={
        200: UserSerializer,
        400: 'Email no proporcionat',
        404: 'Usuari no trobat'
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def search_user_by_email(request):
    """Cerca un usuari per email"""
    try:
        email = request.GET.get('email')
        if not email:
            return Response({
                'error': 'Email no proporcionat'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        controller = UserController()
        success, user, error_message = controller.get_user_by_email(email)
        
        if not success:
            return Response({
                'error': error_message
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error en search_user_by_email: {str(e)}")
        return Response({
            'error': 'Error intern del servidor'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)