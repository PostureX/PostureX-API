import os
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
from typing import List, Dict

client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
)

def get_session_presigned_urls(user_id: str, session_id: str) -> Dict[str, str]:
    """
    Get presigned URLs for all media files in a session
    
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
                # Generate presigned URL (valid for 1 hour)
                url = client.presigned_get_object(
                    videos_bucket, 
                    obj.object_name, 
                    expires=timedelta(hours=1)
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