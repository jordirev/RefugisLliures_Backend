from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def health_check(request):
    """
    Simple health check endpoint to verify the API is running.
    """
    return Response({
        'status': 'ok',
        'message': 'RefugisLliures Backend API is running'
    }, status=status.HTTP_200_OK)

