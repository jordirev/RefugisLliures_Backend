"""
Views per a la gestió de mitjans (imatges i vídeos) de refugis
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..permissions import IsMediaUploader
from ..utils.swagger_examples import EXAMPLE_REFUGI_MEDIA_LIST, EXAMPLE_REFUGI_MEDIA_UPLOAD_RESPONSE
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_FILE_TYPE,
    ERROR_400_NO_FILES,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_NOT_MEDIA_OWNER,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_404_MEDIA_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR,
    SUCCESS_204_NO_CONTENT
)

logger = logging.getLogger(__name__)


class RefugiMediaAPIView(APIView):
    """
    Gestiona la lectura i pujada de mitjans (imatges i vídeos) per a un refugi específic.
    GET + POST /api/refugis/{id}/media/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = RefugiLliureController()
    
    @swagger_auto_schema(
        tags=['Refuge Media'],
        operation_description=(
            "Obté la llista de tots els mitjans (imatges i vídeos) d'un refugi amb URLs prefirmades. "
            "\n\nRequereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="Llista de mitjans",
                examples={
                    'application/json': EXAMPLE_REFUGI_MEDIA_LIST
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request, id):
        """
        Llista tots els mitjans d'un refugi amb metadades completes.
        """
        try:
            # URLs prefirmades vàlides per 1 hora
            expiration = 3600 
            
            media_list, error = self.controller.get_refugi_media(id, expiration)
            
            if error:
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({'media': media_list}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error llistant mitjans: {str(e)}")
            return Response(
                {'error': 'Error obtenint els mitjans'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        tags=['Refuge Media'],
        operation_description=(
            "Puja una o més imatges/vídeos per a un refugi específic. "
            "Els fitxers es guarden a R2 en la carpeta refugis-lliures/{refuge_id}/. "
            "\n\nFormats acceptats:"
            "\n- Imatges: JPEG, JPG, PNG, WebP, HEIC, HEIF"
            "\n- Vídeos: MP4, MOV, AVI, WebM"
            "\n\nRequereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'files',
                openapi.IN_FORM,
                description='Fitxers a pujar (imatges o vídeos)',
                type=openapi.TYPE_FILE,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Mitjans pujats correctament",
                examples={
                    'application/json': EXAMPLE_REFUGI_MEDIA_UPLOAD_RESPONSE
                }
            ),
            400: ERROR_400_NO_FILES,
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request, id):
        """
        Puja mitjans per a un refugi.
        """
        try:
            files = request.FILES.getlist('files')
            
            if not files:
                return Response(
                    {'error': 'No s\'han proporcionat fitxers'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir UID de l'usuari autenticat
            creator_uid = getattr(request, 'user_uid', None)
            if not creator_uid:
                return Response({
                    'error': 'No autenticat',
                    'message': 'UID d\'usuari no trobat'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Delegar al controller
            result, error = self.controller.upload_refugi_media(id, files, creator_uid)
            
            if error:
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en l'endpoint de pujada de mitjans: {str(e)}")
            return Response(
                {'error': 'Error procesant la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RefugiMediaDeleteAPIView(APIView):
    """
    Gestiona l'eliminació individual d'un mitjà d'un refugi.
    DELETE /api/refugis/{id}/media/{key}
    """
    permission_classes = [IsAuthenticated, IsMediaUploader]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = RefugiLliureController()
    
    @swagger_auto_schema(
        tags=['Refuge Media'],
        operation_description=(
            "Elimina un mitjà específic d'un refugi utilitzant la seva key. "
            "\n Si el mitjà és una imatge vinculada a una experiència, també s'eliminarà d'aquesta. "
            "\n\nRequereix autenticació i que l'usuari sigui el creador del mitjà o administrador."
        ),
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'key',
                openapi.IN_PATH,
                description="Key del mitjà a eliminar (path complet al fitxer a R2)",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            204: SUCCESS_204_NO_CONTENT,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_NOT_MEDIA_OWNER,
            404: ERROR_404_MEDIA_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request, id, key):
        """
        Elimina un mitjà d'un refugi a partir de la seva key.
        """
        try:
            # Decodificar la key (pot venir codificada en la URL)
            from urllib.parse import unquote
            decoded_key = unquote(key)
            
            # Delegar al controller
            success, error = self.controller.delete_refugi_media(id, decoded_key)
            
            if error:
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if not success:
                return Response(
                    {'error': 'Error eliminant el mitjà'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'success': True,
                'message': 'Mitjà eliminat correctament',
                'key': decoded_key
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en l'endpoint d'eliminació de mitjà: {str(e)}")
            return Response(
                {'error': 'Error procesant la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )  