"""
Vistes d'usuari que encara viuen a Firestore: avisos de moderació.

Les altres rutes d'usuari (crear, detall, esborrar, avatar, edat, preferits i visitats) són a PostgreSQL:
`apps/accounts/views.py` (chunk 3 de la migració).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..controllers.media_report_controller import MediaReportController
from ..permissions import HasProfile, IsSameUser
from ..serializers.media_serializer import ModerationNoticeSerializer
from ..utils.swagger_error_responses import (
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_500_INTERNAL_ERROR,
)
from ..utils.swagger_examples import EXAMPLE_MODERATION_NOTICES

INTERNAL_SERVER_ERROR = "Error intern del servidor"

logger = logging.getLogger(__name__)


class UserModerationNoticesAPIView(APIView):
    """GET: avisos de moderació de l'usuari (declaració de motius, art. 17 DSA)"""
    permission_classes = [IsAuthenticated, HasProfile, IsSameUser]

    @swagger_auto_schema(
        tags=['Users'],
        operation_description=(
            "Llista els avisos de moderació de l'usuari (més recents primer): ocultacions cautelars, "
            "retirades, strikes, bloquejos i restauracions, amb la motivació i la via de recurs."
        ),
        responses={
            200: openapi.Response(description='Avisos de moderació',
                                  examples={'application/json': EXAMPLE_MODERATION_NOTICES}),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            500: ERROR_500_INTERNAL_ERROR,
        }
    )
    def get(self, request, uid):
        try:
            notices, error_message = MediaReportController().get_user_notices(uid)
            if error_message:
                return Response({'error': error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({'notices': ModerationNoticeSerializer(notices, many=True).data},
                            status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error en moderation_notices: {str(e)}")
            return Response({'error': INTERNAL_SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
