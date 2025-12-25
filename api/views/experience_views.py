"""
Views per a la gestió d'experiències de refugis
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..controllers.experience_controller import ExperienceController
from ..permissions import IsExperienceCreator
from ..serializers.experience_serializer import (
    ExperienceCreateSerializer,
    ExperienceUpdateSerializer,
    ExperienceResponseSerializer,
    ExperienceListResponseSerializer
)

logger = logging.getLogger(__name__)


class ExperienceListAPIView(APIView):
    """
    Gestiona la llista d'experiències d'un refugi.
    GET + POST /api/refuges/{refuge_id}/experiences/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = ExperienceController()
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Obté la llista d'experiències d'un refugi ordenades per data de modificació descendent. "
            "Les dates es mostren en format DD/MM/YYYY."
            "\n\nRequereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="Llista d'experiències",
                schema=ExperienceListResponseSerializer
            ),
            401: openapi.Response(description="No autenticat"),
            404: openapi.Response(description="Refugi no trobat"),
            500: openapi.Response(description="Error intern del servidor")
        }
    )
    def get(self, request, refuge_id):
        """
        Llista totes les experiències d'un refugi amb URLs prefirmades per a les imatges.
        """
        try:
            experiences, error = self.controller.get_experiences_by_refuge(refuge_id)
            
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
    
            # Wrap experiences in a dict with 'experiences' key for the serializer
            response_data = {'experiences': [e.to_dict() for e in experiences]}
            serializer = ExperienceListResponseSerializer(response_data)

            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error llistant experiències: {str(e)}")
            return Response(
                {'error': 'Error obtenint les experiències'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Crea una nova experiència per a un refugi. "
            "S'envia el comentari i opcionalment fitxers mitjançant multipart/form-data. "
            "\n\nRequereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'comment',
                openapi.IN_FORM,
                description="Comentari de l'experiència",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'files',
                openapi.IN_FORM,
                description='Fitxers a pujar (imatges o vídeos)',
                type=openapi.TYPE_FILE,
                required=False
            )
        ],
        responses={
            201: openapi.Response(
                description="Experiència creada correctament",
                schema=ExperienceResponseSerializer
            ),
            400: openapi.Response(description="Dades invàlides"),
            401: openapi.Response(description="No autenticat"),
            404: openapi.Response(description="Refugi no trobat"),
            500: openapi.Response(description="Error intern del servidor")
        }
    )
    def post(self, request, refuge_id):
        """
        Crea una nova experiència per a un refugi.
        """
        try:
            # Validar dades
            serializer = ExperienceCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Dades invàlides', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir UID de l'usuari autenticat
            creator_uid = getattr(request, 'user_uid', None)
            if not creator_uid:
                return Response({
                    'error': 'No autenticat',
                    'message': 'UID d\'usuari no trobat'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Obtenir fitxers si n'hi ha
            files = request.FILES.getlist('files')
            
            # Crear l'experiència
            result, uploaded_result, error = self.controller.create_experience(
                refuge_id=refuge_id,
                creator_uid=creator_uid,
                comment=serializer.validated_data['comment'],
                files=files if files else None
            )
            
            if error:
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                if result is not None and uploaded_result is not None:
                    # Error al assignar media_keys a l'experiència però ja s'han pujat fitxers i creat l'experiència
                    serializer = ExperienceResponseSerializer(result.to_dict())
                    response = {
                        'experience': serializer.data,
                        'uploaded_files': uploaded_result['uploaded'] if uploaded_result else [],
                        'failed_files': uploaded_result['failed'] if uploaded_result else [],
                        'message': error
                    }
                    return Response(response, status=status.HTTP_201_CREATED)
                if result is not None:
                    # Error al pujar fitxers però experiència creada
                    serializer = ExperienceResponseSerializer(result.to_dict())
                    response = {
                        'experience': serializer.data,
                        'message': error
                    }
                    return Response(response, status=status.HTTP_201_CREATED)
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            serializer = ExperienceResponseSerializer(result.to_dict())
            response = {
                'experience': serializer.data,
                'uploaded_files': uploaded_result['uploaded'] if uploaded_result else [],
                'failed_files': uploaded_result['failed'] if uploaded_result else []
            }
            
            return Response(response, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creant experiència: {str(e)}")
            return Response(
                {'error': 'Error procesant la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExperienceDetailAPIView(APIView):
    """
    Gestiona una experiència específica.
    PATCH + DELETE /api/refuges/{refuge_id}/experiences/{experience_id}/
    """
    permission_classes = [IsAuthenticated, IsExperienceCreator]
    parser_classes = [MultiPartParser, FormParser]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = ExperienceController()
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Actualitza una experiència existent. "
            "Només el creador pot editar la seva experiència. "
            "Es pot modificar el comentari i afegir noves fotos."
            "\n\nRequereix autenticació i ser el creador de l'experiència."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'experience_id',
                openapi.IN_PATH,
                description="ID de l'experiència",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'comment',
                openapi.IN_FORM,
                description="Nou comentari de l'experiència (opcional)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'files',
                openapi.IN_FORM,
                description='Nous fitxers a pujar (opcional)',
                type=openapi.TYPE_FILE,
                required=False
            )
        ],
        responses={
            200: openapi.Response(
                description="Experiència actualitzada correctament",
                schema=ExperienceResponseSerializer
            ),
            400: openapi.Response(description="Dades invàlides"),
            401: openapi.Response(description="No autenticat"),
            403: openapi.Response(description="No tens permís per editar aquesta experiència"),
            404: openapi.Response(description="Experiència no trobada"),
            500: openapi.Response(description="Error intern del servidor")
        }
    )
    def patch(self, request, refuge_id, experience_id):
        """
        Actualitza una experiència (comentari i/o fotos).
        """
        try:
            # Validar dades
            serializer = ExperienceUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Dades invàlides', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir dades validades
            comment = serializer.validated_data.get('comment')
            files = request.FILES.getlist('files')
            
            # Actualitzar l'experiència
            result, upload_result, error = self.controller.update_experience(
                experience_id=experience_id,
                comment=comment,
                files=files if files else None
            )
            
            if error:
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                if upload_result is not None:
                    # Error en actualitzar però ja s'han pujat fitxers
                    serializer = ExperienceResponseSerializer(result.to_dict())
                    response = {
                        'uploaded_files': upload_result['uploaded'] if upload_result else [],
                        'failed_files': upload_result['failed'] if upload_result else [],
                        'message': error
                    }
                    return Response(response, status=status.HTTP_200_OK)
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            serializer = ExperienceResponseSerializer(result.to_dict())
            response = {
                'experience': serializer.data,
                'uploaded_files': upload_result['uploaded'] if upload_result else [],
                'failed_files': upload_result['failed'] if upload_result else [], 
            }
            
            return Response(response, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error actualitzant experiència: {str(e)}")
            return Response(
                {'error': 'Error procesant la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Elimina una experiència i tots els seus mitjans associats. "
            "Només el creador pot eliminar la seva experiència."
            "\n\nRequereix autenticació i ser el creador de l'experiència."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="ID del refugi",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'experience_id',
                openapi.IN_PATH,
                description="ID de l'experiència",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(description="Experiència eliminada correctament"),
            401: openapi.Response(description="No autenticat"),
            403: openapi.Response(description="No tens permís per eliminar aquesta experiència"),
            404: openapi.Response(description="Experiència no trobada"),
            500: openapi.Response(description="Error intern del servidor")
        }
    )
    def delete(self, request, refuge_id, experience_id):
        """
        Elimina una experiència i tots els seus mitjans.
        """
        try:
            success, error = self.controller.delete_experience(experience_id, refuge_id)
            
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
                    {'error': 'Error eliminant l\'experiència'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                'success': True,
                'message': 'Experiència eliminada correctament'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error eliminant experiència: {str(e)}")
            return Response(
                {'error': 'Error processat la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
