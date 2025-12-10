"""
Views per a la gestió de propostes de refugis amb endpoints REST
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.refuge_proposal_controller import RefugeProposalController
from ..serializers.refuge_proposal_serializer import (
    RefugeProposalCreateSerializer,
    RefugeProposalResponseSerializer,
    RefugeProposalRejectSerializer
)
from ..permissions import IsFirebaseAdmin
from ..utils.swagger_examples import (
    EXAMPLE_REFUGE_PROPOSAL_CREATE,
    EXAMPLE_REFUGE_PROPOSAL_UPDATE,
    EXAMPLE_REFUGE_PROPOSAL_DELETE,
    EXAMPLE_REFUGE_PROPOSAL_RESPONSE,
    EXAMPLE_REFUGE_PROPOSALS_LIST
)
from ..utils.swagger_error_responses import (
    ERROR_400_INVALID_PARAMS,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_404_PROPOSAL_NOT_FOUND,
    ERROR_409_PROPOSAL_ALREADY_REVIEWED,
    ERROR_500_INTERNAL_ERROR
)

logger = logging.getLogger(__name__)


# ========== COLLECTION ENDPOINT: /refuges-proposals/ ==========

class RefugeProposalCollectionAPIView(APIView):
    """
    Gestiona la col·lecció de propostes de refugis:
    - POST: Crear una nova proposta (requereix autenticació)
    - GET: Llistar totes les propostes amb filtre per status (només admins)
    """
    
    def get_permissions(self):
        """Permisos diferents per GET (admin) i POST (autenticat)"""
        if self.request.method == 'GET':
            return [IsFirebaseAdmin()]
        return [IsAuthenticated()]
    
    @swagger_auto_schema(
        operation_description=(
            "Crea una nova proposta de refugi. Requereix autenticació.\n\n"
            "**Tipus d'accions:**\n"
            "- `create`: Crear un nou refugi (no requereix `refuge_id`, sí `payload`)\n"
            "- `update`: Actualitzar un refugi existent (requereix `refuge_id` i `payload`)\n"
            "- `delete`: Eliminar un refugi (requereix `refuge_id`, no `payload`)\n\n"
            "La proposta quedarà en estat `pending` fins que un administrador l'aprovi o rebutgi."
        ),
        request_body=RefugeProposalCreateSerializer,
        responses={
            201: openapi.Response(
                description="Proposta creada correctament",
                schema=RefugeProposalResponseSerializer,
                examples={
                    'application/json': EXAMPLE_REFUGE_PROPOSAL_RESPONSE
                }
            ),
            400: ERROR_400_INVALID_PARAMS,
            401: ERROR_401_UNAUTHORIZED,
            500: ERROR_500_INTERNAL_ERROR
        },
        tags=['Refuge Proposals']
    )
    def post(self, request):
        """Crear una nova proposta de refugi"""
        # Validar les dades
        serializer = RefugeProposalCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtenir l'UID de l'usuari autenticat
        creator_uid = getattr(request.user, 'uid', None)
        if not creator_uid:
            return Response(
                {'error': 'User UID not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Crear la proposta
        controller = RefugeProposalController()
        proposal, error = controller.create_proposal(serializer.validated_data, creator_uid)
        
        if error:
            return Response(
                {'error': error},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Serialitzar la resposta
        response_serializer = RefugeProposalResponseSerializer(proposal.to_dict())
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @swagger_auto_schema(
        operation_description=(
            "Llista totes les propostes de refugis. Només accessible per administradors.\n\n"
            "Es pot filtrar per status utilitzant el paràmetre `status`."
        ),
        manual_parameters=[
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description="Filtre per status de la proposta",
                type=openapi.TYPE_STRING,
                enum=['pending', 'approved', 'rejected'],
                required=False
            )
        ],
        responses={
            200: openapi.Response(
                description="Llista de propostes",
                schema=RefugeProposalResponseSerializer(many=True),
                examples={
                    'application/json': EXAMPLE_REFUGE_PROPOSALS_LIST
                }
            ),
            400: ERROR_400_INVALID_PARAMS,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            500: ERROR_500_INTERNAL_ERROR
        },
        tags=['Refuge Proposals']
    )
    def get(self, request):
        """Llistar totes les propostes (només admins)"""
        # Obtenir el filtre de status (opcional)
        status_filter = request.query_params.get('status', None)
        
        # Llistar les propostes
        controller = RefugeProposalController()
        proposals, error = controller.list_proposals(status_filter)
        
        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST if 'Invalid status' in error else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Serialitzar la resposta
        proposals_data = [proposal.to_dict() for proposal in proposals]
        response_serializer = RefugeProposalResponseSerializer(proposals_data, many=True)
        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK
        )


# ========== APPROVE ENDPOINT: /refuges-proposals/{id}/approve/ ==========

class RefugeProposalApproveAPIView(APIView):
    """
    Aprova una proposta de refugi (només admins)
    """
    permission_classes = [IsFirebaseAdmin]
    
    @swagger_auto_schema(
        operation_description=(
            "Aprova una proposta de refugi i executa l'acció corresponent. Només accessible per administradors.\n\n"
            "**Accions que s'executaran:**\n"
            "- `create`: Es crearà un nou refugi amb les dades del `payload`\n"
            "- `update`: S'actualitzaran les dades del refugi especificat\n"
            "- `delete`: S'eliminarà el refugi especificat\n\n"
            "Després d'aprovar, la proposta canviarà a estat `approved` i no es podrà modificar."
        ),
        responses={
            200: openapi.Response(
                description="Proposta aprovada correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                ),
                examples={
                    'application/json': {'message': 'Proposal approved successfully'}
                }
            ),
            400: ERROR_400_INVALID_PARAMS,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_PROPOSAL_NOT_FOUND,
            409: ERROR_409_PROPOSAL_ALREADY_REVIEWED,
            500: ERROR_500_INTERNAL_ERROR
        },
        tags=['Refuge Proposals']
    )
    def post(self, request, id):
        """Aprovar una proposta"""
        # Obtenir l'UID de l'admin
        reviewer_uid = getattr(request.user, 'uid', None)
        if not reviewer_uid:
            return Response(
                {'error': 'User UID not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Aprovar la proposta
        controller = RefugeProposalController()
        success, error = controller.approve_proposal(id, reviewer_uid)
        
        if not success:
            # Determinar el codi d'estat HTTP segons l'error
            if 'not found' in error.lower():
                status_code = status.HTTP_404_NOT_FOUND
            elif 'already' in error.lower():
                status_code = status.HTTP_409_CONFLICT
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            return Response(
                {'error': error},
                status=status_code
            )
        
        return Response(
            {'message': 'Proposal approved successfully'},
            status=status.HTTP_200_OK
        )


# ========== REJECT ENDPOINT: /refuges-proposals/{id}/reject/ ==========

class RefugeProposalRejectAPIView(APIView):
    """
    Rebutja una proposta de refugi (només admins)
    """
    permission_classes = [IsFirebaseAdmin]
    
    @swagger_auto_schema(
        operation_description=(
            "Rebutja una proposta de refugi. Només accessible per administradors.\n\n"
            "No s'executarà cap acció sobre els refugis. La proposta canviarà a estat `rejected` "
            "i opcionalment es pot proporcionar una raó del rebuig."
        ),
        request_body=RefugeProposalRejectSerializer,
        responses={
            200: openapi.Response(
                description="Proposta rebutjada correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                ),
                examples={
                    'application/json': {'message': 'Proposal rejected successfully'}
                }
            ),
            400: ERROR_400_INVALID_PARAMS,
            401: ERROR_401_UNAUTHORIZED,
            403: ERROR_403_FORBIDDEN,
            404: ERROR_404_PROPOSAL_NOT_FOUND,
            409: ERROR_409_PROPOSAL_ALREADY_REVIEWED,
            500: ERROR_500_INTERNAL_ERROR
        },
        tags=['Refuge Proposals']
    )
    def post(self, request, id):
        """Rebutjar una proposta"""
        # Validar les dades (opcional: reason)
        serializer = RefugeProposalRejectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtenir l'UID de l'admin
        reviewer_uid = getattr(request.user, 'uid', None)
        if not reviewer_uid:
            return Response(
                {'error': 'User UID not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Rebutjar la proposta
        reason = serializer.validated_data.get('reason')
        controller = RefugeProposalController()
        success, error = controller.reject_proposal(id, reviewer_uid, reason)
        
        if not success:
            # Determinar el codi d'estat HTTP segons l'error
            if 'not found' in error.lower():
                status_code = status.HTTP_404_NOT_FOUND
            elif 'already' in error.lower():
                status_code = status.HTTP_409_CONFLICT
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            return Response(
                {'error': error},
                status=status_code
            )
        
        return Response(
            {'message': 'Proposal rejected successfully'},
            status=status.HTTP_200_OK
        )
