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
    Utilitza els Custom Claims de Firebase Auth per determinar si un usuari és admin.
    Un usuari és administrador si té el custom claim 'role' amb valor 'admin'.
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari autenticat és un administrador mitjançant custom claims
        """
        # Comprova que l'usuari està autenticat
        if not request.user or not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
            return False
        
        # Obté els custom claims de l'usuari
        user_claims = getattr(request, 'user_claims', {})
        if not user_claims:
            # Intenta obtenir-los de l'objecte user si no estan a request
            user_claims = getattr(request.user, 'claims', {})
        
        # Comprova si l'usuari té el custom claim 'role' amb valor 'admin'
        return user_claims.get('role') == 'admin'


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
