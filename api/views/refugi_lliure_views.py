"""
Views per a la gestió de refugis amb endpoints REST estàndard
"""
import logging
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.refugi_lliure_controller import RefugiLliureController
from ..controllers.renovation_controller import RenovationController
from ..serializers.refugi_lliure_serializer import (
    RefugiSerializer, 
    RefugiSearchResponseSerializer,
    RefugiSearchFiltersSerializer
)
from ..serializers.renovation_serializer import RenovationSerializer
from ..utils.swagger_examples import (
    EXAMPLE_REFUGI_SEARCH_RESPONSE,
    EXAMPLE_REFUGI_COLOMERS_DETAILED,
    EXAMPLE_RENOVATIONS_LIST,
)
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_PARAMS,
    ERROR_401_UNAUTHORIZED,
    ERROR_404_REFUGI_NOT_FOUND,
    ERROR_500_INTERNAL_ERROR,
)



# Configurar logging
logger = logging.getLogger(__name__)

# ========== COLLECTION ENDPOINT: /refugis/ ==========

class RefugiLliureCollectionAPIView(APIView):
    """
    Gestiona la col·lecció de refugis amb cerca i filtres opcionals:
    - GET: Obtenir refugis amb filtres opcionals (no requereix autenticació)
      * Sense filtres: retorna totes les coordenades dels refugis
      * Amb filtres: cerca i retorna refugis que compleixen els criteris
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        security=[],
        operation_description=(
            "Obté una llista de refugis amb suport per filtres opcionals. "
            "\n- Quan no s'especifiquen filtres, retorna totes les coordenades dels refugis. "
            "\n- Quan s'utilitzen filtres, retorna els refugis que compleixen els criteris especificats. "
            "\n\nAquest endpoint no requereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'name',
                openapi.IN_QUERY,
                description="Filtre per nom del refugi (cerca parcial, case-insensitive)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'type',
                openapi.IN_QUERY,
                description="Filtre per tipus de refugi",
                type=openapi.TYPE_STRING,
                enum=['non gardé', 'fermée', 'cabane ouverte mais ocupee par le berger l ete', 'orri'],
                required=False
            ),
            openapi.Parameter(
                'condition',
                openapi.IN_QUERY,
                description="Filtre per tipus de refugi",
                type=openapi.TYPE_NUMBER,
                enum=[0, 1, 2],
                required=False
            ),
            openapi.Parameter(
                'altitude_min',
                openapi.IN_QUERY,
                description="Altitud mínima en metres",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'altitude_max',
                openapi.IN_QUERY,
                description="Altitud màxima en metres",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'places_min',
                openapi.IN_QUERY,
                description="Capacitat mínima de places",
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'places_max',
                openapi.IN_QUERY,
                description="Capacitat màxima de places",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={
            200: openapi.Response(
                description='Llista de refugis o coordenades',
                schema=RefugiSearchResponseSerializer,
                examples={
                    'application/json': EXAMPLE_REFUGI_SEARCH_RESPONSE
                }
            ),
            400: ERROR_400_INVALID_PARAMS,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request):
        """Obtenir refugis amb filtres opcionals"""
        try:
            # Validar paràmetres d'entrada
            filters_serializer = RefugiSearchFiltersSerializer(data=request.GET)
            if not filters_serializer.is_valid():
                return Response({
                    'error': 'Invalid query parameters',
                    'details': filters_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            controller = RefugiLliureController()
            search_result, error = controller.search_refugis(filters_serializer.validated_data)
            
            if error:
                return Response({
                    'error': error
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar la resposta
            response_serializer = RefugiSearchResponseSerializer(data=search_result)
            if response_serializer.is_valid():
                return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
            else:
                return Response(search_result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error processing refugis request: {str(e)}')
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ========== ITEM ENDPOINT: /refugis/{id}/ ==========

class RefugiLliureDetailAPIView(APIView):
    """
    Gestiona operacions sobre un refugi específic:
    - GET: Obtenir detalls d'un refugi per ID (no requereix autenticació)
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        security=[],
        operation_description=(
            "Obté els detalls complets d'un refugi específic per ID. "
            "\nRetorna informació completa del refugi incloent nom, descripció, coordenades, "
            "dificultats, rutes properes i altres detalls. "
            "\nAquest endpoint no requereix autenticació."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="Identificador únic del refugi",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Detalls del refugi',
                schema=RefugiSerializer,
                examples={
                    'application/json': EXAMPLE_REFUGI_COLOMERS_DETAILED
                }
            ),
            404: ERROR_404_REFUGI_NOT_FOUND,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request, refuge_id):
        """Obtenir detalls d'un refugi per ID"""
        try:
            controller = RefugiLliureController()
            refugi, error = controller.get_refugi_by_id(refuge_id)
            
            if error:
                if "not found" in error.lower():
                    return Response({
                        'error': error
                    }, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({
                        'error': error
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar el refugi
            serializer = RefugiSerializer(refugi.to_dict())
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error processing refugis request: {str(e)}')
            return Response({
                'error': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== REFUGE RENOVATIONS ENDPOINT: /refuges/{id}/renovations/ ==========

class RefugeRenovationsAPIView(APIView):
    """
    Gestiona operacions sobre les renovations d'un refugi:
    - GET: Obtenir totes les renovations actives d'un refugi (requereix autenticació)
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description=(
            "Obté totes les renovations d'un refugi específic. "
            "Requereix autenticació amb token JWT de Firebase."
        ),
        manual_parameters=[
            openapi.Parameter(
                'refuge_id',
                openapi.IN_PATH,
                description="Identificador únic del refugi",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description='Renovations actives del refugi',
                schema=RenovationSerializer(many=True),
                examples={
                    'application/json': EXAMPLE_RENOVATIONS_LIST
                }
            ),
            401: ERROR_401_UNAUTHORIZED,
            500: ERROR_500_INTERNAL_ERROR
        }
    )
    def get(self, request, refuge_id):
        """Obtenir renovations d'un refugi"""
        try:
            controller = RenovationController()
            success, renovations, error_message = controller.get_renovations_by_refuge(refuge_id)
            
            if not success:
                return Response({
                    'error': error_message
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Serialitzar les renovations
            serializer = RenovationSerializer([r.to_dict() for r in renovations], many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Error getting refuge renovations: {str(e)}')
            return Response({
                'error': ERROR_500_INTERNAL_ERROR
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)