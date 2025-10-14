from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.http import Http404

from ..models import RefugiLliure
from ..serializers import RefugiLliureSerializer, RefugiLliureListSerializer
from ..controllers import RefugiLliureController


class RefugiLliurePagination(PageNumberPagination):
    """
    Paginació personalitzada per als refugis
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
def refugi_lliure_list(request):
    """
    API per llistar tots els refugis amb opcions de filtratge
    
    Query parameters:
    - regio: Filtrar per regió
    - available: Si és 'true', només refugis disponibles
    - tipus: Filtrar per tipus de refugi
    - page: Número de pàgina
    - page_size: Elements per pàgina
    """
    try:
        # Obtenir tots els refugis
        result = RefugiLliureController.get_all_refugis()
        
        if not result['success']:
            return Response(
                {
                    'error': result['message'],
                    'data': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        queryset = result['data']
        
        # Aplicar filtres opcionals
        regio = request.query_params.get('regio', None)
        if regio:
            queryset = queryset.filter(regio=regio)
        
        available = request.query_params.get('available', None)
        if available and available.lower() == 'true':
            queryset = queryset.filter(estat='obert', tancat=False)
        
        tipus = request.query_params.get('tipus', None)
        if tipus:
            queryset = queryset.filter(tipus=tipus)
        
        # Paginació
        paginator = RefugiLliurePagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = RefugiLliureListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        # Si no hi ha paginació
        serializer = RefugiLliureListSerializer(queryset, many=True)
        return Response(
            {
                'message': 'Refugis obtinguts correctament',
                'data': serializer.data,
                'count': queryset.count()
            },
            status=status.HTTP_200_OK
        )
        
    except DatabaseError as e:
        return Response(
            {
                'error': 'Error de base de dades',
                'message': 'Hi ha hagut un problema accedint a les dades',
                'details': str(e) if request.user.is_staff else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    except Exception as e:
        return Response(
            {
                'error': 'Error intern del servidor',
                'message': 'Hi ha hagut un error inesperat',
                'details': str(e) if request.user.is_staff else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def refugi_lliure_detail(request, refugi_id):
    """
    API per obtenir el detall d'un refugi específic
    
    Parameters:
    - refugi_id: ID del refugi a obtenir
    """
    try:
        # Validar que l'ID sigui un número vàlid
        try:
            refugi_id = int(refugi_id)
        except (ValueError, TypeError):
            return Response(
                {
                    'error': 'ID invàlid',
                    'message': 'L\'ID del refugi ha de ser un número vàlid'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtenir el refugi
        result = RefugiLliureController.get_refugi_by_id(refugi_id)
        
        if not result['success']:
            if result.get('error_code') == 'REFUGI_NOT_FOUND':
                return Response(
                    {
                        'error': 'Refugi no trobat',
                        'message': f'No existeix cap refugi amb l\'ID {refugi_id}'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {
                        'error': 'Error obtenint el refugi',
                        'message': result['message']
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Serialitzar el refugi
        serializer = RefugiLliureSerializer(result['data'])
        
        return Response(
            {
                'message': 'Refugi obtingut correctament',
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )
        
    except DatabaseError as e:
        return Response(
            {
                'error': 'Error de base de dades',
                'message': 'Hi ha hagut un problema accedint a les dades',
                'details': str(e) if request.user.is_staff else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    except Exception as e:
        return Response(
            {
                'error': 'Error intern del servidor',
                'message': 'Hi ha hagut un error inesperat',
                'details': str(e) if request.user.is_staff else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Classe per a gestió més avançada amb ViewSets (opcional)
from rest_framework import viewsets
from rest_framework.decorators import action


class RefugiLliureApiView(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet per a la gestió completa dels refugis (només lectura)
    
    Proporciona automàticament:
    - list(): GET /api/refugis/
    - retrieve(): GET /api/refugis/{id}/
    """
    
    queryset = RefugiLliure.objects.all()
    pagination_class = RefugiLliurePagination
    
    def get_serializer_class(self):
        """
        Retorna el serializer apropiat segons l'acció
        """
        if self.action == 'list':
            return RefugiLliureListSerializer
        return RefugiLliureSerializer
    
    def list(self, request, *args, **kwargs):
        """
        Llista tots els refugis amb filtres opcionals
        """
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {
                    'error': 'Error llistant els refugis',
                    'message': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Obtenir un refugi específic
        """
        try:
            return super().retrieve(request, *args, **kwargs)
        except Http404:
            return Response(
                {
                    'error': 'Refugi no trobat',
                    'message': f'No existeix cap refugi amb aquest ID'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'error': 'Error obtenint el refugi',
                    'message': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """
        Endpoint personalitzat per obtenir només refugis disponibles
        URL: /api/refugis/available/
        """
        try:
            result = RefugiLliureController.filter_available_refugis()
            
            if not result['success']:
                return Response(
                    {
                        'error': result['message']
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Aplicar paginació
            page = self.paginate_queryset(result['data'])
            if page is not None:
                serializer = RefugiLliureListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = RefugiLliureListSerializer(result['data'], many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {
                    'error': 'Error obtenint refugis disponibles',
                    'message': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_region(self, request):
        """
        Endpoint personalitzat per obtenir refugis per regió
        URL: /api/refugis/by_region/?regio=pirineus
        """
        try:
            regio = request.query_params.get('regio')
            if not regio:
                return Response(
                    {
                        'error': 'Paràmetre requerit',
                        'message': 'Cal especificar el paràmetre "regio"'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            result = RefugiLliureController.filter_refugis_by_region(regio)
            
            if not result['success']:
                return Response(
                    {
                        'error': result['message']
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Aplicar paginació
            page = self.paginate_queryset(result['data'])
            if page is not None:
                serializer = RefugiLliureListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = RefugiLliureListSerializer(result['data'], many=True)
            return Response({
                'message': f'Refugis de la regió {regio}',
                'data': serializer.data
            })
            
        except Exception as e:
            return Response(
                {
                    'error': 'Error filtrant per regió',
                    'message': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
def health_check(request):
    """
    Simple health check endpoint to verify the API is running.
    """
    return Response({
        'status': 'ok',
        'message': 'RefugisLliures Backend API is running'
    }, status=status.HTTP_200_OK)