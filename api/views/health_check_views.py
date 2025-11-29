"""
Views per a la gestió de health check de l'API
"""
import logging
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..serializers.refugi_lliure_serializer import HealthCheckResponseSerializer
from ..utils.swagger_examples import (
    EXAMPLE_HEALTH_CHECK_RESPONSE,
    EXAMPLE_HEALTH_CHECK_UNHEALTHY,
)
from ..utils.swagger_error_responses import (
    ERROR_503_SERVICE_UNAVAILABLE,
)


# Configurar logging
logger = logging.getLogger(__name__)

# ========== ITEM ENDPOINT: /health/ ==========

class HealthCheckAPIView(APIView):
    """
    Verifica l'estat de l'API i la connexió amb Firebase:
    - GET: Comprova l'estat de salut del sistema (no requereix autenticació)
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        security=[],
        operation_description=(
            "Comprova l'estat de salut de l'API i la connexió amb Firebase. "
            "Retorna informació sobre l'estat del servei, Firebase i les col·leccions de Firestore. "
            "Aquest endpoint no requereix autenticació i pot ser utilitzat per monitoratge."
        ),
        responses={
            200: openapi.Response(
                description='API en estat saludable',
                schema=HealthCheckResponseSerializer,
                examples={
                    'application/json': EXAMPLE_HEALTH_CHECK_RESPONSE
                }
            ),
            503: ERROR_503_SERVICE_UNAVAILABLE
        }
    )
    def get(self, request):
        """Obtenir l'estat de l'API"""
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
