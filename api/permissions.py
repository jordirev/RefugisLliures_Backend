"""
Permisos personalitzats per a l'API
"""
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permís personalitzat que permet llegir a qualsevol usuari autenticat,
    però només permet escriure al propietari del recurs
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari té permís per accedir a la vista
        """
        # Permet accés autenticat per a tots els mètodes
        return request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Comprova si l'usuari té permís per accedir a l'objecte
        """
        # Permet llegir a qualsevol usuari autenticat
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Només permet escriure al propietari
        return obj.uid == request.user.uid


class IsSameUser(permissions.BasePermission):
    """
    Permís que comprova si l'usuari autenticat està accedint a les seves pròpies dades
    basant-se en el paràmetre 'uid' de la URL
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari autenticat està accedint a les seves pròpies dades
        """
        # Comprova que l'usuari està autenticat
        if not request.user or not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
            return False
        
        # Obté el UID del paràmetre de la URL
        url_uid = view.kwargs.get('uid')
        
        # Si no hi ha UID a la URL (per exemple, en endpoints de col·lecció), permet l'accés
        if not url_uid:
            return True
        
        # Comprova que l'UID de la URL coincideix amb l'UID de l'usuari autenticat
        return url_uid == request.user.uid


class SafeMethodsOnly(permissions.BasePermission):
    """
    Permís que només permet mètodes HTTP segurs (GET, HEAD, OPTIONS)
    """
    
    def has_permission(self, request, view):
        """
        Només permet mètodes HTTP segurs
        """
        return request.method in permissions.SAFE_METHODS


class IsFirebaseAdmin(permissions.BasePermission):
    """
    Permís que només permet accés als usuaris administradors de Firebase.
    Els UIDs d'administradors es defineixen a settings.FIREBASE_ADMIN_UIDS.
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari autenticat és un administrador
        """
        from django.conf import settings
        
        # Comprova que l'usuari està autenticat
        if not request.user or not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
            return False
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        # Comprova si el UID està a la llista d'administradors
        admin_uids = getattr(settings, 'FIREBASE_ADMIN_UIDS', [])
        return user_uid in admin_uids


class IsCreator(permissions.BasePermission):
    """
    Permís personalitzat que només permet accedir al creador d'una renovation.
    Comprova que el creator_uid de l'objecte coincideix amb l'UID de l'usuari autenticat.
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari està autenticat
        """
        return request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Comprova si l'usuari és el creador de l'objecte
        """
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        # Comprova si l'objecte té un camp 'creator_uid' i coincideix amb l'usuari autenticat
        if hasattr(obj, 'creator_uid'):
            return obj.creator_uid == user_uid
        return False
