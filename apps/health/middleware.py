"""
Converteix en un 503 «unhealthy» l'error de BD del health check quan PostgreSQL és inabastable.

Amb `ATOMIC_REQUESTS`, si la BD no respon la petició falla en obrir la transacció, abans d'arribar a la vista
(que és qui normalment informa `database: false`). Només afecta `/api/health/`.
"""
import logging

from django.db.utils import Error as DatabaseError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

HEALTH_PATH = '/api/health/'


class HealthDatabaseErrorMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if request.path == HEALTH_PATH and isinstance(exception, DatabaseError):
            logger.error(f'Health check: base de dades no disponible ({type(exception).__name__})')
            return JsonResponse({
                'status': 'unhealthy',
                'message': 'Database unavailable',
                'firebase': False,
                'database': False,
            }, status=503)
        return None
