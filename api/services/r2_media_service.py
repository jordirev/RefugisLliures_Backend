"""
R2 Media Service - Servei per gestionar la pujada, obtenció i eliminació de mitjans al bucket R2 de Cloudflare.
Utilitza el patró Strategy per a gestionar diferents tipus de fitxers i destinacions.
"""
import uuid
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, BinaryIO
from urllib.parse import urlparse, unquote
from datetime import datetime
from botocore.exceptions import ClientError
from ..r2_config import get_r2_client, R2_BUCKET_NAME, R2_ENDPOINT
from ..models.media_metadata import MediaMetadata, RefugeMediaMetadata
from ..services.cache_service import CacheService

logger = logging.getLogger(__name__)

class MediaPathStrategy(ABC):
    """
    Estratègia abstracta per definir com es construeixen els paths per a diferents tipus de mitjans.
    """
    
    @abstractmethod
    def get_base_path(self, entity_id: str) -> str:
        """Retorna el path base per a un tipus de mitjà."""
        pass
    
    @abstractmethod
    def get_allowed_content_types(self) -> List[str]:
        """Retorna els content types permesos per aquest tipus de mitjà."""
        pass
    
    @abstractmethod
    def validate_file(self, content_type: str) -> bool:
        """Valida si el content type és permès."""
        pass

    @abstractmethod
    def generate_media_metadata_from_dict(self, metadata_dict: Dict[str, str], service, expiration: int = 3600) -> MediaMetadata:
        """Genera un objecte MediaMetadata amb URL prefirmada a partir d'un diccionari de metadades."""
        pass


class RefugiMediaStrategy(MediaPathStrategy):
    """
    Estratègia per a mitjans (imatges i vídeos) de refugis.
    Path: refugis-lliures/{refuge_id}/{filename}
    """
    
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/webp',
        'image/heic',
        'image/heif'
    ]
    
    ALLOWED_VIDEO_TYPES = [
        'video/mp4',
        'video/quicktime',  # .mov
        'video/x-msvideo',  # .avi
        'video/webm'
    ]
    
    def get_base_path(self, entity_id: str) -> str:
        return f"refugis-lliures/{entity_id}"
    
    def get_allowed_content_types(self) -> List[str]:
        return self.ALLOWED_IMAGE_TYPES + self.ALLOWED_VIDEO_TYPES
    
    def validate_file(self, content_type: str) -> bool:
        return content_type in self.get_allowed_content_types()
    
    def generate_media_metadata_from_dict(self, metadata_dict: Dict[str, str], service, expiration: int = 3600) -> MediaMetadata:
        """
        Genera un objecte MediaMetadata amb URL prefirmada a partir d'un diccionari de metadades.
        Per a mitjans de refugi.

        Args:
            metadata_dict: Diccionari amb keys: {'key': {'creator_uid':, 'uploaded_at': }}
            service: Instància de R2MediaService per generar URLs
            expiration: Temps d'expiració de la URL en segons
        
        Returns:
            Objecte MediaMetadata amb URL prefirmada
        """
        # Calculem el expriation en funció del TTL a Cache
        cache_service = CacheService()
        expiration = cache_service.get_timeout('refugi_detail')

        key = next(iter(metadata_dict)) if metadata_dict else ''
        key_dict = metadata_dict[key] if key else {}
        url = service.generate_presigned_url(key, expiration) if key else ''
        
        return RefugeMediaMetadata(
            key=key,
            url=url,
            creator_uid=key_dict.get('creator_uid', ''),
            uploaded_at=key_dict.get('uploaded_at', ''),
            experience_id=key_dict.get('experience_id', None)
        )


class UserAvatarStrategy(MediaPathStrategy):
    """
    Estratègia per a avatars d'usuaris (només imatges).
    Path: users-avatars/{uid}/{filename}
    """
    
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/webp',
        'image/heic',
        'image/heif'
    ]
    
    def get_base_path(self, entity_id: str) -> str:
        return f"users-avatars/{entity_id}"
    
    def get_allowed_content_types(self) -> List[str]:
        return self.ALLOWED_IMAGE_TYPES
    
    def validate_file(self, content_type: str) -> bool:
        return content_type in self.get_allowed_content_types()
    
    def generate_media_metadata_from_dict(self, metadata_dict: Dict[str, str], service, expiration: int = 3600) -> MediaMetadata:
        """
        Genera un objecte MediaMetadata amb URL prefirmada a partir d'un diccionari de metadades.
        Per a l'avatar d'usuari.

        Args:
            metadata_dict: Diccionari amb keys: {'key': , 'uploaded_at': }
            service: Instància de R2MediaService per generar URLs
            expiration: Temps d'expiració de la URL en segons
        
        Returns:
            Objecte MediaMetadata amb URL prefirmada
        """
        # Calculem el expriation en funció del TTL a Cache
        cache_service = CacheService()
        expiration = cache_service.get_timeout('user_detail')
        
        key = metadata_dict.get('key', '')
        url = service.generate_presigned_url(key, expiration) if key else ''
        
        return MediaMetadata(
            key=key,
            url=url,
            uploaded_at=metadata_dict.get('uploaded_at', '')
        )


class R2MediaService:
    """
    Servei principal per gestionar mitjans al bucket R2 de Cloudflare.
    Utilitza estratègies per determinar el comportament segons el tipus de mitjà.
    """
    
    def __init__(self, strategy: MediaPathStrategy):
        """
        Inicialitza el servei amb una estratègia específica.
        
        Args:
            strategy: Estratègia per determinar paths i validacions
        """
        self.strategy = strategy
        self.client = get_r2_client()
        self.bucket_name = R2_BUCKET_NAME
        self.endpoint = R2_ENDPOINT
    
    def upload_file(
        self, 
        file_content: BinaryIO, 
        entity_id: str, 
        content_type: str,
        filename: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Puja un fitxer al bucket R2.
        
        Args:
            file_content: Contingut binari del fitxer
            entity_id: ID de l'entitat (refuge_id o uid)
            content_type: MIME type del fitxer
            filename: Nom del fitxer (opcional, es genera si no es proporciona)
        
        Returns:
            Dict amb 'key' (path al bucket) i 'url' (URL prefirmada)
        
        Raises:
            ValueError: Si el content type no és vàlid
            Exception: Si hi ha un error pujant el fitxer
        """
        # Validar content type
        if not self.strategy.validate_file(content_type):
            raise ValueError(
                f"Content type '{content_type}' no permès. "
                f"Tipus permesos: {self.strategy.get_allowed_content_types()}"
            )
        
        # Generar nom de fitxer si no es proporciona
        if not filename:
            extension = self._get_extension_from_content_type(content_type)
            filename = f"{uuid.uuid4()}{extension}"
        
        # Construir path complet
        base_path = self.strategy.get_base_path(entity_id)
        key = f"{base_path}/{filename}"
        
        try:
            # Pujar fitxer amb AWS Signature
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                ContentType=content_type
            )
            
            logger.info(f"Fitxer pujat correctament: {key}")
            
            # Generar URL prefirmada
            presigned_url = self.generate_presigned_url(key)
            
            return {
                'key': key,
                'url': presigned_url
            }
            
        except ClientError as e:
            logger.error(f"Error pujant fitxer a R2: {str(e)}")
            raise Exception(f"Error pujant fitxer: {str(e)}")
    
    def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Genera una URL prefirmada per accedir a un fitxer.
        
        Args:
            key: Path del fitxer al bucket
            expiration: Temps d'expiració en segons (per defecte 1 hora)
        
        Returns:
            URL prefirmada per accedir al fitxer
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generant URL prefirmada: {str(e)}")
            raise Exception(f"Error generant URL prefirmada: {str(e)}")
    
    def generate_presigned_urls(self, keys: List[str], expiration: int = 3600) -> List[str]:
        """
        Genera URLs prefirmades per a múltiples fitxers.
        
        Args:
            keys: Llista de paths dels fitxers al bucket
            expiration: Temps d'expiració en segons (per defecte 1 hora)
        
        Returns:
            Llista d'URLs prefirmades
        """
        urls = []
        for key in keys:
            try:
                url = self.generate_presigned_url(key, expiration)
                urls.append(url)
            except Exception as e:
                logger.warning(f"No s'ha pogut generar URL per {key}: {str(e)}")
        return urls
    
    def generate_media_metadata_from_dict(self, metadata_dict: Dict[str, str], expiration: int = 3600) -> MediaMetadata:
        """
        Genera un objecte MediaMetadata amb URL prefirmada a partir d'un diccionari de metadades.
        
        Args:
            metadata_dict: Diccionari amb keys: 'key', 'creator_uid', 'uploaded_at'
            expiration: Temps d'expiració de la URL en segons
        
        Returns:
            Objecte MediaMetadata amb URL prefirmada segons si es Refugi o Avatar (sense creator_uid)
        """
        return self.strategy.generate_media_metadata_from_dict(metadata_dict, self, expiration)
    
    def generate_media_metadata_list(self, metadata_input, expiration: int = 3600) -> List[MediaMetadata]:
        """
        Genera una llista d'objectes MediaMetadata amb URLs prefirmades.
        Accepta tant diccionari com llista per compatibilitat.
        
        Args:
            metadata_input: Diccionari o llista de diccionaris amb metadades
            expiration: Temps d'expiració de les URLs en segons
        
        Returns:
            Llista d'objectes MediaMetadata
        """
        result = []
        
        # Si és un diccionari (nova estructura), processar les entrades
        if isinstance(metadata_input, dict):
            for key, metadata in metadata_input.items():
                try:
                    # Crear diccionari amb key i metadata
                    single_key_dict = {key: metadata}
                    media_metadata = self.strategy.generate_media_metadata_from_dict(single_key_dict, self, expiration)
                    result.append(media_metadata)
                except Exception as e:
                    logger.warning(f"No s'ha pogut generar MediaMetadata per {key}: {str(e)}")
        
        # Si és una llista (estructura antiga), processar com abans
        elif isinstance(metadata_input, list):
            for metadata_dict in metadata_input:
                try:
                    media_metadata = self.generate_media_metadata_from_dict(metadata_dict, expiration)
                    result.append(media_metadata)
                except Exception as e:
                    logger.warning(f"No s'ha pogut generar MediaMetadata per {metadata_dict.get('key', 'unknown')}: {str(e)}")
        
        return result
    
    def delete_file(self, key: str) -> bool:
        """
        Elimina un fitxer del bucket R2.
        
        Args:
            key: Path del fitxer al bucket
        
        Returns:
            True si s'ha eliminat correctament, False en cas contrari
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            logger.info(f"Fitxer eliminat correctament: {key}")
            return True
        except ClientError as e:
            logger.error(f"Error eliminant fitxer de R2: {str(e)}")
            return False
    
    def delete_files(self, keys: List[str]) -> Dict[str, List[str]]:
        """
        Elimina múltiples fitxers del bucket R2.
        
        Args:
            keys: Llista de paths dels fitxers al bucket
        
        Returns:
            Dict amb 'deleted' (llista de keys eliminats) i 'failed' (llista de keys amb error)
        """
        deleted = []
        failed = []
        
        for key in keys:
            if self.delete_file(key):
                deleted.append(key)
            else:
                failed.append(key)
        
        return {
            'deleted': deleted,
            'failed': failed
        }
    
    def list_files(self, entity_id: str) -> List[str]:
        """
        Llista tots els fitxers d'una entitat (refugi o usuari).
        
        Args:
            entity_id: ID de l'entitat
        
        Returns:
            Llista de keys dels fitxers
        """
        base_path = self.strategy.get_base_path(entity_id)
        
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=base_path
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
            
        except ClientError as e:
            logger.error(f"Error llistant fitxers: {str(e)}")
            return []
    
    def delete_all_files(self, entity_id: str) -> Dict[str, List[str]]:
        """
        Elimina tots els fitxers d'una entitat.
        
        Args:
            entity_id: ID de l'entitat
        
        Returns:
            Dict amb 'deleted' i 'failed'
        """
        keys = self.list_files(entity_id)
        return self.delete_files(keys)
    
    def _extract_key_from_presigned_url(self, presigned_url: str) -> Optional[str]:
        """
        Extreu el key (path) d'una URL prefirmada.
        
        Args:
            presigned_url: URL prefirmada
        
        Returns:
            Key del fitxer o None si no es pot extreure
        """
        try:
            parsed = urlparse(presigned_url)
            # El path inclou el bucket name, hem d'extreure només el key
            path = parsed.path
            
            # Eliminar el "/" inicial i el bucket name si està present
            if path.startswith('/'):
                path = path[1:]
            
            # Si el path comença amb el bucket name, l'eliminem
            if path.startswith(f"{self.bucket_name}/"):
                path = path[len(f"{self.bucket_name}/"):]
            
            return unquote(path) if path else None
            
        except Exception as e:
            logger.error(f"Error extraient key de URL: {str(e)}")
            return None
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """
        Obté l'extensió del fitxer a partir del content type.
        
        Args:
            content_type: MIME type del fitxer
        
        Returns:
            Extensió del fitxer amb punt (ex: '.jpg')
        """
        extensions = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/heic': '.heic',
            'image/heif': '.heif',
            'video/mp4': '.mp4',
            'video/quicktime': '.mov',
            'video/x-msvideo': '.avi',
            'video/webm': '.webm'
        }
        return extensions.get(content_type, '.bin')


# Factory functions per crear instàncies del servei amb diferents estratègies

def get_refugi_media_service() -> R2MediaService:
    """Retorna una instància del servei configurada per a mitjans de refugis."""
    return R2MediaService(RefugiMediaStrategy())


def get_user_avatar_service() -> R2MediaService:
    """Retorna una instància del servei configurada per a avatars d'usuaris."""
    return R2MediaService(UserAvatarStrategy())
