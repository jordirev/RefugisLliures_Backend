"""
Views per a la gestió de visites a refugis
"""
import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from ..controllers.refuge_visit_controller import RefugeVisitController
from ..serializers.refuge_visit_serializer import (
    RefugeVisitListSerializer,
    CreateRefugeVisitSerializer,
    UpdateRefugeVisitSerializer
)
from ..permissions import IsSameUser

logger = logging.getLogger(__name__)


# ========== REFUGE VISITS ENDPOINT: /refuges/{id}/visits/ ==========

class RefugeVisitsAPIView(APIView):
    """
    Gestiona les visites d'un refugi específic
    GET: Obté totes les visites actuals i futures del refugi
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Obté totes les visites actuals i futures d'un refugi ordenades per data ascendent",
        responses={
            200: openapi.Response(
                description="Llista de visites obtinguda correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'result': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'date': openapi.Schema(type=openapi.TYPE_STRING, example="2025-07-18"),
                                    'total_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=12),
                                    'is_visitor': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
                                    'num_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=2)
                                }
                            )
                        )
                    }
                )
            ),
            401: "No autenticat",
            404: "Refugi no trobat",
            500: "Error intern del servidor"
        }
    )
    def get(self, request, refuge_id):
        """Obté totes les visites actuals i futures d'un refugi"""
        try:
            controller = RefugeVisitController()
            success, visits, error = controller.get_refuge_visits(refuge_id)
            
            if not success:
                if "no trobat" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obté l'UID del token
            uid = request.user.uid
            
            # Serialitza les visites passant el context
            serializer = RefugeVisitListSerializer(visits, many=True, context={'user_uid': uid})
            
            return Response({'result': serializer.data}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en GET refuge visits: {str(e)}")
            return Response(
                {'error': 'Error intern del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ========== USER VISITS ENDPOINT: /users/{uid}/visits/ ==========

class UserVisitsAPIView(APIView):
    """
    Gestiona les visites d'un usuari específic
    GET: Obté totes les visites de l'usuari
    """
    permission_classes = [IsAuthenticated, IsSameUser]
    
    @swagger_auto_schema(
        operation_description="Obté totes les visites d'un usuari ordenades per data descendent",
        responses={
            200: openapi.Response(
                description="Llista de visites obtinguda correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'result': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'date': openapi.Schema(type=openapi.TYPE_STRING, example="2025-07-18"),
                                    'refuge_id': openapi.Schema(type=openapi.TYPE_STRING, example="refuge123"),
                                    'total_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=12),
                                    'is_visitor': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
                                    'num_visitors': openapi.Schema(type=openapi.TYPE_INTEGER, example=2)
                                }
                            )
                        )
                    }
                )
            ),
            401: "No autenticat",
            403: "No tens permís per accedir a aquestes dades",
            500: "Error intern del servidor"
        }
    )
    def get(self, request, uid):
        """Obté totes les visites d'un usuari"""
        try:
            controller = RefugeVisitController()
            success, visits, error = controller.get_user_visits(uid)
            
            if not success:
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Serialitza les visites passant el context (les visites ja inclouen refuge_id)
            visits_list = [visit for visit_id, visit in visits]
            serializer = RefugeVisitListSerializer(visits_list, many=True, context={'user_uid': uid})
            
            return Response({'result': serializer.data}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error en GET user visits: {str(e)}")
            return Response(
                {'error': 'Error intern del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# ========== REFUGE VISITS DETAIL ENDPOINT: /refuges/{id}/visits/{date}/ ==========

class RefugeVisitDetailAPIView(APIView):
    """
    Gestiona una visita específica d'un refugi
    POST: Crea una nova visita o afegeix un visitant a una visita existent
    PATCH: Actualitza el nombre de visitants d'un usuari
    DELETE: Elimina un visitant d'una visita
    """
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        tags="refuge",
        operation_description="Crea una nova visita o afegeix un visitant a una visita existent",
        request_body=CreateRefugeVisitSerializer,
        responses={
            201: openapi.Response(
                description="Visita creada correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example="Visita creada correctament"),
                        'visit': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'date': openapi.Schema(type=openapi.TYPE_STRING),
                                'total_visitors': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'is_visitor': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'num_visitors': openapi.Schema(type=openapi.TYPE_INTEGER)
                            }
                        )
                    }
                )
            ),
            400: "Paràmetres invàlids o usuari ja registrat",
            401: "No autenticat",
            404: "Refugi no trobat",
            500: "Error intern del servidor"
        }
    )
    def post(self, request, refuge_id, visit_date):
        """Crea una nova visita o afegeix un visitant"""
        try:
            serializer = CreateRefugeVisitSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obté l'UID del token
            uid = request.user.uid
            num_visitors = serializer.validated_data['num_visitors']
            
            controller = RefugeVisitController()
            success, visit, error = controller.create_visit(refuge_id, visit_date, uid, num_visitors)
            
            if not success:
                if "no trobat" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Serialitza la visita passant el context
            serializer = RefugeVisitListSerializer(visit, context={'user_uid': uid})
            
            return Response(
                {
                    'message': 'Visita creada correctament',
                    'visit': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error en POST refuge visit: {str(e)}")
            return Response(
                {'error': 'Error intern del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Actualitza el nombre de visitants d'un usuari en una visita",
        request_body=UpdateRefugeVisitSerializer,
        responses={
            200: openapi.Response(
                description="Visita actualitzada correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example="Visita actualitzada correctament"),
                        'visit': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'date': openapi.Schema(type=openapi.TYPE_STRING),
                                'total_visitors': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'is_visitor': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                'num_visitors': openapi.Schema(type=openapi.TYPE_INTEGER)
                            }
                        )
                    }
                )
            ),
            400: "Paràmetres invàlids o usuari no registrat",
            401: "No autenticat",
            404: "Refugi o visita no trobats",
            500: "Error intern del servidor"
        }
    )
    def patch(self, request, refuge_id, visit_date):
        """Actualitza el nombre de visitants d'un usuari"""
        try:
            serializer = UpdateRefugeVisitSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {'error': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obté l'UID del token
            uid = request.user.uid
            num_visitors = serializer.validated_data['num_visitors']
            
            controller = RefugeVisitController()
            success, visit, error = controller.update_visit(refuge_id, visit_date, uid, num_visitors)
            
            if not success:
                if "no trobat" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Serialitza la visita passant el context
            serializer = RefugeVisitListSerializer(visit, context={'user_uid': uid})
            
            return Response(
                {
                    'message': 'Visita actualitzada correctament',
                    'visit': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error en PATCH refuge visit: {str(e)}")
            return Response(
                {'error': 'Error intern del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @swagger_auto_schema(
        operation_description="Elimina un visitant d'una visita",
        responses={
            200: openapi.Response(
                description="Visitant eliminat correctament",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example="Visitant eliminat correctament")
                    }
                )
            ),
            400: "Usuari no registrat a la visita",
            401: "No autenticat",
            404: "Refugi o visita no trobats",
            500: "Error intern del servidor"
        }
    )
    def delete(self, request, refuge_id, visit_date):
        """Elimina un visitant d'una visita"""
        try:
            # Obté l'UID del token
            uid = request.user.uid
            
            controller = RefugeVisitController()
            success, error = controller.delete_visit(refuge_id, visit_date, uid)
            
            if not success:
                if "no trobat" in error.lower():
                    return Response(
                        {'error': error},
                        status=status.HTTP_404_NOT_FOUND
                    )
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(
                {'message': 'Visitant eliminat correctament'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error en DELETE refuge visit: {str(e)}")
            return Response(
                {'error': 'Error intern del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
