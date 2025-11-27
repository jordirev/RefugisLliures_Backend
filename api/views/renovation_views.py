"""
Views per a la gestió de renovations amb endpoints REST estàndard
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.renovation_controller import RenovationController
from ..serializers.renovation_serializer import (
    RenovationSerializer,
    RenovationCreateSerializer,
    RenovationUpdateSerializer
)
from ..permissions import IsCreator

# Configurar logging
logger = logging.getLogger(__name__)

# Definim constants d'errors
ERROR_400_INVALID_DATA = 'Dades invàlides'
ERROR_401_UNAUTHORIZED = 'No autoritzat'
ERROR_403_FORBIDDEN = 'No tens permís per realitzar aquesta acció'
ERROR_404_RENOVATION_NOT_FOUND = 'Renovation no trobada'
ERROR_409_OVERLAP = 'Hi ha un solapament temporal amb una altra renovation'
ERROR_500_INTERNAL_ERROR = 'Error intern del servidor'


# ========== COLLECTION ENDPOINT: /renovations/ ==========

class RenovationListAPIView(APIView):
    """
    Gestiona operacions sobre la col·lecció de renovations:
    - GET: Obtenir totes les renovations (requereix autenticació)
    - POST: Crear una nova renovation (requereix autenticació)
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Obté la llista de totes les renovations actives (i.e., no finalitzades).",
        responses={
            200: openapi.Response(
                description='Llista de renovations',
                schema=RenovationSerializer(many=True)
            ),
            401: ERROR_401_UNAUTHORIZED,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request):
        """Obtenir totes les renovations"""
        try:
            controller = RenovationController()
            success, renovations, error = controller.get_all_renovations()
            
            if not success:
                return Response({
                    'error': error
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar les renovations
            serializer = RenovationSerializer([r.to_dict() for r in renovations], many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error getting renovations: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description=(
            "Crea una nova renovation. No es poden solapar temporalment amb "
            "altres renovations del mateix refugi."
        ),
        request_body=RenovationCreateSerializer,
        responses={
            201: openapi.Response(
                description='Renovation creada',
                schema=RenovationSerializer
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            409: ERROR_409_OVERLAP,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request):
        """Crear una nova renovation"""
        try:
            # Validar dades
            serializer = RenovationCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response({
                    'error': ERROR_401_UNAUTHORIZED
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Crear renovation
            controller = RenovationController()
            success, renovation, error = controller.create_renovation(
                serializer.validated_data,
                user_uid
            )
            
            if not success:
                if 'solapa' in error.lower():
                    # renovation conté la renovation solapada
                    response_serializer = RenovationSerializer(renovation.to_dict())
                    return Response({
                        'error': error,
                        'overlapping_renovation': response_serializer.data
                    }, status=status.HTTP_409_CONFLICT)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la renovation creada
            response_serializer = RenovationSerializer(renovation.to_dict())
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f'Error creating renovation: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== ITEM ENDPOINT: /renovations/{id} (GET, PATCH, DELETE) ==========

class RenovationAPIView(APIView):
    """
    Gestiona operacions sobre una renovation:
    - GET: Obtenir una renovation específica
    - PATCH: Actualitzar una renovation (només el creador)
    - DELETE: Eliminar una renovation (només el creador)
    """
    def get_permissions(self):
        """
        Retorna els permisos segons el mètode HTTP:
        - GET: només IsAuthenticated
        - PATCH/DELETE: IsAuthenticated + IsCreator
        """
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCreator()]
    
    @swagger_auto_schema(
        operation_description="Obté una renovation específica",
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_QUERY,
                description="ID de la renovation",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Renovation trobada',
                schema=RenovationSerializer
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_RENOVATION_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request):
        """Obtenir una renovation específica"""
        try:
            # Obtenir ID de la renovation
            renovation_id = request.query_params.get('id')
            if not renovation_id:
                return Response({
                    'error': 'ID de renovation requerit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtenir renovation
            controller = RenovationController()
            success, renovation, error = controller.get_renovation_by_id(renovation_id)
            
            if not success:
                if 'no trobada' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la renovation
            response_serializer = RenovationSerializer(renovation.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error getting renovation: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_description=(
            "Actualitza una renovation. Només el creador pot editar-la. "
            "Els camps refuge_id i creator_uid no es poden editar. "
            "Si s'editen les dates, es comprova que no hi hagi solapaments temporals."
        ),
        request_body=RenovationUpdateSerializer,
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_QUERY,
                description="ID de la renovation a actualitzar",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Renovation actualitzada',
                schema=RenovationSerializer
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_RENOVATION_NOT_FOUND,
            409: ERROR_409_OVERLAP,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def patch(self, request):
        """Actualitzar una renovation"""
        try:
            # Obtenir ID de la renovation
            renovation_id = request.query_params.get('id')
            if not renovation_id:
                return Response({
                    'error': 'ID de renovation requerit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validar dades
            serializer = RenovationUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'error': ERROR_400_INVALID_DATA,
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response({
                    'error': ERROR_401_UNAUTHORIZED
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Actualitzar renovation
            controller = RenovationController()
            success, renovation, error = controller.update_renovation(
                renovation_id,
                serializer.validated_data,
                user_uid
            )
            
            if not success:
                if 'no trobada' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'creador' in error.lower() or 'permís' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_403_FORBIDDEN)
                elif 'solapa' in error.lower():
                    # renovation conté la renovation solapada
                    response_serializer = RenovationSerializer(renovation.to_dict())
                    return Response({
                        'error': error,
                        'overlapping_renovation': response_serializer.data
                    }, status=status.HTTP_409_CONFLICT)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la renovation actualitzada
            response_serializer = RenovationSerializer(renovation.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error updating renovation: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @swagger_auto_schema(
        operation_description=(
            "Elimina una renovation. Només el creador pot eliminar-la."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_QUERY,
                description="ID de la renovation a eliminar",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            204: 'Renovation eliminada correctament',
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_RENOVATION_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request):
        """Eliminar una renovation"""
        try:
            # Obtenir ID de la renovation
            renovation_id = request.query_params.get('id')
            if not renovation_id:
                return Response({
                    'error': 'ID de renovation requerit'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response({
                    'error': ERROR_401_UNAUTHORIZED
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Eliminar renovation
            controller = RenovationController()
            success, error = controller.delete_renovation(renovation_id, user_uid)
            
            if not success:
                if 'no trobada' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'creador' in error.lower() or 'permís' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_403_FORBIDDEN)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f'Error deleting renovation: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== COLLECTION ENDPOINT: /renovations/{id}/participants ==========

class RenovationParticipantsAPIView(APIView):
    """
    Gestiona l'afegiment de participants a una renovation:
    - POST: Afegir l'usuari autenticat com a participant
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description=(
            "Afegeix l'usuari autenticat com a participant a una renovation. "
            "El creador no pot unir-se a la seva pròpia renovation."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="ID de la renovation",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Participant afegit',
                schema=RenovationSerializer
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_RENOVATION_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request, id):
        """Afegir participant a una renovation"""
        try:
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response({
                    'error': ERROR_401_UNAUTHORIZED
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Afegir participant
            controller = RenovationController()
            success, renovation, error = controller.add_participant(id, user_uid)
            
            if not success:
                if 'no trobada' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'creador' in error.lower() or 'ja és participant' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la renovation actualitzada
            response_serializer = RenovationSerializer(renovation.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error adding participant: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== COLLECTION ENDPOINT: /renovations/{id}/participants/{uid} ==========

class RenovationParticipantDetailAPIView(APIView):
    """
    Gestiona l'eliminació de participants d'una renovation:
    - DELETE: Eliminar un participant
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description=(
            "Elimina un participant d'una renovation. "
            "Un participant pot eliminar-se a si mateix. "
            "El creador pot eliminar qualsevol participant."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="ID de la renovation",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'uid',
                openapi.IN_PATH,
                description="UID del participant a eliminar",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Participant eliminat',
                schema=RenovationSerializer
            ),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_RENOVATION_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request, id, uid):
        """Eliminar participant d'una renovation"""
        try:
            # Obtenir UID de l'usuari autenticat
            requester_uid = getattr(request, 'user_uid', None)
            if not requester_uid:
                return Response({
                    'error': ERROR_401_UNAUTHORIZED
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Eliminar participant
            controller = RenovationController()
            success, renovation, error = controller.remove_participant(id, uid, requester_uid)
            
            if not success:
                if 'no trobada' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                elif 'permís' in error.lower() or 'no és participant' in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_403_FORBIDDEN)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la renovation actualitzada
            response_serializer = RenovationSerializer(renovation.to_dict())
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error removing participant: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
