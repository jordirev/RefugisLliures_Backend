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

from api.views.user_views import UID_NOT_FOUND_ERROR, UID_NOT_FOUND_MESSAGE
from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..permissions import IsMediaUploader

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
                    'application/json': {
                        'media': [
                            {
                                'key': 'refugis-lliures/refugi123/photo1.jpg',
                                'url': 'https://presigned-url...',
                                'creator_uid': 'user123',
                                'uploaded_at': '2024-12-08T10:30:00Z'
                            }
                        ]
                    }
                }
            ),
            401: openapi.Response(description="No autenticat"),
            404: openapi.Response(description="Refugi no trobat"),
            500: openapi.Response(description="Error del servidor")
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
                    'application/json': {
                        'uploaded': [
                            {
                                'filename': 'photo1.jpg',
                                'key': 'refugis-lliures/refugi123/uuid.jpg',
                                'url': 'https://presigned-url...',
                                'creator_uid': 'user123',
                                'uploaded_at': '2024-12-08T10:30:00Z'
                            }
                        ],
                        'failed': [
                            {
                                'filename': 'invalid.txt',
                                'error': 'Content type not allowed'
                            }
                        ]
                    }
                }
            ),
            400: openapi.Response(description="Petició invàlida"),
            401: openapi.Response(description="No autenticat"),
            403: openapi.Response(description="No autoritzat"),
            404: openapi.Response(description="Refugi no trobat"),
            500: openapi.Response(description="Error del servidor")
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
                    'error': UID_NOT_FOUND_ERROR,
                    'message': UID_NOT_FOUND_MESSAGE
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
        operation_description=(
            "Elimina un mitjà específic d'un refugi utilitzant la seva key. "
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
            200: openapi.Response(
                description="Mitjà eliminat correctament",
                examples={
                    'application/json': {
                        'success': True,
                        'message': 'Mitjà eliminat correctament',
                        'key': 'refugis-lliures/refugi123/uuid.jpg'
                    }
                }
            ),
            400: openapi.Response(description="Petició invàlida"),
            401: openapi.Response(description="No autenticat"),
            403: openapi.Response(description="No autoritzat"),
            404: openapi.Response(description="Mitjà no trobat"),
            500: openapi.Response(description="Error del servidor")
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