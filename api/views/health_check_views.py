"""
Health check de l'API (D43): comprova PostgreSQL i que Firebase Admin estigui inicialitzat.

No fa cap crida de xarxa (ni a Firebase, ni a R2) ni toca cap cache; mai exposa el text d'una excepció.
"""
import logging

import firebase_admin
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.database_health import check_database
from ..serializers.health_serializer import HealthCheckResponseSerializer
from ..utils.swagger_examples import (
    EXAMPLE_HEALTH_CHECK_RESPONSE,
    EXAMPLE_HEALTH_CHECK_UNHEALTHY,
)

logger = logging.getLogger(__name__)


def _firebase_ok() -> bool:
    """Firebase Admin inicialitzat (comprovació local, sense xarxa)."""
    try:
        firebase_admin.get_app()
        return True
    except Exception as e:
        logger.error(f'Health check: Firebase Admin no inicialitzat ({type(e).__name__})')
        return False


class HealthCheckAPIView(APIView):
    """GET: estat de salut de l'API (no requereix autenticació)."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        security=[],
        operation_description=(
            "Comprova l'estat de salut de l'API: la connexió amb PostgreSQL i que Firebase Admin estigui "
            "inicialitzat. No requereix autenticació i pot ser utilitzat per monitoratge."
        ),
        responses={
            200: openapi.Response(
                description='API en estat saludable',
                schema=HealthCheckResponseSerializer,
                examples={'application/json': EXAMPLE_HEALTH_CHECK_RESPONSE},
            ),
            503: openapi.Response(
                description='Algun component no està disponible',
                schema=HealthCheckResponseSerializer,
                examples={'application/json': EXAMPLE_HEALTH_CHECK_UNHEALTHY},
            ),
        },
    )
    def get(self, request):
        database = check_database()
        firebase = _firebase_ok()
        healthy = database and firebase
        data = {
            'status': 'healthy' if healthy else 'unhealthy',
            'message': 'API operativa' if healthy else 'Servei no disponible',
            'firebase': firebase,
            'database': database,
        }
        return Response(data, status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)
