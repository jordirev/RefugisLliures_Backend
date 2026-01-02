"""
Servei per gestionar la cache amb Redis
"""
import json
import logging
import hashlib
from typing import Any, Optional, Callable, List, Dict
from functools import wraps
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Servei singleton per gestionar operacions de cache"""
    
    _instance = None
    
    # Cache timeouts per defecte (en segons)
    CACHE_TIMEOUTS = {
        # Refugis
        'refugi_detail': 600,      # 10 minuts
        'refugi_search': 600,      # 10 minuts
        'refugi_coords': 3600,     # 1 hora
        
        # Usuaris
        'user_detail': 600,        # 10 minuts
        
        # Renovations
        'renovation_detail': 600,  # 10 minuts
        'renovation_list': 600,    # 10 minuts
        
        # Experiences
        'experience_detail': 600,  # 10 minuts
        'experience_list': 600,    # 10 minuts
        
        # Proposals
        'proposal_detail': 600,    # 10 minuts
        'proposal_list': 600,      # 10 minuts
        
        # Visits
        'refuge_visit_detail': 600,  # 10 minuts
        'refuge_visits_list': 600,   # 10 minuts
        
        # Doubts
        'doubt_detail': 600,       # 10 minuts
        'doubt_list': 600,         # 10 minuts
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Inicialitza els timeouts definits en CACHE_TIMEOUTS
        self.timeouts = self.CACHE_TIMEOUTS.copy()
    
    def get_timeout(self, key_type: str) -> int:
        """Obté el timeout específic per un tipus de clau"""
        return self.timeouts.get(key_type, 600)  # 10 minuts per defecte
    
    def generate_key(self, prefix: str, **kwargs) -> str:
        """
        Genera una clau de cache única basada en prefix i paràmetres
        
        Args:
            prefix: Prefix per la clau (ex: 'refugi_detail')
            **kwargs: Paràmetres que identifiquen únicament l'objecte
            
        Returns:
            Clau de cache generada (ex: 'refugi_detail:refugi_id:123')
        """
        # Ordena els paràmetres per consistència
        if not kwargs:
            return prefix
        
        # Construeix la clau concatenant parelles clau:valor ordenades
        sorted_params = sorted(kwargs.items())
        parts = [prefix]
        for key, value in sorted_params:
            # Converteix el valor a string per assegurar consistència
            parts.append(f"{key}:{value}")
        
        return ":".join(parts)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obté un valor de la cache
        
        Args:
            key: Clau de cache
            
        Returns:
            Valor de la cache o None si no existeix
        """
        try:
            # Only log whether it's a hit or miss (no key) per request
            value = cache.get(key)
            if value is not None:
                # Use numeric custom level so the logger configured with CACHE_LEVEL will emit it
                logger.log(21, "Cache HIT")
            else:
                logger.log(21, "Cache MISS")
            return value
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Estableix un valor a la cache
        
        Args:
            key: Clau de cache
            value: Valor a guardar
            timeout: Temps en segons (None = default)
            
        Returns:
            True si s'ha guardat correctament
        """
        try:
            cache.set(key, value, timeout)
            logger.log(21, f"Cache SET (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Elimina una clau de la cache
        
        Args:
            key: Clau a eliminar
            
        Returns:
            True si s'ha eliminat correctament
        """
        try:
            cache.delete(key)
            logger.log(21, "Cache DELETE")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """
        Elimina totes les claus que coincideixin amb un patró
        
        Args:
            pattern: Patró de claus (ex: 'refugi_*')
            
        Returns:
            True si s'han eliminat correctament
        """
        try:
            cache.delete_pattern(f"*{pattern}*")
            logger.log(21, f"Cache DELETE PATTERN: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache pattern {pattern}: {str(e)}")
            return False
    
    def clear_all(self) -> bool:
        """
        Neteja tota la cache
        
        Returns:
            True si s'ha netejat correctament
        """
        try:
            cache.clear()
            logger.log(21, "Cache cleared completely")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    def get_stats(self) -> dict:
        """
        Obté estadístiques de la cache
        
        Returns:
            Diccionari amb estadístiques
        """
        try:
            # Intenta obtenir estadístiques de Redis
            from django_redis import get_redis_connection
            con = get_redis_connection("default")
            info = con.info()
            
            return {
                'connected': True,
                'keys': con.dbsize(),
                'memory_used': info.get('used_memory_human', 'N/A'),
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                'connected': False,
                'error': str(e)
            }
    
    def get_or_fetch_list(
        self, 
        list_cache_key: str, 
        detail_key_prefix: str,
        fetch_all_fn: Callable[[], List[Dict[str, Any]]],
        fetch_single_fn: Callable[[str], Optional[Dict[str, Any]]],
        get_id_fn: Callable[[Dict[str, Any]], str],
        list_timeout: Optional[int] = None,
        detail_timeout: Optional[int] = None,
        id_param_name: str = 'id'
    ) -> List[Dict[str, Any]]:
        """
        Implementa l'estratègia ID caching per llistes:
        1. Busca la llista d'IDs a la cache
        2. Per cada ID, busca el detall a la cache
        3. Si no hi ha llista cached, llegeix TOTES les dades d'una (no el doble de lectures)
        4. Guarda la llista d'IDs i cada detall per separat
        5. Si algun detall ha expirat, el llegeix individualment de Firestore
        
        Args:
            list_cache_key: Clau de cache per la llista d'IDs
            detail_key_prefix: Prefix per les claus de detall (ex: 'refugi_detail')
            fetch_all_fn: Funció que retorna TOTES les dades completes des de Firestore
            fetch_single_fn: Funció que retorna un element individual per ID des de Firestore
            get_id_fn: Funció per extreure l'ID d'un element de dades
            list_timeout: Timeout per la llista d'IDs
            detail_timeout: Timeout per cada detall
            id_param_name: Nom del paràmetre per la clau de detall (ex: 'renovation_id', 'experience_id')
            
        Returns:
            Llista de diccionaris amb les dades completes
        """
        # 1. Intenta obtenir llista d'IDs de la cache
        cached_ids = self.get(list_cache_key)
        
        if cached_ids is None:
            # Cache MISS: Llegeix TOTES les dades d'una des de Firestore (no el doble de lectures)
            all_data = fetch_all_fn()
            
            # Extreu les IDs i guarda la llista
            ids = [get_id_fn(item) for item in all_data]
            actual_list_timeout = list_timeout or self.get_timeout(detail_key_prefix.replace('_detail', '_list'))
            self.set(list_cache_key, ids, actual_list_timeout)
            
            # Guarda cada detall individualment a la cache
            actual_detail_timeout = detail_timeout or self.get_timeout(detail_key_prefix)
            for item_data in all_data:
                item_id = get_id_fn(item_data)
                detail_cache_key = self.generate_key(detail_key_prefix, **{id_param_name: item_id})
                self.set(detail_cache_key, item_data, actual_detail_timeout)
            
            return all_data
        
        # Cache HIT: Usa la llista d'IDs cached i busca cada detall
        results = []
        actual_detail_timeout = detail_timeout or self.get_timeout(detail_key_prefix)
        
        for item_id in cached_ids:
            detail_cache_key = self.generate_key(detail_key_prefix, **{id_param_name: item_id})
            cached_detail = self.get(detail_cache_key)
            
            if cached_detail is not None:
                # Detall trobat a la cache
                results.append(cached_detail)
            else:
                # Detall no cached: llegeix-lo individualment de Firestore
                logger.log(21, f"Cache MISS for detail {detail_key_prefix}:{item_id}, fetching from Firestore")
                item_data = fetch_single_fn(item_id)
                if item_data:
                    # Guarda el detall a la cache per futures lectures
                    self.set(detail_cache_key, item_data, actual_detail_timeout)
                    results.append(item_data)
        
        return results
    
    def get_or_fetch_detail(
        self,
        detail_cache_key: str,
        fetch_fn: Callable[[], Optional[Dict[str, Any]]],
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Obté un detall de la cache o el llegeix de Firestore
        
        Args:
            detail_cache_key: Clau de cache per el detall
            fetch_fn: Funció que retorna el detall des de Firestore
            timeout: Timeout per la cache
            
        Returns:
            Diccionari amb les dades o None si no existeix
        """
        # Intenta obtenir de cache
        cached_data = self.get(detail_cache_key)
        if cached_data is not None:
            logger.info(f"Retrieved detail for cache key {detail_cache_key} from cache")
            return cached_data
        
        # Cache MISS: llegeix de Firestore
        data = fetch_fn()
        logger.info(f"Fetched detail for cache key {detail_cache_key} from Firestore")
        if data:
            # Guarda a cache
            self.set(detail_cache_key, data, timeout)
        
        return data


# Instància global del servei
cache_service = CacheService()


# Decorador per caching automàtic
def cache_result(key_prefix: str, timeout: Optional[int] = None):
    """
    Decorador per fer cache automàtic del resultat d'una funció
    
    Args:
        key_prefix: Prefix per la clau de cache
        timeout: Temps de cache en segons (None = default)
    
    Usage:
        @cache_result('refugi_detail', timeout=600)
        def get_refugi(refuge_id):
            return refugi_data
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Genera clau única basada en arguments
            cache_key = cache_service.generate_key(key_prefix, args=args, kwargs=kwargs)
            
            # Intenta obtenir de cache
            cached_value = cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Si no està en cache, executa la funció
            result = func(*args, **kwargs)
            
            # Guarda a cache
            actual_timeout = timeout or cache_service.get_timeout(key_prefix)
            cache_service.set(cache_key, result, actual_timeout)
            
            return result
        return wrapper
    return decorator
