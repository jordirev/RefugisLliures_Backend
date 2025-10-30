"""
Middleware per a l'aplicació API
"""
from .firebase_auth_middleware import FirebaseAuthenticationMiddleware

__all__ = ['FirebaseAuthenticationMiddleware']
