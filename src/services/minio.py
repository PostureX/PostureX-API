import os
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from typing import List, Dict

# Import caching functions
from src.utils.cache import get_cached_presigned_url, cache_presigned_url
from src.config.app_config import AppConfig

CONFIG = AppConfig()

client = Minio(
    CONFIG.minio_endpoint,
    access_key=CONFIG.minio_access_key,
    secret_key=CONFIG.minio_secret_key,
    secure=CONFIG.minio_secure,
)


def get_session_presigned_urls(user_id: str, session_id: str) -> Dict[str, str]:
    """
    Get presigned URLs for all media files in a session with caching

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        Dict mapping file names to presigned URLs
    """
    try:
        videos_bucket = "videos"

        # Check if videos bucket exists
        if not client.bucket_exists(videos_bucket):
            return {}

        prefix = f"{user_id}/{session_id}/"
        objects = client.list_objects(videos_bucket, prefix=prefix, recursive=True)

        presigned_urls = {}
        for obj in objects:
            try:
                # Check cache first
                cached_url = get_cached_presigned_url(videos_bucket, obj.object_name)

                if cached_url:
                    # Use cached URL
                    filename = obj.object_name.split("/")[-1]
                    side = filename.split("_")[-1].split(".")[0]
                    presigned_urls[side] = cached_url
                else:
                    # Generate new presigned URL (valid for 1 hour)
                    expires_delta = timedelta(hours=1)
                    url = client.presigned_get_object(
                        videos_bucket, obj.object_name, expires=expires_delta
                    )

                    # Cache the URL
                    cache_presigned_url(
                        videos_bucket, obj.object_name, url, expires_delta
                    )

                    # Use the full filename as the key
                    filename = obj.object_name.split("/")[-1]
                    # Extract side from filename
                    side = filename.split("_")[-1]
                    # Remove file extension
                    side = side.split(".")[0]
                    presigned_urls[side] = url

            except Exception as e:
                print(f"Error generating presigned URL for {obj.object_name}: {e}")
                continue

        return presigned_urls

    except Exception as e:
        print(f"Error getting presigned URLs for session {session_id}: {str(e)}")
        return {}
