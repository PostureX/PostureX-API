from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from src.services.minio import client as minio_client
import os

video_bp = Blueprint('video', __name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
BUCKET_NAME = "videos"

def ensure_bucket():
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)

@video_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_media():
    """Upload single image or video file"""
    user_id = str(get_jwt_identity())
    
    # Check for file in request
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Get optional model parameter (defaults to 'cx')
    model_id = request.form.get('model', 'cx')
    
    # Validate model (you can expand this list as needed)
    available_models = ['cx', 'gy']
    if model_id not in available_models:
        return jsonify({"error": f"Invalid model: {model_id}. Available models: {available_models}"}), 400
    
    # Validate file type
    allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', 
                         '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in allowed_extensions:
        return jsonify({"error": f"Unsupported file type: {file_ext}"}), 400
    
    filename = secure_filename(file.filename)
    
    # Format filename as modelname_originalname for single uploads
    base_name, ext = os.path.splitext(filename)
    model_filename = f"{model_id}_{base_name}{ext}"
    minio_path = f"{user_id}/{model_filename}"
    
    ensure_bucket()
    file.seek(0)
    minio_client.put_object(
        BUCKET_NAME,
        minio_path,
        file,
        length=-1,
        part_size=10*1024*1024,
        content_type=file.mimetype
    )
    
    file_url = f"http://{MINIO_ENDPOINT}/{BUCKET_NAME}/{minio_path}"
    
    return jsonify({
        "file_url": file_url,
        "filename": model_filename,
        "original_filename": filename,
        "model": model_id,
        "file_type": "video" if file_ext in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'} else "image",
        "message": "File uploaded successfully. Analysis will begin automatically."
    }), 201

@video_bp.route('/upload/multiview', methods=['POST'])
@jwt_required()
def upload_multi_view():
    """Upload multiple files for multi-view posture analysis (front, left, right, back)"""
    user_id = str(get_jwt_identity())
    
    # Get session_id (required for multi-view)
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({"error": "session_id is required for multi-view uploads"}), 400
    
    # Get optional model parameter (defaults to 'cx')
    model_id = request.form.get('model', 'cx')
    
    # Validate model
    available_models = ['cx', 'gy']
    if model_id not in available_models:
        return jsonify({"error": f"Invalid model: {model_id}. Available models: {available_models}"}), 400
    
    # Expected views
    expected_views = ['front', 'left', 'right', 'back']
    uploaded_files = {}
    errors = []
    
    # Process each view
    for view in expected_views:
        if view not in request.files:
            errors.append(f"Missing file for {view} view")
            continue
            
        file = request.files[view]
        if file.filename == '':
            errors.append(f"No file selected for {view} view")
            continue
        
        # Validate file type
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', 
                             '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            errors.append(f"Unsupported file type for {view}: {file_ext}")
            continue
        
        # Upload to MinIO with model prefix in filename
        # Format: modelname_side.ext for multiview uploads
        minio_path = f"{user_id}/{session_id}/{model_id}_{view}{file_ext}"
        
        try:
            ensure_bucket()
            file.seek(0)
            minio_client.put_object(
                BUCKET_NAME,
                minio_path,
                file,
                length=-1,
                part_size=10*1024*1024,
                content_type=file.mimetype
            )
            
            uploaded_files[view] = {
                "file_url": f"http://{MINIO_ENDPOINT}/{BUCKET_NAME}/{minio_path}",
                "filename": f"{model_id}_{view}{file_ext}",
                "model": model_id,
                "file_type": "video" if file_ext in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'} else "image"
            }
            
        except Exception as e:
            errors.append(f"Failed to upload {view}: {str(e)}")
    
    # Return results
    if errors and not uploaded_files:
        return jsonify({"error": "All uploads failed", "details": errors}), 400
    elif errors:
        return jsonify({
            "message": "Partial upload success",
            "uploaded_files": uploaded_files,
            "errors": errors,
            "session_id": session_id,
            "model": model_id
        }), 207  # Multi-status
    else:
        return jsonify({
            "message": "All files uploaded successfully. Analysis will begin automatically.",
            "uploaded_files": uploaded_files,
            "session_id": session_id,
            "model": model_id,
            "views_uploaded": list(uploaded_files.keys())
        }), 201

@video_bp.route('/delete', methods=['POST'])
@jwt_required()
def delete_video():
    user_id = str(get_jwt_identity())
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({"error": "Missing filename"}), 400
    filename = data['filename']
    minio_path = f"{user_id}/{filename}"
    ensure_bucket()
    try:
        minio_client.remove_object(BUCKET_NAME, minio_path)
        return jsonify({"message": "Video deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@video_bp.route('/delete/multiview', methods=['POST'])
@jwt_required()
def delete_multiview():
    user_id = str(get_jwt_identity())
    data = request.get_json()
    if not data or 'session_id' not in data:
        return jsonify({"error": "Missing session_id"}), 400
    session_id = data['session_id']
    folder_prefix = f"{user_id}/{session_id}/"
    ensure_bucket()
    try:
        objects = minio_client.list_objects(BUCKET_NAME, prefix=folder_prefix, recursive=True)
        object_names = [obj.object_name for obj in objects]

        if not object_names:
            return jsonify({"message": "No files found to delete"}), 404
        
        for minio_path in object_names:
            try:
                minio_client.remove_object(BUCKET_NAME, minio_path)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"message": f"Multi-view session deleted successfully. Removed {len(object_names)} files: {object_names}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500