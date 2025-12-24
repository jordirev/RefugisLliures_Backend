"""
Views per a la gestió de dubtes i respostes de refugis
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from ..controllers.doubt_controller import DoubtController
from ..permissions import IsDoubtCreator, IsAnswerCreator
from ..serializers.doubt_serializer import (
    DoubtSerializer,
    CreateDoubtSerializer,
    CreateAnswerSerializer,
    AnswerSerializer
)
from ..utils.swagger_examples import (
    EXAMPLE_DOUBT_LIST,
    EXAMPLE_DOUBT_DETAIL,
    EXAMPLE_ANSWER_DETAIL
)
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_DATA,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_404_DOUBT_NOT_FOUND,
    ERROR_404_ANSWER_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR
)

logger = logging.getLogger(__name__)


class DoubtListAPIView(APIView):
    """
    Gestiona la llista de dubtes d'un refugi.
    GET + POST /api/refuges/{refuge_id}/doubts/
    """
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DoubtController()
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Obté la llista de dubtes d'un refugi amb totes les seves respostes ordenades per data de creació descendent. "
            "Les respostes estan ordenades per data de creació ascendent."
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
                description="Llista de dubtes amb les seves respostes",
                examples={'application/json': EXAMPLE_DOUBT_LIST}
            ),
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_DOUBT_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request, refuge_id):
        """
        Llista tots els dubtes d'un refugi amb totes les seves respostes.
        """
        try:
            doubts, error = self.controller.get_doubts_by_refuge(refuge_id)
            
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
            
            # Serialitzar els dubtes
            doubts_data = [doubt.to_dict() for doubt in doubts]
            serializer = DoubtSerializer(data=doubts_data, many=True)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error llistant dubtes: {str(e)}")
            return Response(
                {'error': 'Error obtenint els dubtes'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Crea un nou dubte per a un refugi. "
            "El refuge_id s'extreu del path i el creator_uid del token d'autenticació."
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
        request_body=CreateDoubtSerializer,
        responses={
            201: openapi.Response(
                description="Dubte creat correctament",
                examples={'application/json': EXAMPLE_DOUBT_DETAIL}
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request, refuge_id):
        """
        Crea un nou dubte per a un refugi.
        """
        try:
            # Validar dades
            serializer = CreateDoubtSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Dades invàlides', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir UID de l'usuari autenticat
            creator_uid = getattr(request, 'user_uid', None)
            if not creator_uid:
                return Response(
                    {'error': 'No autenticat'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Crear dubte
            doubt, error = self.controller.create_doubt(
                refuge_id=refuge_id,
                creator_uid=creator_uid,
                message=serializer.validated_data['message']
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
            
            serializer = DoubtSerializer(doubt.to_dict())
            serializer.is_valid(raise_exception=True)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error creant dubte: {str(e)}")
            return Response(
                {'error': 'Error creant el dubte'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DoubtDetailAPIView(APIView):
    """
    Gestiona l'eliminació d'un dubte.
    DELETE /api/refuges/{refuge_id}/doubts/{doubt_id}/
    """
    permission_classes = [IsAuthenticated, IsDoubtCreator]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DoubtController()
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Elimina un dubte i totes les seves respostes. "
            "Només el creador del dubte o un administrador poden eliminar-lo."
            "\n\nRequereix autenticació i permís IsDoubtCreator."
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
                'doubt_id',
                openapi.IN_PATH,
                description="ID del dubte",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            204: openapi.Response(description="Dubte eliminat correctament"),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_DOUBT_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request, refuge_id, doubt_id):
        """
        Elimina un dubte i totes les seves respostes.
        """
        try:
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response(
                    {'error': 'No autenticat'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Eliminar dubte
            success, error = self.controller.delete_doubt(refuge_id, doubt_id, user_uid)
            
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
                    {'error': 'Error eliminant el dubte'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error eliminant dubte: {str(e)}")
            return Response(
                {'error': 'Error eliminant el dubte'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnswerListAPIView(APIView):
    """
    Gestiona la creació de respostes a un dubte.
    POST /api/refuges/{refuge_id}/doubts/{doubt_id}/answers/
    """
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DoubtController()
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Crea una nova resposta a un dubte. "
            "El creator_uid s'extreu del token d'autenticació. "
            "S'incrementa el comptador answers_count del dubte."
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
                'doubt_id',
                openapi.IN_PATH,
                description="ID del dubte",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        request_body=CreateAnswerSerializer,
        responses={
            201: openapi.Response(
                description="Resposta creada correctament",
                examples={'application/json': EXAMPLE_ANSWER_DETAIL}
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_DOUBT_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request, refuge_id, doubt_id):
        """
        Crea una nova resposta a un dubte.
        """
        try:
            # Validar dades
            serializer = CreateAnswerSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Dades invàlides', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir UID de l'usuari autenticat
            creator_uid = getattr(request, 'user_uid', None)
            if not creator_uid:
                return Response(
                    {'error': 'No autenticat'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Crear resposta
            answer, error = self.controller.create_answer(
                refuge_id=refuge_id,
                doubt_id=doubt_id,
                creator_uid=creator_uid,
                message=serializer.validated_data['message'],
                parent_answer_id=None
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
            
            serializer = AnswerSerializer(answer.to_dict())
            serializer.is_valid(raise_exception=True)
            return Response(
                answer.to_dict(),
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error creant resposta: {str(e)}")
            return Response(
                {'error': 'Error creant la resposta'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnswerReplyAPIView(APIView):
    """
    Gestiona la creació de respostes a una resposta i l'eliminació de respostes.
    POST /api/refuges/{refuge_id}/doubts/{doubt_id}/answers/{answer_id}/
    DELETE /api/refuges/{refuge_id}/doubts/{doubt_id}/answers/{answer_id}/
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = DoubtController()
    
    def get_permissions(self):
        """
        Assigna permisos segons el mètode HTTP
        """
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), IsAnswerCreator()]
        return [IsAuthenticated()]
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Crea una nova resposta a una resposta d'un dubte. "
            "El creator_uid s'extreu del token d'autenticació. "
            "El parent_answer_id és l'ID de l'answer del path. "
            "S'incrementa el comptador answers_count del dubte."
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
                'doubt_id',
                openapi.IN_PATH,
                description="ID del dubte",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'answer_id',
                openapi.IN_PATH,
                description="ID de la resposta pare",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        request_body=CreateAnswerSerializer,
        responses={
            201: openapi.Response(
                description="Resposta creada correctament",
                examples={'application/json': EXAMPLE_ANSWER_DETAIL}
            ),
            400: ERROR_400_INVALID_DATA,
            401: ERROR_401_UNAUTHORIZED,
            404: ERROR_404_DOUBT_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def post(self, request, refuge_id, doubt_id, answer_id):
        """
        Crea una nova resposta a una resposta d'un dubte.
        """
        try:
            # Validar dades
            serializer = CreateAnswerSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': 'Dades invàlides', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtenir UID de l'usuari autenticat
            creator_uid = getattr(request, 'user_uid', None)
            if not creator_uid:
                return Response(
                    {'error': 'No autenticat'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Crear resposta amb parent_answer_id
            answer, error = self.controller.create_answer(
                refuge_id=refuge_id,
                doubt_id=doubt_id,
                creator_uid=creator_uid,
                message=serializer.validated_data['message'],
                parent_answer_id=answer_id
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
            
            serializer = AnswerSerializer(answer.to_dict())
            serializer.is_valid(raise_exception=True)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error creant resposta: {str(e)}")
            return Response(
                {'error': 'Error creant la resposta'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        tags=['Refuge Doubts'],
        operation_description=(
            "Elimina una resposta. "
            "Es decrementa el comptador answers_count del dubte. "
            "No s'eliminen les respostes filles (parent_answer_id apunta a aquesta). "
            "Només el creador de la resposta o un administrador poden eliminar-la."
            "\n\nRequereix autenticació i permís IsAnswerCreator."
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
                'doubt_id',
                openapi.IN_PATH,
                description="ID del dubte",
                type=openapi.TYPE_STRING,
                required=True
            ),
            openapi.Parameter(
                'answer_id',
                openapi.IN_PATH,
                description="ID de la resposta",
                type=openapi.TYPE_STRING,
                required=True
            ),
        ],
        responses={
            204: openapi.Response(description="Resposta eliminada correctament"),
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_ANSWER_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def delete(self, request, refuge_id, doubt_id, answer_id):
        """
        Elimina una resposta.
        """
        try:
            # Obtenir UID de l'usuari autenticat
            user_uid = getattr(request, 'user_uid', None)
            if not user_uid:
                return Response(
                    {'error': 'No autenticat'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Eliminar resposta
            success, error = self.controller.delete_answer(
                refuge_id, doubt_id, answer_id, user_uid
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
            
            if not success:
                return Response(
                    {'error': 'Error eliminant la resposta'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error eliminant resposta: {str(e)}")
            return Response(
                {'error': 'Error eliminant la resposta'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
