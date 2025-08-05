import json
import io
from datetime import timedelta, datetime
from typing import Dict, Any, List
from minio.error import S3Error
from .minio import client as minio_client
from .analysis_bucket_minio import ensure_analysis_bucket, ANALYSIS_BUCKET

SUMMARY_BUCKET = "summary"


def ensure_summary_bucket():
    """Ensure the summary bucket exists"""
    try:
        if not minio_client.bucket_exists(SUMMARY_BUCKET):
            minio_client.make_bucket(SUMMARY_BUCKET)
            print(f"Created bucket: {SUMMARY_BUCKET}")
    except S3Error as e:
        print(f"Error ensuring summary bucket: {e}")
        raise


def save_posture_insights(user_id: str, insights_data: Dict[str, Any]) -> bool:
    """
    Save posture insights data to MinIO summary bucket

    Args:
        user_id: User identifier
        insights_data: Dictionary containing date_generated and insights

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_summary_bucket()

        # Create file path: user_id/posture_insights.json
        file_path = f"{user_id}/posture_insights.json"

        # Convert insights data to JSON
        json_data = json.dumps(insights_data, indent=2, default=str)
        json_bytes = json_data.encode("utf-8")

        # Upload to MinIO
        minio_client.put_object(
            SUMMARY_BUCKET,
            file_path,
            io.BytesIO(json_bytes),
            length=len(json_bytes),
            content_type="application/json",
        )

        print(f"Successfully saved posture insights to {file_path}")
        return True

    except Exception as e:
        print(f"Error saving posture insights: {str(e)}")
        return False


def get_posture_insights(user_id: str) -> Dict[str, Any]:
    """
    Get posture insights data from MinIO summary bucket

    Args:
        user_id: User identifier

    Returns:
        Dictionary containing posture insights or empty dict if not found
    """
    try:
        ensure_summary_bucket()

        file_path = f"{user_id}/posture_insights.json"

        # Get object from MinIO
        response = minio_client.get_object(SUMMARY_BUCKET, file_path)
        data = json.loads(response.read().decode("utf-8"))
        response.close()

        return data

    except Exception as e:
        print(f"Error getting posture insights: {str(e)}")
        return {}


def get_posture_insights_presigned_url(user_id: str) -> str:
    """
    Get presigned URL for posture insights file

    Args:
        user_id: User identifier

    Returns:
        String containing presigned URL or empty string if not found
    """
    try:
        ensure_summary_bucket()

        file_path = f"{user_id}/posture_insights.json"

        # Check if file exists
        try:
            minio_client.stat_object(SUMMARY_BUCKET, file_path)
            # Generate presigned URL (valid for 1 hour)
            url = minio_client.presigned_get_object(
                SUMMARY_BUCKET, file_path, expires=timedelta(hours=1)
            )
            return url
        except:
            return ""

    except Exception as e:
        print(f"Error getting posture insights presigned URL: {str(e)}")
        return ""


def get_user_weekly_feedback_data(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all feedback data for a user from the current week

    Args:
        user_id: User identifier

    Returns:
        List of feedback data dictionaries from current week
    """
    try:
        ensure_analysis_bucket()

        # Get current date and calculate week start
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        prefix = f"{user_id}/"
        objects = minio_client.list_objects(
            ANALYSIS_BUCKET, prefix=prefix, recursive=True
        )

        weekly_feedback = []
        for obj in objects:
            # Only process feedback.json files
            if obj.object_name.endswith("/feedback.json"):
                # Check if file was created this week
                if obj.last_modified.replace(tzinfo=None) >= week_start:
                    try:
                        # Get the feedback data
                        response = minio_client.get_object(
                            ANALYSIS_BUCKET, obj.object_name
                        )
                        feedback_data = json.loads(response.read().decode("utf-8"))
                        response.close()

                        # Add metadata
                        feedback_data["session_path"] = obj.object_name
                        feedback_data["created_date"] = obj.last_modified.isoformat()

                        weekly_feedback.append(feedback_data)

                    except Exception as e:
                        print(
                            f"Error reading feedback file {obj.object_name}: {str(e)}"
                        )
                        continue

        return weekly_feedback

    except Exception as e:
        print(f"Error getting weekly feedback data: {str(e)}")
        return []
