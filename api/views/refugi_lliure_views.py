"""
Views per a la gestió de refugis utilitzant arquitectura en capes
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..serializers.refugi_lliure_serializer import (
    RefugiSerializer, 
    RefugiSearchResponseSerializer,
    HealthCheckResponseSerializer,
    RefugiSearchFiltersSerializer
)

# Configurar logging
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Endpoint per comprovar l'estat de l'API"""
    try:
        controller = RefugiLliureController()
        health_data, error = controller.health_check()
        
        if error and health_data.get('status') == 'unhealthy':
            # Serialitzar resposta d'error
            serializer = HealthCheckResponseSerializer(data=health_data)
            if serializer.is_valid():
                return Response(serializer.validated_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            else:
                return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Serialitzar resposta exitosa
        serializer = HealthCheckResponseSerializer(data=health_data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response(health_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}')
        error_data = {
            'status': 'unhealthy',
            'message': f'Error: {str(e)}',
            'firebase': False
        }
        return Response(error_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

@api_view(['GET'])
@permission_classes([AllowAny])
def refugi_detail(request, refugi_id):
    """Obtenir els detalls d'un refugi específic"""
    try:
        controller = RefugiLliureController()
        refugi, error = controller.get_refugi_by_id(refugi_id)
        
        if error:
            if "not found" in error.lower():
                return Response({
                    'error': error
                }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    'error': error
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Serialitzar el refugi
        serializer = RefugiSerializer(refugi.to_dict())
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Error getting refugi detail: {str(e)}')
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def refugis_collection(request):
    """
    Endpoint unificat per obtenir refugis amb o sense filtres
    - Sense filtres: retorna totes les coordenades dels refugis
    - Amb filtres: cerca i retorna refugis que compleixen els criteris
    """
    try:
        # Validar paràmetres d'entrada
        filters_serializer = RefugiSearchFiltersSerializer(data=request.GET)
        if not filters_serializer.is_valid():
            return Response({
                'error': 'Invalid query parameters',
                'details': filters_serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        controller = RefugiLliureController()
        search_result, error = controller.search_refugis(filters_serializer.validated_data)
        
        if error:
            return Response({
                'error': error
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Serialitzar la resposta
        response_serializer = RefugiSearchResponseSerializer(data=search_result)
        if response_serializer.is_valid():
            return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response(search_result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Error processing refugis request: {str(e)}')
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)