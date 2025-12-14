import os
import boto3
from botocore.config import Config

# R2 configuration
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")


def get_r2_client():
    """
    Creates and returns a configured boto3 S3 client for Cloudflare R2.
    """
    if not all([R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_BUCKET_NAME]):
        raise ValueError("R2 configuration is incomplete. Please check environment variables.")
    
    return boto3.client(
        service_name='s3',
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto',  # Cloudflare R2 uses 'auto' as region
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    )

