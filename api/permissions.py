"""
Permisos personalitzats per a l'API
"""
import logging
logger = logging.getLogger(__name__)
from rest_framework import permissions
from .services import firestore_service

# Helper per a comprovar si l'usuari és admin
def is_firebase_admin(request):
    """
    Comprova si l'usuari autenticat és un administrador mitjançant custom claims
    """
    # Obté els custom claims de l'usuari
    user_claims = getattr(request, 'user_claims', {})
    if not user_claims:
        # Intenta obtenir-los de l'objecte user si no estan a request
        user_claims = getattr(request.user, 'claims', {})
    
    # Comprova si l'usuari té el custom claim 'role' amb valor 'admin'
    return user_claims.get('role') == 'admin'



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
        
        return is_firebase_admin(request)


class IsExperienceCreator(permissions.BasePermission):
    """
    Permís personalitzat que només permet accedir al creador d'una clase.
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
        # Els admins tenen accés directe
        if is_firebase_admin(request):
            return True
        
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté l'ID de l'objecte des de la vista
        instance_id = view.kwargs.get('experience_id')
    
        # Si no hi ha id, és un endpoint de creació (POST) i no cal verificar
        if not instance_id:
            logger.info("No hi ha experience_id, permetent accés (creació).")
            return True

        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        from .daos.experience_dao import ExperienceDAO
        # Obtenim l'objecte des de la base de dades
        instance = ExperienceDAO().get_experience_by_id(instance_id)
        
        # Comprova si l'usuari és el creador de l'objecte
        return instance.get('creator_uid') == user_uid
    
class IsRenovationCreator(permissions.BasePermission):
    """
    Permís personalitzat que només permet accedir al creador d'una clase.
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
        # Els admins tenen accés directe
        if is_firebase_admin(request):
            return True
        
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté l'ID de l'objecte des de la vista
        instance_id = view.kwargs.get('id')
    
        # Si no hi ha id, és un endpoint de creació (POST) i no cal verificar
        if not instance_id:
            logger.info("No hi ha experience_id, permetent accés (creació).")
            return True
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        from .daos.renovation_dao import RenovationDAO
        # Obtenim l'objecte des de la base de dades
        instance = RenovationDAO().get_renovation_by_id(instance_id)
        
        # Comprova si l'usuari és el creador de l'objecte
        return instance.get('creator_uid') == user_uid

class IsDoubtCreator(permissions.BasePermission):
    """
    Permís personalitzat que només permet accedir al creador d'un dubte.
    Comprova que el creator_uid del dubte coincideix amb l'UID de l'usuari autenticat.
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari està autenticat
        """
        return request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Comprova si l'usuari és el creador del dubte
        """
        # Els admins tenen accés directe
        if is_firebase_admin(request):
            return True
        
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté l'ID del dubte des de la vista
        doubt_id = view.kwargs.get('doubt_id')
        
        # Si no hi ha id, és un endpoint de creació (POST) i no cal verificar
        if not doubt_id:
            logger.info("No hi ha doubt_id, permetent accés (creació).")
            return True
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        from .controllers.doubt_controller import DoubtController
        # Obtenim el dubte des de la base de dades
        doubt = DoubtController().get_doubt_by_id(doubt_id)
        
        if not doubt:
            return False
        
        # Comprova si l'usuari és el creador del dubte
        return doubt.creator_uid == user_uid


class IsAnswerCreator(permissions.BasePermission):
    """
    Permís personalitzat que només permet accedir al creador d'una resposta.
    Comprova que el creator_uid de la resposta coincideix amb l'UID de l'usuari autenticat.
    """
    
    def has_permission(self, request, view):
        """
        Comprova si l'usuari està autenticat
        """
        return request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Comprova si l'usuari és el creador de la resposta
        """
        # Els admins tenen accés directe
        if is_firebase_admin(request):
            return True
        
        # Només aplica a mètodes no segurs (POST, PUT, PATCH, DELETE)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Obté l'ID de la resposta des de la vista
        answer_id = view.kwargs.get('answer_id')
        doubt_id = view.kwargs.get('doubt_id')
        
        # Si no hi ha id, és un endpoint de creació (POST) i no cal verificar
        if not answer_id or not doubt_id:
            logger.info("No hi ha answer_id o doubt_id, permetent accés (creació).")
            return True
        
        # Obté el UID de l'usuari autenticat
        user_uid = getattr(request, 'user_uid', None)
        if not user_uid:
            return False
        
        from .controllers.doubt_controller import DoubtController
        # Obtenim la resposta des de la base de dades
        answer = DoubtController().get_answer_by_id(doubt_id, answer_id)
        
        if not answer:
            return False
        
        # Comprova si l'usuari és el creador de la resposta
        return answer.creator_uid == user_uid



# ========== Edat i bloqueig (feature images) ==========

from rest_framework import exceptions as drf_exceptions

ERROR_CODE_AGE_NOT_CONFIRMED = 'age_not_confirmed'
ERROR_CODE_USER_BLOCKED = 'user_blocked'
ERROR_CODE_PROFILE_REQUIRED = 'profile_required'


def coded_error(code: str, message: str) -> dict:
    """Cos d'error amb codi explícit: {error: code, code: code, message: text}"""
    return {'error': code, 'code': code, 'message': message}


def _request_uid(request):
    uid = getattr(request, 'user_uid', None)
    if not uid:
        uid = getattr(getattr(request, 'user', None), 'uid', None)
    return uid if isinstance(uid, str) else None


def get_user_for_permissions(uid):
    """Fila de `users.users` de PostgreSQL (la RLS del context de la petició la deixa veure). 1 consulta; sense cache."""
    if not uid:
        return None
    from apps.accounts import selectors
    return selectors.get_user(uid)


_UNSET = object()


def _request_account(request):
    """
    Usuari (`UserAccount` o `None`) de la petició, llegit **una sola vegada** per petició encara que hi hagi
    `HasProfile` + `IsNotBlocked` + `IsAgeConfirmed` (§7.3.6). La cau viu a l'objecte `request`, no a Redis.
    """
    uid = _request_uid(request)
    cached = getattr(request, '_account_cache', _UNSET)
    if cached is not _UNSET and cached[0] == uid:
        return cached[1]
    user = get_user_for_permissions(uid)
    request._account_cache = (uid, user)
    return user


def _is_authenticated(request) -> bool:
    return bool(request.user and getattr(request.user, 'is_authenticated', False))


class HasProfile(permissions.BasePermission):
    """
    Requereix que l'usuari autenticat tingui fila a `users.users` (el perfil es crea amb `POST /users/`).
    Falla amb 403 {error: 'profile_required'}. Va just després d'`IsAuthenticated` a tot endpoint autenticat
    llevat de `POST /users/`.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request):
            return False
        if _request_account(request) is None:
            raise drf_exceptions.PermissionDenied(coded_error(
                ERROR_CODE_PROFILE_REQUIRED, "Cal crear el perfil d'usuari abans d'usar l'aplicació."))
        return True


class IsNotBlocked(permissions.BasePermission):
    """
    Denega l'accés als usuaris bloquejats per moderació (users.users.is_blocked).
    Falla amb 403 {error: 'user_blocked'}.
    """

    def has_permission(self, request, view):
        # L'autenticació la comprova IsAuthenticated (va abans a la llista); aquí només el bloqueig
        if not _request_uid(request):
            return _is_authenticated(request)
        user = _request_account(request)
        if user is not None and getattr(user, 'is_blocked', False) is True:
            raise drf_exceptions.PermissionDenied(coded_error(
                ERROR_CODE_USER_BLOCKED,
                "El teu compte està bloquejat per incompliment de les normes de la comunitat."
            ))
        return True


class IsAgeConfirmed(permissions.BasePermission):
    """
    Requereix que l'usuari hagi confirmat que té 16 anys o més (users.users.age_confirmed_at).
    Falla amb 403 {error: 'age_not_confirmed'}.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request):
            return False
        user = _request_account(request)
        if user is None or not getattr(user, 'age_confirmed_at', None):
            raise drf_exceptions.PermissionDenied(coded_error(
                ERROR_CODE_AGE_NOT_CONFIRMED,
                "Cal confirmar l'edat abans de pujar o denunciar contingut."
            ))
        return True
