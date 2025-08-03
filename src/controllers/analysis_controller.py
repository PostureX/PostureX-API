from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.config.database import db
from src.models.analysis import Analysis
import threading
from src.config.websocket_config import MODEL_CONFIGS
from src.controllers.minio_video_controller import process_session_files
from src.services.analysis_bucket_minio import get_detailed_analysis_data, list_analysis_files, delete_session_analysis_data, save_feedback_data, get_feedback_file_path
from src.services.video_upload_analysis_service import delete_session_video_files
from src.services.minio import get_session_presigned_urls

from src.services.analysis_bucket_minio import ANALYSIS_BUCKET
from src.services.minio import client as minio_client
from datetime import timedelta

analysis_bp = Blueprint("analysis", __name__)


class AnalysisController:
    """Controller for analysis-related operations"""

    def save_analysis(self, user_id, session_id, feedback_data):
        """Save analysis results to database and feedback to MinIO"""
        try:
            # Create new analysis record without feedback
            new_analysis = Analysis(
                user_id=user_id,
                session_id=session_id,
            )
           
            db.session.add(new_analysis)
            db.session.commit()

            # Save feedback data to MinIO as a single file for all sides
            feedback_saved = save_feedback_data(str(user_id), session_id, feedback_data)

            return {
                "message": "Analysis saved successfully",
                "analysis_id": new_analysis.id,
                "feedback_saved": feedback_saved,
            }, 201

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    def get_all_analyses(self, user_id):
        """Get all analyses for a user with presigned URLs for media files and analysis JSON files"""
        try:
            analyses = (
                Analysis.query.filter_by(user_id=user_id)
                .order_by(Analysis.created_at.desc())
                .all()
            )
            
            result = []
            for analysis in analyses:
                analysis_dict = analysis.to_dict()
                
                # Get presigned URLs for media files (videos/images)
                analysis_dict["uploads"] = get_session_presigned_urls(str(user_id), analysis.session_id)
                
                # Get presigned URLs for analysis JSON files
                analysis_dict["analysis_json_urls"] = self._get_session_analysis_json_urls(str(user_id), analysis.session_id)
                
                # Get presigned URLs for feedback JSON files
                analysis_dict["feedback_json_url"] = self._get_session_feedback_json_url(str(user_id), analysis.session_id)
                
                result.append(analysis_dict)
            
            return result, 200

        except Exception as e:
            return {"error": str(e)}, 500

    def get_analysis_by_id(self, user_id, analysis_id):
        """Get detailed analysis by ID with presigned URLs for media files and analysis JSON files"""
        try:
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()

            if not analysis:
                return {"error": "Analysis not found"}, 404

            analysis_dict = analysis.to_dict()
            
            # Get presigned URLs for media files (videos/images)
            analysis_dict["uploads"] = get_session_presigned_urls(str(user_id), analysis.session_id)
            
            # Get presigned URLs for analysis JSON files
            analysis_dict["analysis_json_urls"] = self._get_session_analysis_json_urls(str(user_id), analysis.session_id)
            
            # Get presigned URLs for feedback JSON files
            analysis_dict["feedback_json_url"] = self._get_session_feedback_json_url(str(user_id), analysis.session_id)
            
            return analysis_dict, 200

        except Exception as e:
            return {"error": str(e)}, 500

    def _get_session_analysis_json_urls(self, user_id: str, session_id: str) -> dict:
        """Helper method to get presigned URLs for analysis JSON files"""
        try:
            # Get list of available analysis files
            files = list_analysis_files(user_id, session_id)
            json_urls = {}
            
            for file_path in files:
                if "detailed_" in file_path and file_path.endswith(".json"):
                    # Extract side name from filename (e.g., "detailed_left.json" -> "left")
                    filename = file_path.split("/")[-1]
                    side = filename.replace("detailed_", "").replace(".json", "")
                    
                    # Generate presigned URL for this JSON file
                    try:
                        url = minio_client.presigned_get_object(
                            ANALYSIS_BUCKET,
                            file_path,
                            expires=timedelta(hours=1)
                        )
                        json_urls[side] = url
                    except Exception as e:
                        print(f"Error generating presigned URL for {file_path}: {e}")
                        continue
            
            return json_urls
            
        except Exception as e:
            print(f"Error getting session analysis JSON URLs: {str(e)}")
            return {}

    def _get_session_feedback_json_url(self, user_id: str, session_id: str) -> str:
        """Helper method to get presigned URL for the feedback JSON file"""
        try:
            # Check if feedback file exists
            file_path = get_feedback_file_path(user_id, session_id)
            
            if not file_path:
                return ""
            
            # Generate presigned URL for the feedback JSON file
            try:
                url = minio_client.presigned_get_object(
                    ANALYSIS_BUCKET,
                    file_path,
                    expires=timedelta(hours=1)
                )
                return url
            except Exception as e:
                print(f"Error generating presigned URL for {file_path}: {e}")
                return ""
            
        except Exception as e:
            print(f"Error getting session feedback JSON URL: {str(e)}")
            return ""

    def reattempt_analysis(self, user_id, analysis_id, model_name=None):
        """Re-attempt analysis by re-processing the session files with specified model"""
        try:
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()

            if not analysis:
                return {"error": "Analysis not found"}, 404

            # Validate model name if provided
            if model_name:
                if model_name not in MODEL_CONFIGS:
                    available_models = list(MODEL_CONFIGS.keys())
                    return {
                        "error": f"Invalid model: {model_name}. Available models: {available_models}",
                        "available_models": available_models
                    }, 400
            else:
                return {"error": "Model name is required for re-attempt"}, 400

            # Update status to in_progress
            analysis.status = "in_progress"
            db.session.commit()

            # Start background processing with specified model
            app = current_app._get_current_object()
            threading.Thread(
                target=self._process_session_files_background,
                args=(user_id, analysis.session_id, model_name, app, analysis_id)
            ).start()

            return {
                "message": "Analysis re-attempting",
                "analysis_id": analysis_id,
                "model": model_name,
                "status": "in_progress"
            }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    def _process_session_files_background(self, user_id, session_id, model_name, app, analysis_id):
        """Background processing of session files"""
        try:
            with app.app_context():
                print(f"Re-processing analysis {analysis_id} for session {session_id}")
                process_session_files(user_id, session_id, model_name, app)
                print(f"Completed re-processing analysis {analysis_id}")
                
        except Exception as e:
            with app.app_context():
                print(f"Error in background processing for analysis {analysis_id}: {str(e)}")
                # Update analysis status to failed
                analysis = Analysis.query.get(analysis_id)
                if analysis:
                    analysis.status = "failed"
                    db.session.commit()
    #Not needed right now
    # def get_detailed_analysis_api(self, user_id, session_id, detected_side=None):
    #     """Get detailed analysis data from MinIO for API endpoints"""
    #     try:
    #         if detected_side:
    #             # Get specific side data
    #             detailed_data = get_detailed_analysis_data(str(user_id), session_id, detected_side)
    #             if not detailed_data:
    #                 return {"error": f"No detailed data found for {detected_side} side"}, 404
    #             return detailed_data, 200
    #         else:
    #             # List all available analysis files for the session
    #             files = list_analysis_files(str(user_id), session_id)
    #             if not files:
    #                 return {"error": "No detailed analysis data found for this session"}, 404
                
    #             # Extract sides from file names
    #             sides = []
    #             for file_path in files:
    #                 if "detailed_" in file_path and file_path.endswith(".json"):
    #                     filename = file_path.split("/")[-1]  # Get filename
    #                     side = filename.replace("detailed_", "").replace(".json", "")
    #                     sides.append(side)
                
    #             return {"available_sides": sides, "files": files}, 200

    #     except Exception as e:
    #         return {"error": str(e)}, 500

    def delete_analysis(self, user_id, analysis_id):
        """Delete analysis by ID and associated analysis files from MinIO"""
        try:
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()

            if not analysis:
                return {"error": "Analysis not found"}, 404

            # Store session_id for MinIO cleanup before deleting the database record
            session_id = analysis.session_id

            # Delete from database first
            db.session.delete(analysis)
            db.session.commit()

            # Delete associated analysis files from MinIO analysis-data bucket
            analysis_deletion_success = delete_session_analysis_data(str(user_id), session_id)
            
            # Delete associated video files from MinIO videos bucket
            video_deletion_success = delete_session_video_files(str(user_id), session_id)
            
            # Determine response based on deletion results
            if analysis_deletion_success and video_deletion_success:
                return {
                    "message": "Analysis, analysis files, and video files deleted successfully",
                    "analysis_id": analysis_id,
                    "session_id": session_id
                }, 200
            elif analysis_deletion_success and not video_deletion_success:
                return {
                    "message": "Analysis and analysis files deleted successfully, but some video files may remain",
                    "analysis_id": analysis_id,
                    "session_id": session_id,
                    "warning": "Failed to delete some video files from MinIO"
                }, 200
            elif not analysis_deletion_success and video_deletion_success:
                return {
                    "message": "Analysis and video files deleted successfully, but some analysis files may remain",
                    "analysis_id": analysis_id,
                    "session_id": session_id,
                    "warning": "Failed to delete some analysis files from MinIO"
                }, 200
            else:
                return {
                    "message": "Analysis deleted from database, but some files may remain in storage",
                    "analysis_id": analysis_id,
                    "session_id": session_id,
                    "warning": "Failed to delete some analysis files and video files from MinIO"
                }, 200

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500


# Initialize controller
analysis_controller = AnalysisController()


@analysis_bp.route("/save", methods=["POST"])
@jwt_required()
def save_analysis():
    """Save analysis results with feedback stored in MinIO"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not all(k in data for k in ('session_id', 'feedback')):
        return jsonify({"error": "Missing required fields"}), 400

    result, status = analysis_controller.save_analysis(
        user_id,
        data['session_id'],
        data['feedback'],  # This should now be a dict with side-based feedback
    )
    return jsonify(result), status


@analysis_bp.route("/list", methods=["GET"])
@jwt_required()
def list_analyses():
    """Get all analyses for current user"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_all_analyses(user_id)
    return jsonify(result), status

@analysis_bp.route("/retry/<int:analysis_id>", methods=["POST"])
@jwt_required()
def reattempt_analysis(analysis_id):
    """Re-attempt analysis by re-processing session files with optional model selection"""
    user_id = int(get_jwt_identity())
    
    # Get model from request body (optional)
    data = request.get_json() or {}
    model_name = data.get('model')
    if model_name and not isinstance(model_name, str):
        return jsonify({"error": "Model name either missing or isn't a string"}), 400
    
    result, status = analysis_controller.reattempt_analysis(user_id, analysis_id, model_name)
    return jsonify(result), status


@analysis_bp.route("/<int:analysis_id>", methods=["GET"])
@jwt_required()
def get_analysis(analysis_id):
    """Get specific analysis by ID with full detailed data, presigned URLs, and frame-by-frame results"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_analysis_by_id(user_id, analysis_id)
    return jsonify(result), status


@analysis_bp.route("/<int:analysis_id>", methods=["DELETE"])
@jwt_required()
def delete_analysis(analysis_id):
    """Delete specific analysis by ID"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.delete_analysis(user_id, analysis_id)
    return jsonify(result), status
