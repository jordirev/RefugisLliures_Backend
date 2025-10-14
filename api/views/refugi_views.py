"""
Views per a la gestió de refugis utilitzant Firestore
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ..services import firestore_service

# Configurar logging
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Endpoint per comprovar l'estat de l'API"""
    try:
        # Comprova la connexió amb Firestore
        db = firestore_service.get_db()
        
        # Prova de connexió amb Firestore
        collections = list(db.collections())
        
        return Response({
            'status': 'healthy',
            'message': 'API is running correctly',
            'firebase': True,
            'firestore': True,
            'collections_count': len(collections)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Health check failed: {str(e)}')
        return Response({
            'status': 'unhealthy',
            'message': f'Error: {str(e)}',
            'firebase': False
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

@api_view(['GET'])
@permission_classes([AllowAny])
def refugi_list(request):
    """Llista tots els refugis des de Firestore"""
    try:
        db = firestore_service.get_db()
        
        # Obtenir paràmetres de consulta
        limit = request.GET.get('limit', 10)
        try:
            limit = int(limit)
            if limit > 100:  # Límit màxim per evitar sobrecàrrega
                limit = 100
        except ValueError:
            limit = 10
        
        # Consulta a Firestore
        refugis_ref = db.collection('data_refugis_lliures')
        docs = refugis_ref.limit(limit).stream()
        
        refugis = []
        for doc in docs:
            refugi_data = doc.to_dict()
            refugi_data['id'] = doc.id
            refugis.append(refugi_data)
        
        return Response({
            'count': len(refugis),
            'results': refugis
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Error getting refugis list: {str(e)}')
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def refugi_detail(request, refugi_id):
    """Obtenir els detalls d'un refugi específic"""
    try:
        db = firestore_service.get_db()
        
        # Consulta a Firestore
        doc_ref = db.collection('data_refugis_lliures').document(str(refugi_id))
        doc = doc_ref.get()
        
        if not doc.exists:
            return Response({
                'error': 'Refugi not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        refugi_data = doc.to_dict()
        refugi_data['id'] = doc.id
        
        return Response(refugi_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Error getting refugi detail: {str(e)}')
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def search_refugis(request):
    """Cerca refugis amb filtres"""
    try:
        db = firestore_service.get_db()
        
        # Obtenir paràmetres de cerca
        query_text = request.GET.get('q', '').strip()
        comarca = request.GET.get('comarca', '').strip()
        limit = request.GET.get('limit', 10)
        
        try:
            limit = int(limit)
            if limit > 100:
                limit = 100
        except ValueError:
            limit = 10
        
        # Construir consulta base
        refugis_ref = db.collection('data_refugis_lliures')
        
        # Aplicar filtres si es proporcionen
        if comarca:
            refugis_ref = refugis_ref.where('comarca', '==', comarca)
        
        # Obtenir documents
        docs = refugis_ref.limit(limit).stream()
        
        refugis = []
        for doc in docs:
            refugi_data = doc.to_dict()
            refugi_data['id'] = doc.id
            
            # Si hi ha text de cerca, filtrar pels noms
            if query_text:
                nom = refugi_data.get('nom', '').lower()
                if query_text.lower() in nom:
                    refugis.append(refugi_data)
            else:
                refugis.append(refugi_data)
        
        return Response({
            'count': len(refugis),
            'results': refugis,
            'filters': {
                'query': query_text,
                'comarca': comarca
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'Error searching refugis: {str(e)}')
        return Response({
            'error': f'Internal server error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)