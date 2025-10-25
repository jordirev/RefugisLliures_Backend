"""
Servei per gestionar la cache amb Redis
"""
import json
import logging
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Servei singleton per gestionar operacions de cache"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.default_timeout = getattr(settings, 'CACHE_TIMEOUTS', {})
    
    def get_timeout(self, key_type: str) -> int:
        """Obté el timeout específic per un tipus de clau"""
        return self.default_timeout.get(key_type, 300)
    
    def generate_key(self, prefix: str, **kwargs) -> str:
        """
        Genera una clau de cache única basada en prefix i paràmetres
        
        Args:
            prefix: Prefix per la clau (ex: 'refugi_detail')
            **kwargs: Paràmetres que identifiquen únicament l'objecte
            
        Returns:
            Clau de cache generada
        """
        # Ordena els paràmetres per consistència
        params_str = json.dumps(kwargs, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"{prefix}:{params_hash}"
    
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
        def get_refugi(refugi_id):
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
