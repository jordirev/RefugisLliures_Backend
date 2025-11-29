"""
Backend d'autenticació personalitzat per a Firebase Auth
"""
import logging
from rest_framework import authentication
from rest_framework import exceptions
from firebase_admin import auth

logger = logging.getLogger(__name__)


class FirebaseAuthentication(authentication.BaseAuthentication):
    """
    Classe d'autenticació personalitzada per a Django REST Framework
    que verifica tokens JWT de Firebase Auth
    """
    
    def authenticate(self, request):
        """
        Autentica la request utilitzant el token JWT de Firebase
        
        Returns:
            tuple: (user, token) si l'autenticació té èxit, None en cas contrari
        """
        # Si ja hem verificat el token al middleware, utilitza aquesta informació
        if hasattr(request, 'firebase_user') and hasattr(request, 'user_uid'):
            # Crea un objecte d'usuari simple amb la informació del token
            user_claims = getattr(request, 'user_claims', {})
            user = type('FirebaseUser', (), {
                'uid': request.user_uid,
                'email': request.firebase_user.get('email'),
                'is_authenticated': True,
                'is_anonymous': False,
                'claims': user_claims,
            })()
            return (user, request.firebase_user)
        
        # Si no hi ha informació del middleware, intenta verificar el token aquí
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        token_parts = auth_header.split()
        if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Format del token invàlid')
        
        token = token_parts[1]
        
        try:
            decoded_token = auth.verify_id_token(token)
            
            # Crea un objecte d'usuari amb la informació del token
            user = type('FirebaseUser', (), {
                'uid': decoded_token.get('uid'),
                'email': decoded_token.get('email'),
                'is_authenticated': True,
                'is_anonymous': False,
                'claims': decoded_token,
            })()
            
            return (user, decoded_token)
            
        except auth.ExpiredIdTokenError:
            raise exceptions.AuthenticationFailed('Token expirat')
        except auth.RevokedIdTokenError:
            raise exceptions.AuthenticationFailed('Token revocat')
        except auth.InvalidIdTokenError:
            raise exceptions.AuthenticationFailed('Token invàlid')
        except Exception as e:
            logger.error(f"Error verificant token: {str(e)}")
            raise exceptions.AuthenticationFailed('Error verificant el token')
    
    def authenticate_header(self, request):
        """
        Retorna el valor del header WWW-Authenticate en cas d'error d'autenticació
        """
        return 'Bearer realm="api"'
