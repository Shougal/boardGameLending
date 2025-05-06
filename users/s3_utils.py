# s3_utils.py
import boto3
from django.conf import settings


def generate_presigned_url(key, expires_in=3600):
    """
    Generate a pre-signed URL to access a private S3 file.

    :param key: Full S3 object key, e.g. "images/catan.jpg"
    :param expires_in: Time in seconds the URL is valid (default: 1 hour)
    :return: Pre-signed URL string or None
    """
    try:
        s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        print(f"[S3 Error] Could not generate presigned URL: {e}")
        return None
