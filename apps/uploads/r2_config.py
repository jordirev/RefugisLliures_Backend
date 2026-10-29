import os
import boto3
from botocore.config import Config


def get_r2_client():
    """
    Creates and returns a configured boto3 S3 client for Cloudflare R2.
    Les variables d'entorn es llegeixen dins de la funció per permetre
    que els tests les configurin abans de la primera crida.
    """
    r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_endpoint = os.getenv("R2_ENDPOINT")
    r2_bucket_name = os.getenv("R2_BUCKET_NAME")
    
    if not all([r2_access_key_id, r2_secret_access_key, r2_endpoint, r2_bucket_name]):
        raise ValueError("R2 configuration is incomplete. Please check environment variables.")
    
    return boto3.client(
        service_name='s3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_access_key_id,
        aws_secret_access_key=r2_secret_access_key,
        region_name='auto',  # Cloudflare R2 uses 'auto' as region
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    )


# Per mantenir compatibilitat, exportem les variables com a funcions
def get_r2_bucket_name():
    """Retorna el nom del bucket R2."""
    return os.getenv("R2_BUCKET_NAME")


def get_r2_endpoint():
    """Retorna l'endpoint R2."""
    return os.getenv("R2_ENDPOINT")


# Mantenim les variables per compatibilitat amb codi existent
# que pugui importar-les directament (seran None si no estan configurades)
R2_ACCESS_KEY_ID = None
R2_SECRET_ACCESS_KEY = None
R2_ENDPOINT = None
R2_BUCKET_NAME = None
