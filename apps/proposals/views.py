"""
Vistes de `proposals`: crear, llistar, aprovar i rebutjar propostes de canvi de refugis.

Les vistes només validen l'entrada, criden els `selectors` (lectures) o els `services` (escriptures) com a atributs de
mòdul i serialitzen. El context de RLS el fixa el hook de `api/rls_hook.py`.

Permisos (decisió del PO, 26/10): crear exigeix `IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed` (escriptura de
contingut); llistar tot, aprovar i rebutjar, `IsAuthenticated, HasProfile, IsFirebaseAdmin` (un admin pot aprovar la seva);
`my-refuges-proposals`, només `IsAuthenticated, HasProfile`. Ordre: permisos -> validació (400) -> existència (404) ->
estat (409).
"""
import logging

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasProfile, IsAgeConfirmed, IsFirebaseAdmin, IsNotBlocked
from api.utils.swagger_error_responses import (
    ERROR_400_INVALID_PARAMS,
    ERROR_401_UNAUTHORIZED,
    ERROR_403_FORBIDDEN,
    ERROR_404_PROPOSAL_NOT_FOUND,
    ERROR_409_PROPOSAL_ALREADY_REVIEWED,
    ERROR_500_INTERNAL_ERROR,
)
from api.utils.swagger_examples import (
    EXAMPLE_REFUGE_PROPOSAL_RESPONSE,
    EXAMPLE_REFUGE_PROPOSALS_LIST,
)
from apps.core.errors import server_error

from . import selectors, services
from .models import Status
from .serializers import CreateProposalSerializer, ProposalSerializer, RejectProposalSerializer

logger = logging.getLogger(__name__)

ERR_LIST = 'Error de base de dades en obtenir les propostes'
ERR_CREATE = 'Error de base de dades en crear la proposta'
ERR_APPROVE = 'Error de base de dades en aprovar la proposta'
ERR_REJECT = 'Error de base de dades en rebutjar la proposta'
ERR_R2_DELETE = 'Error en esborrar els fitxers del refugi a R2'

READ_PERMISSIONS = [IsAuthenticated, HasProfile]
WRITE_PERMISSIONS = [IsAuthenticated, HasProfile, IsNotBlocked, IsAgeConfirmed]
ADMIN_PERMISSIONS = [IsAuthenticated, HasProfile, IsFirebaseAdmin]

INVALID_STATUS = "Invalid status filter: {}. Must be 'pending', 'approved', or 'rejected'"


def _status_filter(request):
    """`(status, error_response)`: el filtre `status` (buit = sense filtre) o la resposta 400 si no és vàlid."""
    value = request.query_params.get('status')
    if value and value not in Status.values:
        return None, Response({'error': INVALID_STATUS.format(value)}, status=status.HTTP_400_BAD_REQUEST)
    return value or None, None


def _review_error(exc):
    """404/409 de les excepcions de revisió (`approve` i `reject`); `None` si no és una d'elles."""
    if isinstance(exc, services.ProposalNotFound):
        return Response({'error': 'Proposal not found'}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, services.ProposalAlreadyReviewed):
        return Response({'error': f'Proposal is already {exc.status}'}, status=status.HTTP_409_CONFLICT)
    return None


def _list_response(request, **filters):
    status_filter, error = _status_filter(request)
    if error:
        return error
    try:
        proposals = selectors.list_proposals(status=status_filter, **filters)
    except Exception as exc:
        return server_error(ERR_LIST, exc, logger=logger)
    return Response(ProposalSerializer(proposals, many=True).data)


ERROR_409_POSSIBLE_DUPLICATES = openapi.Response(
    description='Hi ha refugis a menys de 500 m amb un nom semblant (la proposta no es desa)',
    examples={'application/json': {
        'error': 'possible_duplicates', 'code': 'possible_duplicates',
        'message': 'Hi ha refugis a menys de 500 m amb un nom semblant. Comprova que no sigui el mateix.',
        'possible_duplicates': [{'id': '0197b1c2-0000-7000-8000-000000000001', 'name': 'Refugi de Colomers',
                                 'distance_m': 120}]}})
ERROR_409_APPROVE = openapi.Response(
    description='La proposta ja ha estat revisada, o un enllaç del payload ja pertany a un altre refugi (cap canvi)',
    examples={'application/json': {'error': 'Proposal is already approved'}})

_status_param = openapi.Parameter('status', openapi.IN_QUERY, description='Filtre per estat de la proposta',
                                  type=openapi.TYPE_STRING, enum=Status.values, required=False)


class ProposalCollectionAPIView(APIView):
    """POST /api/refuges-proposals/ (crear; autenticat) i GET (llistar totes; només admins)."""

    parser_classes = [JSONParser]

    def get_permissions(self):
        classes = ADMIN_PERMISSIONS if self.request.method == 'GET' else WRITE_PERMISSIONS
        return [permission() for permission in classes]

    @swagger_auto_schema(
        operation_description=(
            "Crea una proposta de refugi. Requereix autenticació, perfil, usuari no bloquejat i edat confirmada "
            "(403 `profile_required`, `user_blocked` o `age_not_confirmed`). 400 si falla la validació o si el refugi "
            "d'un `update`/`delete` no existeix.\n\n"
            "**Tipus d'accions:**\n"
            "- `create`: crear un refugi nou (`payload`, sense `refuge_id`). Si hi ha un refugi a menys de 500 m amb un "
            "nom semblant, 409 `possible_duplicates` amb la llista (`id`, `name`, `distance_m`).\n"
            "- `update`: canviar un refugi (`refuge_id` i `payload` amb només els camps canviats; `null` el buida)\n"
            "- `delete`: esborrar un refugi (`refuge_id`, sense `payload`)\n\n"
            "La proposta queda `pending` fins que un admin l'aprova o la rebutja."),
        request_body=CreateProposalSerializer,
        responses={201: openapi.Response(description='Proposta creada', schema=ProposalSerializer,
                                         examples={'application/json': EXAMPLE_REFUGE_PROPOSAL_RESPONSE}),
                   400: ERROR_400_INVALID_PARAMS, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   409: ERROR_409_POSSIBLE_DUPLICATES,
                   500: ERROR_500_INTERNAL_ERROR},
        tags=['Refuge Proposals'],
    )
    def post(self, request):
        serializer = CreateProposalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Invalid data', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            proposal = services.create_proposal(
                creator_uid=request.user_uid, action=data['action'], refuge_id=data.get('refuge_id'),
                payload=data.get('payload'), comment=data.get('comment'))
        except services.RefugeNotFound:
            return Response({'error': 'Refuge does not exists'}, status=status.HTTP_400_BAD_REQUEST)
        except services.PossibleDuplicates as exc:
            return Response({
                'error': 'possible_duplicates', 'code': 'possible_duplicates',
                'message': 'Hi ha refugis a menys de 500 m amb un nom semblant. Comprova que no sigui el mateix.',
                'possible_duplicates': exc.duplicates}, status=status.HTTP_409_CONFLICT)
        except Exception as exc:
            return server_error(ERR_CREATE, exc, logger=logger)
        return Response(ProposalSerializer(proposal).data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        operation_description=("Llista totes les propostes (només admins), per data de creació descendent. Filtres "
                               "combinables per `status` i `refuge-id`."),
        manual_parameters=[_status_param,
                           openapi.Parameter('refuge-id', openapi.IN_QUERY, description='Filtre per ID del refugi',
                                             type=openapi.TYPE_STRING, required=False)],
        responses={200: openapi.Response(description='Llista de propostes', schema=ProposalSerializer(many=True),
                                         examples={'application/json': EXAMPLE_REFUGE_PROPOSALS_LIST}),
                   400: ERROR_400_INVALID_PARAMS, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   500: ERROR_500_INTERNAL_ERROR},
        tags=['Refuge Proposals'],
    )
    def get(self, request):
        return _list_response(request, refuge_id=request.query_params.get('refuge-id') or None)


class MyProposalCollectionAPIView(APIView):
    """GET /api/my-refuges-proposals/: les propostes de qui fa la petició (també un admin)."""

    permission_classes = READ_PERMISSIONS

    @swagger_auto_schema(
        operation_description="Llista les propostes pròpies, per data de creació descendent. Filtre per `status`.",
        manual_parameters=[_status_param],
        responses={200: openapi.Response(description='Llista de propostes', schema=ProposalSerializer(many=True),
                                         examples={'application/json': EXAMPLE_REFUGE_PROPOSALS_LIST}),
                   400: ERROR_400_INVALID_PARAMS, 401: ERROR_401_UNAUTHORIZED, 500: ERROR_500_INTERNAL_ERROR},
        tags=['Refuge Proposals'],
    )
    def get(self, request):
        return _list_response(request, creator_uid=request.user_uid)


class ProposalApproveAPIView(APIView):
    """POST /api/refuges-proposals/{id}/approve/ (només admins)."""

    permission_classes = ADMIN_PERMISSIONS

    @swagger_auto_schema(
        operation_description=(
            "Aprova la proposta i n'aplica l'acció en una transacció (`create` crea el refugi, `update` el canvia, "
            "`delete` l'esborra amb tot el que en penja i els seus fitxers d'R2). Només admins (403 si no). 404 si la "
            "proposta no existeix; 409 si ja està aprovada o rebutjada, o si un enllaç del payload ja és d'un altre "
            "refugi (la proposta continua pendent). 500 si R2 falla en un `delete` (tot es desfà)."),
        responses={200: openapi.Response(description='Proposta aprovada',
                                         examples={'application/json': {'message': 'Proposal approved successfully'}}),
                   401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN, 404: ERROR_404_PROPOSAL_NOT_FOUND,
                   409: ERROR_409_APPROVE, 500: ERROR_500_INTERNAL_ERROR},
        tags=['Refuge Proposals'],
    )
    def post(self, request, proposal_id):
        try:
            services.approve_proposal(proposal_id=proposal_id, reviewer_uid=request.user_uid)
        except services.LinkAlreadyUsed:
            return Response({'error': 'A link of the proposal already belongs to another refuge'},
                            status=status.HTTP_409_CONFLICT)
        except services.MediaStorageError as exc:
            return server_error(ERR_R2_DELETE, exc, logger=logger)
        except (services.ProposalNotFound, services.ProposalAlreadyReviewed) as exc:
            return _review_error(exc)
        except Exception as exc:
            return server_error(ERR_APPROVE, exc, logger=logger)
        return Response({'message': 'Proposal approved successfully'})


class ProposalRejectAPIView(APIView):
    """POST /api/refuges-proposals/{id}/reject/ (només admins)."""

    permission_classes = ADMIN_PERMISSIONS
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_description=("Rebutja la proposta (no s'aplica res). Només admins. El motiu és opcional (màxim 2000 "
                               "caràcters). 404 si no existeix; 409 si ja està aprovada o rebutjada."),
        request_body=RejectProposalSerializer,
        responses={200: openapi.Response(description='Proposta rebutjada',
                                         examples={'application/json': {'message': 'Proposal rejected successfully'}}),
                   400: ERROR_400_INVALID_PARAMS, 401: ERROR_401_UNAUTHORIZED, 403: ERROR_403_FORBIDDEN,
                   404: ERROR_404_PROPOSAL_NOT_FOUND, 409: ERROR_409_PROPOSAL_ALREADY_REVIEWED,
                   500: ERROR_500_INTERNAL_ERROR},
        tags=['Refuge Proposals'],
    )
    def post(self, request, proposal_id):
        serializer = RejectProposalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Invalid data', 'details': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        try:
            services.reject_proposal(proposal_id=proposal_id, reviewer_uid=request.user_uid,
                                     reason=serializer.validated_data.get('reason'))
        except (services.ProposalNotFound, services.ProposalAlreadyReviewed) as exc:
            return _review_error(exc)
        except Exception as exc:
            return server_error(ERR_REJECT, exc, logger=logger)
        return Response({'message': 'Proposal rejected successfully'})
