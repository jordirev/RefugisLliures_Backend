"""
R2 Media Service - Servei per gestionar la pujada, obtenció i eliminació de mitjans al bucket R2 de Cloudflare.
Utilitza el patró Strategy per a gestionar diferents tipus de fitxers i destinacions.
"""
import uuid
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from botocore.exceptions import ClientError
from .r2_config import get_r2_client, get_r2_bucket_name

logger = logging.getLogger(__name__)

class MediaPathStrategy(ABC):
    """
    Estratègia abstracta per definir com es construeixen els paths per a diferents tipus de mitjans.
    """
    
    @abstractmethod
    def get_base_path(self, entity_id: str) -> str:
        """Retorna el path base per a un tipus de mitjà."""
        pass
    


class RefugiMediaStrategy(MediaPathStrategy):
    """
    Estratègia per a mitjans (imatges i vídeos) de refugis.
    Path: refugis-lliures/{refuge_id}/{uuid}.{ext} (+ {uuid}_thumb.webp)
    """
    
    def get_base_path(self, entity_id: str) -> str:
        return f"refugis-lliures/{entity_id}"
    


class UserAvatarStrategy(MediaPathStrategy):
    """
    Estratègia per a avatars d'usuaris (només imatges).
    Path: users-avatars/{uid}/{uuid}.webp
    """
    
    def get_base_path(self, entity_id: str) -> str:
        return f"users-avatars/{entity_id}"
    


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
        self.bucket_name = get_r2_bucket_name()
    
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
    
    # ------------------------------------------------------------------
    # Pujada directa (presigned PUT) i post-procés
    # ------------------------------------------------------------------

    def build_media_key(self, entity_id: str, extension: str, suffix: str = '', media_id: Optional[str] = None) -> str:
        """
        Construeix una clau UUID dins del path base de l'estratègia.
        Ex: refugis-lliures/{id}/{uuid}.webp, refugis-lliures/{id}/{uuid}_thumb.webp
        """
        media_id = media_id or str(uuid.uuid4())
        if extension and not extension.startswith('.'):
            extension = f".{extension}"
        return f"{self.strategy.get_base_path(entity_id)}/{media_id}{suffix}{extension}"

    def generate_presigned_put_url(self, key: str, content_type: str, content_length: int,
                                   expiration: int = 600) -> str:
        """
        Genera una URL PUT prefirmada. Es signen Content-Type i Content-Length, de manera
        que R2 rebutja una pujada amb un altre tipus o una altra mida.

        Raises:
            Exception: si no es pot generar
        """
        try:
            return self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'ContentType': content_type,
                    'ContentLength': int(content_length),
                },
                ExpiresIn=expiration,
                HttpMethod='PUT',
            )
        except ClientError as e:
            logger.error(f"Error generant URL PUT prefirmada: {str(e)}")
            raise Exception(f"Error generant URL PUT prefirmada: {str(e)}")

    def head_object(self, key: str) -> Optional[Dict]:
        """
        Retorna {'size': int, 'content_type': str} o None si l'objecte no existeix.

        Raises:
            ClientError: errors diferents de 404
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'size': int(response.get('ContentLength', 0)),
                'content_type': response.get('ContentType'),
            }
        except ClientError as e:
            code = str(e.response.get('Error', {}).get('Code', ''))
            if code in ('404', 'NoSuchKey', 'NotFound'):
                return None
            logger.error(f"Error fent HEAD de {key}: {str(e)}")
            raise

    def get_object_bytes(self, key: str, max_bytes: Optional[int] = None) -> Optional[bytes]:
        """
        Descarrega un objecte. Si max_bytes està definit es llegeixen com a molt
        max_bytes + 1 bytes (el caller detecta "massa gran"). None si no existeix.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            body = response['Body']
            if max_bytes is not None:
                return body.read(max_bytes + 1)
            return body.read()
        except ClientError as e:
            code = str(e.response.get('Error', {}).get('Code', ''))
            if code in ('404', 'NoSuchKey', 'NotFound'):
                return None
            logger.error(f"Error descarregant {key}: {str(e)}")
            raise

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """
        Puja bytes ja processats a una clau concreta.

        Raises:
            Exception: si falla la pujada
        """
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl='private, max-age=31536000, immutable',
            )
            logger.info(f"Fitxer pujat correctament: {key}")
        except ClientError as e:
            logger.error(f"Error pujant {key} a R2: {str(e)}")
            raise Exception(f"Error pujant fitxer: {str(e)}")

    def copy_object(self, source_key: str, dest_key: str) -> bool:
        """Copia un objecte dins del bucket. Retorna True/False (no llança)."""
        try:
            self.client.copy_object(
                Bucket=self.bucket_name,
                Key=dest_key,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key},
            )
            return True
        except ClientError as e:
            logger.error(f"Error copiant {source_key} a {dest_key}: {str(e)}")
            return False

    def move_object(self, source_key: str, dest_key: str) -> bool:
        """Copia i esborra l'origen. Retorna True només si la còpia ha anat bé."""
        if not self.copy_object(source_key, dest_key):
            return False
        if not self.delete_file(source_key):
            logger.warning(f"Copiat {source_key} a {dest_key} però no s'ha pogut esborrar l'origen")
        return True


# Factory functions per crear instàncies del servei amb diferents estratègies

def get_refugi_media_service() -> R2MediaService:
    """Retorna una instància del servei configurada per a mitjans de refugis."""
    return R2MediaService(RefugiMediaStrategy())


def get_user_avatar_service() -> R2MediaService:
    """Retorna una instància del servei configurada per a avatars d'usuaris."""
    return R2MediaService(UserAvatarStrategy())


QUARANTINE_PREFIX = 'quarantine'
MODERATION_HOLD_PREFIX = 'moderation-hold'


def quarantine_key(upload_id: str) -> str:
    """Clau temporal d'una pujada directa (lifecycle de R2: 1 dia)."""
    return f"{QUARANTINE_PREFIX}/{upload_id}"


def moderation_hold_key(original_key: str) -> str:
    """Clau d'evidència retinguda per moderació (accés restringit)."""
    return f"{MODERATION_HOLD_PREFIX}/{original_key}"
