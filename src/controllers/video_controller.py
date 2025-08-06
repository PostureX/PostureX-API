from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from src.services.minio import client as minio_client
from src.config.database import db
from src.models.analysis import Analysis
import os

video_bp = Blueprint("video", __name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
BUCKET_NAME = "videos"


def ensure_bucket():
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)


@video_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_media():
    """Upload 1-4 media files for posture analysis (supports front, left, right, back views)"""
    user_id = str(get_jwt_identity())

    # Get required session_id
    session_id = request.form.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    # Check if session_id already exists for this user
    folder_prefix = f"{user_id}/{session_id}/"
    ensure_bucket()
    existing_objects = list(
        minio_client.list_objects(BUCKET_NAME, prefix=folder_prefix, recursive=True)
    )
    if existing_objects:
        return (
            jsonify(
                {
                    "error": "session_id already exists",
                    "message": f"Session '{session_id}' already exists for this user. Please use a different session_id or delete the existing session first.",
                    "existing_files": [obj.object_name for obj in existing_objects],
                }
            ),
            409,
        )  # Conflict status code

    # Get optional model parameter (defaults to 'cx')
    model_id = request.form.get("model")
    if not model_id:
        return jsonify({"error": "model is required"}), 400

    # Validate model
    available_models = ["cx", "gy"]
    if model_id not in available_models:
        return (
            jsonify(
                {
                    "error": f"Invalid model: {model_id}. Available models: {available_models}"
                }
            ),
            400,
        )

    # Validate file types
    allowed_extensions = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
    }

    # Supported views (user must specify the actual view)
    supported_views = ["front", "left", "right", "back"]

    uploaded_files = {}
    errors = []

    # Check if any files are provided
    if not request.files:
        return jsonify({"error": "No files provided"}), 400

    # Create analysis record in database BEFORE uploading files to prevent race condition
    try:
        new_analysis = Analysis(
            user_id=user_id,
            session_id=session_id,
            model_name=model_id,
            status="pending",  # Initial status before processing starts
        )
        db.session.add(new_analysis)
        db.session.commit()
        
        analysis_id = new_analysis.id
        print(f"Created analysis record with ID: {analysis_id}")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating analysis record: {str(e)}")
        return jsonify({"error": f"Failed to create analysis record: {str(e)}"}), 500

    # Process each file in the request
    for field_name, file in request.files.items():
        if file.filename == "":
            errors.append(f"No file selected for {field_name}")
            continue

        # Determine view from field name
        view = field_name.lower()
        if view not in supported_views:
            errors.append(
                f"Unsupported view: {view}. Supported views: {supported_views}"
            )
            continue

        # Validate file type
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            errors.append(f"Unsupported file type for {view}: {file_ext}")
            continue

        # Create MinIO path: user_id/session_id/modelname_view.ext
        minio_path = f"{user_id}/{session_id}/{model_id}_{view}{file_ext}"

        try:
            ensure_bucket()
            file.seek(0)
            minio_client.put_object(
                BUCKET_NAME,
                minio_path,
                file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type=file.mimetype,
            )

            uploaded_files[view] = {
                "file_url": f"http://{MINIO_ENDPOINT}/{BUCKET_NAME}/{minio_path}",
                "filename": f"{model_id}_{view}{file_ext}",
                "original_filename": file.filename,
                "model": model_id,
                "view": view,
                "file_type": (
                    "video"
                    if file_ext
                    in {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
                    else "image"
                ),
            }

        except Exception as e:
            errors.append(f"Failed to upload {view}: {str(e)}")

    # Validate that at least one file was uploaded successfully
    if not uploaded_files:
        # If no files were uploaded successfully, delete the analysis record
        try:
            db.session.delete(new_analysis)
            db.session.commit()
        except Exception as cleanup_error:
            print(f"Error cleaning up analysis record: {str(cleanup_error)}")
        
        return (
            jsonify(
                {"error": "No files were uploaded successfully", "details": errors}
            ),
            400,
        )

    # Return results
    if errors:
        return (
            jsonify(
                {
                    "message": f"Partial upload success. {len(uploaded_files)} files uploaded.",
                    "uploaded_files": uploaded_files,
                    "errors": errors,
                    "session_id": session_id,
                    "model": model_id,
                    "analysis_id": analysis_id,
                    "views_uploaded": list(uploaded_files.keys()),
                }
            ),
            207,
        )  # Multi-status
    else:
        return (
            jsonify(
                {
                    "message": f"All files uploaded successfully. {len(uploaded_files)} files uploaded. Analysis will begin automatically.",
                    "uploaded_files": uploaded_files,
                    "session_id": session_id,
                    "model": model_id,
                    "analysis_id": analysis_id,
                    "views_uploaded": list(uploaded_files.keys()),
                }
            ),
            201,
        )


@video_bp.route("/delete", methods=["POST"])
@jwt_required()
def delete_session():
    """Delete all files for a session_id"""
    user_id = str(get_jwt_identity())
    data = request.get_json()

    if not data or "session_id" not in data:
        return jsonify({"error": "Missing session_id"}), 400

    session_id = data["session_id"]
    folder_prefix = f"{user_id}/{session_id}/"

    ensure_bucket()
    try:
        # List all objects in the session folder
        objects = minio_client.list_objects(
            BUCKET_NAME, prefix=folder_prefix, recursive=True
        )
        object_names = [obj.object_name for obj in objects]

        if not object_names:
            return jsonify({"message": "No files found to delete"}), 404

        # Delete all files in the session
        deleted_files = []
        for minio_path in object_names:
            try:
                minio_client.remove_object(BUCKET_NAME, minio_path)
                deleted_files.append(minio_path)
            except Exception as e:
                return (
                    jsonify({"error": f"Failed to delete {minio_path}: {str(e)}"}),
                    500,
                )

        return (
            jsonify(
                {
                    "message": f"Session deleted successfully. Removed {len(deleted_files)} files.",
                    "session_id": session_id,
                    "deleted_files": deleted_files,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
