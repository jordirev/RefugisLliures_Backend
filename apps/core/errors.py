"""
Errors 500 amb traçabilitat (convenció de les features migrades a PostgreSQL).

La resposta porta un **missatge específic del punt que ha fallat** i un `error_id` (UUID v7):

    {"error": "Error en esborrar el fitxer a R2", "error_id": "0190…"}

El mateix `error_id` es desa al log del servidor amb la traça completa, de manera que un informe d'usuari es pot
localitzar. **Mai** es retorna `str(e)` ni el nom o el text de l'excepció: pot contenir SQL, hosts, bucket, claus o
rutes. El missatge ha de ser un text fix escrit a mà.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from api.utils.ids import uuid7

_default_logger = logging.getLogger(__name__)


def server_error(message, exc=None, *, logger=None):
    """
    Registra l'error (amb `error_id` i traça) i retorna la `Response` 500 `{"error": message, "error_id": …}`.

    `message`: text específic i fix del punt que ha fallat (mai derivat de l'excepció).
    `exc`: l'excepció capturada (si es crida dins d'un `except`, es pot ometre).
    `logger`: el logger del mòdul que crida (per defecte el d'`apps.core.errors`).
    """
    error_id = str(uuid7())
    (logger or _default_logger).error('%s [error_id=%s]', message, error_id, exc_info=exc if exc is not None else True)
    return Response({'error': message, 'error_id': error_id}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
