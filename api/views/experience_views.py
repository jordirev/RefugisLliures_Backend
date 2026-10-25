"""
Views per a la gestió d'experiències de refugis
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.parsers import JSONParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..controllers.experience_controller import ExperienceController, ERROR_NOT_OWNER
from ..permissions import HasProfile, IsExperienceCreator, IsNotBlocked, is_firebase_admin, coded_error
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
    GET /api/experiences/?refuge_id={refuge_id}
    POST /api/experiences/
    """
    permission_classes = [IsAuthenticated, HasProfile]
    parser_classes = [JSONParser]

    def get_permissions(self):
        """GET: IsAuthenticated · POST: IsAuthenticated + IsNotBlocked"""
        if self.request.method == 'POST':
            return [IsAuthenticated(), HasProfile(), IsNotBlocked()]
        return [permission() for permission in self.permission_classes]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = ExperienceController()
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Obté la llista d'experiències d'un refugi ordenades per data de modificació descendent. "
            "\n\nRequereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_QUERY,
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
    def get(self, request):
        """
        Llista totes les experiències d'un refugi amb URLs prefirmades per a les imatges.
        """
        try:
            refuge_id = request.query_params.get('refuge_id')
            if not refuge_id:
                return Response(
                    {'error': 'El refuge_id és requerit. El path és /api/experiences/?refuge_id=refuge_id'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            experiences, error = self.controller.get_experiences_by_refuge(
                refuge_id,
                viewer_uid=getattr(request, 'user_uid', None),
                is_admin=is_firebase_admin(request)
            )
            
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
            "Accepta només JSON {refuge_id, comment}. Les fotos/vídeos es pugen després amb "
            "POST /api/media/upload-intents/ (target=experience) + confirm. "
            "\n\nRequereix autenticació."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['refuge_id', 'comment'],
            properties={
                'refuge_id': openapi.Schema(type=openapi.TYPE_STRING, description="ID del refugi"),
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description="Comentari de l'experiència"),
            },
            example={'refuge_id': 'refugi_colomers', 'comment': 'Refugi net i amb llenya.'}
        ),
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
    def post(self, request):
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
            
            # Crear l'experiència
            result, error = self.controller.create_experience(
                refuge_id=serializer.validated_data['refuge_id'],
                creator_uid=creator_uid,
                comment=serializer.validated_data['comment']
            )
            
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
            
            serializer = ExperienceResponseSerializer(result.to_dict())
            response = {'experience': serializer.data}
            
            return Response(response, status=status.HTTP_201_CREATED)
            
        except (ParseError, UnsupportedMediaType):
            raise  # DRF respon 400/415 (p. ex. multipart, ja no suportat)
        except Exception as e:
            logger.error(f"Error creant experiència: {str(e)}")
            return Response(
                {'error': 'Error procesant la petició'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExperienceDetailAPIView(APIView):
    """
    Gestiona una experiència específica.
    PATCH + DELETE /api/experiences/{experience_id}/
    La propietat es comprova al controller (403 not_owner; els admins hi tenen accés).
    """
    permission_classes = [IsAuthenticated, HasProfile, IsNotBlocked, IsExperienceCreator]
    parser_classes = [JSONParser]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = ExperienceController()
    
    @swagger_auto_schema(
        tags=['Refuge Experiences'],
        operation_description=(
            "Actualitza una experiència existent. "
            "Només el creador pot editar la seva experiència. "
            "Es pot modificar el comentari i afegir noves fotos.\n "
            "Permet afegir noves fotos a l'experiència existent."
            " Aquestes s'afegiran també al refugi de l'experiència."
            "\nPer eliminar fotos d'experiencies, utilitzar: DELETE /api/refuges/{id}/media/{key}/ amb la key del mitjà a eliminar."
            "\n\nRequereix autenticació i ser el creador de l'experiència."
        ),
        manual_parameters=[
            openapi.Parameter(
                'experience_id',
                openapi.IN_PATH,
                description="ID de l'experiència",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'comment': openapi.Schema(type=openapi.TYPE_STRING, description="Nou comentari (opcional)"),
            },
            example={'comment': 'Actualització: ja no hi ha llenya.'}
        ),
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
    def patch(self, request, experience_id):
        """
        Actualitza el comentari d'una experiència.
        Les fotos es pugen amb POST /api/media/upload-intents/ (target=experience) + confirm;
        per eliminar-ne, DELETE /api/refuges/{id}/media/{key}/.
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
            
            # Actualitzar l'experiència
            result, error = self.controller.update_experience(
                experience_id=experience_id,
                comment=comment,
                requester_uid=getattr(request, 'user_uid', None) or getattr(request.user, 'uid', None),
                is_admin=is_firebase_admin(request)
            )
            
            if error:
                if error == ERROR_NOT_OWNER:
                    return Response(coded_error('not_owner', "No ets el creador d'aquesta experiència"),
                                    status=status.HTTP_403_FORBIDDEN)
                if "not found" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            serializer = ExperienceResponseSerializer(result.to_dict())
            return Response({'experience': serializer.data}, status=status.HTTP_200_OK)
            
        except (ParseError, UnsupportedMediaType):
            raise  # DRF respon 400/415 (p. ex. multipart, ja no suportat)
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
    def delete(self, request, experience_id):
        """
        Elimina una experiència i tots els seus mitjans.
        """
        try:
            success, error = self.controller.delete_experience(
                experience_id,
                requester_uid=getattr(request, 'user_uid', None) or getattr(request.user, 'uid', None),
                is_admin=is_firebase_admin(request)
            )
            
            if error:
                if error == ERROR_NOT_OWNER:
                    return Response(coded_error('not_owner', "No ets el creador d'aquesta experiència"),
                                    status=status.HTTP_403_FORBIDDEN)
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
