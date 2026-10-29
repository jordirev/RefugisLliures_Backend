"""Comprovació de la connexió a PostgreSQL per al health check."""
import logging

from django.db import connection
from django.db.utils import Error as DatabaseError

logger = logging.getLogger(__name__)


def check_database() -> bool:
    """Executa `SELECT 1` amb la connexió `default`. Retorna `False` si la BD no respon (sense filtrar detalls)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return True
    except DatabaseError as e:
        logger.error(f'Database health check failed: {type(e).__name__}')
        return False
    except Exception as e:      # qualsevol altre error (driver, configuració) també és «BD no disponible»: 503, mai 500
        logger.error(f'Database health check failed (inesperat): {type(e).__name__}')
        return False
