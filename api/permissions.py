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
    Permís personalitzat que només permet accedir al creador d'una clase.
    Comprova que el creator_uid de l'objecte coincideix amb l'UID de l'usuari autenticat.
    """
    
    def has_permission(self, request):
        """
        Comprova si l'usuari està autenticat
        """
        return request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated
    
    def has_object_permission(self, request, view):
        """
        Comprova si l'usuari és el creador de l'objecte
        """
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        from daos.renovation_dao import RenovationDAO
        
        # Obtenim l'objecte des de la base de dades
        renovation = RenovationDAO.get_renovation_by_id(view.kwargs.get('id'))
        if not renovation:
            return False
        
        # Comprova si l'usuari és el creador de la renovació
        return renovation.get('creator_uid') == user_uid


class IsMediaUploader(permissions.BasePermission):
    """
    Permís personalitzat que verifica si l'usuari és qui va pujar el mitjà.
    
    Busca el mitjà dins del diccionari media_metadata del refugi i comprova
    que el creator_uid del mitjà coincideix amb l'UID de l'usuari autenticat.
    
    Requereix que la vista rebi els paràmetres 'id' (refugi) i 'key' (mitjà).
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari està autenticat i si és el creador del mitjà
        """
        # Comprova que l'usuari està autenticat
        if not request.user or not hasattr(request.user, 'is_authenticated') or not request.user.is_authenticated:
            return False
        
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté els paràmetres de la URL
        refugi_id = view.kwargs.get('id')
        media_key = view.kwargs.get('key')
        
        # Si no hi ha key, no es pot verificar (potser és un endpoint diferent)
        if not media_key or not refugi_id:
            return True
        
        # Decodificar la key si ve codificada
        from urllib.parse import unquote
        decoded_key = unquote(media_key)
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request.user, 'uid', None)
        if not user_uid:
            return False
        
        try:
            # Importa el servei de Firestore
            from daos.refugi_lliure_dao import RefugiLliureDAO
            
            # Obté el refugi des de Firestore
            refugi = RefugiLliureDAO.get_by_id(refugi_id)
            if not refugi:
                return False
            
            # Busca el mitjà dins de media_metadata (ara és un diccionari)
            if 'media_metadata' not in refugi:
                return False
            
            media_metadata = refugi['media_metadata']
            if decoded_key in media_metadata:
                # Comprova si l'usuari és el creador del mitjà
                return media_metadata[decoded_key].get('creator_uid') == user_uid
            
            # Si no es troba el mitjà, denega l'accés
            return False
            
        except Exception as e:
            # En cas d'error, denega l'accés per seguretat
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error verificant permís IsMediaUploader: {str(e)}")
            return False

