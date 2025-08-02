"""
MinIO service for storing detailed analysis data
"""
import json
import os
import io
from typing import Dict, Any, List
from minio.error import S3Error
from .minio import client as minio_client

ANALYSIS_BUCKET = "analysis-data"

def ensure_analysis_bucket():
    """Ensure the analysis-data bucket exists"""
    try:
        if not minio_client.bucket_exists(ANALYSIS_BUCKET):
            minio_client.make_bucket(ANALYSIS_BUCKET)
            print(f"Created bucket: {ANALYSIS_BUCKET}")
    except S3Error as e:
        print(f"Error ensuring analysis bucket: {e}")
        raise

def save_detailed_analysis_data(user_id: str, session_id: str, detected_side: str, analysis_data: Dict[str, Any]) -> bool:
    """
    Save detailed analysis data to MinIO
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        detected_side: The detected side (front, left, right, back)
        analysis_data: Dictionary containing detailed analysis data
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_analysis_bucket()
        
        # Create file path: user_id/session_id/detailed_{detected_side}.json
        file_path = f"{user_id}/{session_id}/detailed_{detected_side}.json"
        
        # Convert analysis data to JSON
        json_data = json.dumps(analysis_data, indent=2, default=str)
        json_bytes = json_data.encode('utf-8')
        
        # Upload to MinIO
        minio_client.put_object(
            ANALYSIS_BUCKET,
            file_path,
            io.BytesIO(json_bytes),
            len(json_bytes),
            content_type="application/json"
        )
        
        print(f"Successfully saved detailed analysis data to {file_path}")
        return True
        
    except Exception as e:
        print(f"Error saving detailed analysis data: {str(e)}")
        return False

def get_detailed_analysis_data(user_id: str, session_id: str, detected_side: str) -> Dict[str, Any]:
    """
    Retrieve detailed analysis data from MinIO
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        detected_side: The detected side (front, left, right, back)
        
    Returns:
        Dict containing the analysis data or empty dict if not found
    """
    try:
        ensure_analysis_bucket()
        
        file_path = f"{user_id}/{session_id}/detailed_{detected_side}.json"
        
        # Download from MinIO
        response = minio_client.get_object(ANALYSIS_BUCKET, file_path)
        json_data = response.read().decode('utf-8')
        
        return json.loads(json_data)
        
    except Exception as e:
        print(f"Error retrieving detailed analysis data: {str(e)}")
        return {}

def list_analysis_files(user_id: str, session_id: str) -> List[str]:
    """
    List all analysis files for a session
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        List of file names
    """
    try:
        ensure_analysis_bucket()
        
        prefix = f"{user_id}/{session_id}/"
        objects = minio_client.list_objects(ANALYSIS_BUCKET, prefix=prefix, recursive=True)
        
        return [obj.object_name for obj in objects]
        
    except Exception as e:
        print(f"Error listing analysis files: {str(e)}")
        return []

def delete_session_analysis_data(user_id: str, session_id: str) -> bool:
    """
    Delete all analysis data for a session
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_analysis_bucket()
        
        prefix = f"{user_id}/{session_id}/"
        objects = minio_client.list_objects(ANALYSIS_BUCKET, prefix=prefix, recursive=True)
        
        for obj in objects:
            minio_client.remove_object(ANALYSIS_BUCKET, obj.object_name)
            
        print(f"Deleted all analysis data for session {session_id}")
        return True
        
    except Exception as e:
        print(f"Error deleting session analysis data: {str(e)}")
        return False
