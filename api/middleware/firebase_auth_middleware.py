"""
Middleware per verificar tokens JWT de Firebase Auth
"""
import logging
from django.utils.deprecation import MiddlewareMixin
from firebase_admin import auth
from rest_framework import status
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class FirebaseAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware per validar tokens JWT de Firebase Auth.
    Verifica el token del header Authorization i afegeix la informació de l'usuari a request.user
    """
    
    # Endpoints que no requereixen autenticació
    EXCLUDED_PATHS = [
        '/api/health/',
        '/api/refuges/',
        '/api/cache/',
        '/admin/',
        '/swagger/',
        '/redoc/',
    ]
    
    def process_request(self, request):
        """
        Processa la request abans que arribi a la vista.
        Verifica el token JWT si l'endpoint ho requereix.
        """
        # Comprova si el path està exclòs
        if self._is_path_excluded(request.path):
            return None
        
        # Obté el token del header Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return self._unauthorized_response('Token d\'autenticació no proporcionat')
        
        # Extreu el token del format "Bearer <token>"
        token_parts = auth_header.split()
        if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
            return self._unauthorized_response('Token d\'autenticació no proporcionat')
        
        token = token_parts[1]
        
        try:
            # Verifica el token amb Firebase Admin SDK
            decoded_token = auth.verify_id_token(token)
            
            # Afegeix la informació de l'usuari a la request
            request.firebase_user = decoded_token
            request.user_uid = decoded_token.get('uid')
            
            logger.info(f"Token verificat correctament per a l'usuari: {request.user_uid}")
            return None
            
        except auth.ExpiredIdTokenError:
            logger.warning("Token JWT expirat")
            return self._unauthorized_response('Token expirat')
            
        except auth.RevokedIdTokenError:
            logger.warning("Token JWT revocat")
            return self._unauthorized_response('Token revocat')
            
        except auth.InvalidIdTokenError as e:
            logger.warning(f"Token JWT invàlid: {str(e)}")
            return self._unauthorized_response('Token invàlid')
            
        except Exception as e:
            logger.error(f"Error verificant token: {str(e)}")
            return self._unauthorized_response('Error verificant el token: ' + str(e))
    
    def _is_path_excluded(self, path):
        """Comprova si el path està exclòs de l'autenticació"""
        for excluded_path in self.EXCLUDED_PATHS:
            if path.startswith(excluded_path):
                return True
        return False
    
    def _unauthorized_response(self, message):
        """Retorna una resposta 401 Unauthorized"""
        return JsonResponse({
            'error': 'No autoritzat',
            'message': message
        }, status=status.HTTP_401_UNAUTHORIZED)
