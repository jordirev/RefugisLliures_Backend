"""
Views per gestionar la cache
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..services.cache_service import cache_service

logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method='get',
    operation_description="Obté estadístiques de la cache Redis",
    responses={
        200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'connected': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                'keys': openapi.Schema(type=openapi.TYPE_INTEGER),
                'memory_used': openapi.Schema(type=openapi.TYPE_STRING),
                'hits': openapi.Schema(type=openapi.TYPE_INTEGER),
                'misses': openapi.Schema(type=openapi.TYPE_INTEGER),
            }
        )
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def cache_stats(request):
    """Obté estadístiques de la cache"""
    try:
        stats = cache_service.get_stats()
        return Response(stats, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return Response({
            'error': 'Error obtenint estadístiques de cache',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='delete',
    operation_description="Neteja tota la cache",
    responses={
        200: 'Cache netejada correctament',
        500: 'Error netejant la cache'
    }
)
@api_view(['DELETE'])
@permission_classes([AllowAny])  # TODO: Canviar a IsAdminUser en producció
def cache_clear(request):
    """Neteja tota la cache"""
    try:
        success = cache_service.clear_all()
        if success:
            return Response({
                'message': 'Cache netejada correctament'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Error netejant la cache'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return Response({
            'error': 'Error netejant la cache',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='delete',
    operation_description="Elimina claus de cache que coincideixin amb un patró",
    manual_parameters=[
        openapi.Parameter('pattern', openapi.IN_QUERY, 
                         description="Patró de claus a eliminar (ex: 'refugi_*')", 
                         type=openapi.TYPE_STRING, required=True)
    ],
    responses={
        200: 'Claus eliminades correctament',
        400: 'Patró no proporcionat',
        500: 'Error eliminant claus'
    }
)
@api_view(['DELETE'])
@permission_classes([AllowAny])  # TODO: Canviar a IsAdminUser en producció
def cache_invalidate(request):
    """Elimina claus que coincideixin amb un patró"""
    try:
        pattern = request.query_params.get('pattern')
        if not pattern:
            return Response({
                'error': 'Patró no proporcionat'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = cache_service.delete_pattern(pattern)
        if success:
            return Response({
                'message': f'Claus amb patró "{pattern}" eliminades correctament'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Error eliminant claus'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Error invalidating cache: {str(e)}")
        return Response({
            'error': 'Error eliminant claus de cache',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
