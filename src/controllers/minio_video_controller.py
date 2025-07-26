from flask import Blueprint, request, jsonify
from src.config.database import db
from src.models.analysis import Analysis
from src.services.minio import client as minio_client
from src.services.video_upload_analysis_service import MediaAnalysisService
from src.config.websocket_config import WEBSOCKET_HOST
from flask_jwt_extended import decode_token, get_jwt_identity, jwt_required, create_access_token
from urllib.parse import unquote
import os
import json
import tempfile
import threading
import time
import traceback
import asyncio

minio_hook_bp = Blueprint('minio_hook', __name__)

def get_media_analyzer_for_model(model_name, service_token):
    """Get MediaAnalysisService instance configured for the specified model"""
    try:
        from src.config.websocket_config import MODEL_CONFIGS
        
        if model_name not in MODEL_CONFIGS:
            print(f"Error: Model '{model_name}' not found in configuration")
            return None
            
        model_config = MODEL_CONFIGS[model_name]
        
        if model_config.get('model_config') is None or model_config.get('checkpoint_path') is None:
            print(f"Error: Model '{model_name}' is not properly configured")
            return None
            
        websocket_port = model_config.get('port', 8894)
        print(f"Using model '{model_name}' on port {websocket_port}")
        
        return MediaAnalysisService(
            websocket_host=WEBSOCKET_HOST, 
            websocket_port=websocket_port, 
            service_token=service_token
        )
            
    except Exception as e:
        print(f"Error getting media analyzer for model {model_name}: {str(e)}")
        return None

def parse_minio_key(key):
    """Parse MinIO key to extract user_id, session_id, view, and model_name"""
    try:
        decoded_key = unquote(key)
        print(f"Parsing key: {decoded_key}")
        
        parts = decoded_key.split('/')
        
        if len(parts) == 3:  # user_id/session_id/model_view.ext
            user_id, session_id, filename = parts
            base_name = os.path.splitext(filename)[0]
            
            if '_' in base_name:
                model_name, view = base_name.split('_', 1)
                print(f"Parsed: user_id={user_id}, session_id={session_id}, view={view}, model={model_name}")
                return user_id, session_id, view, model_name
        
        print(f"Invalid key format: {key}")
        return None, None, None, None
        
    except Exception as e:
        print(f"Error parsing key {key}: {str(e)}")
        return None, None, None, None

def run_inference_on_media(file_path, view, model_name):
    """Run pose inference on media file using WebSocket service"""
    try:
        print(f"Starting inference for: {file_path} with model {model_name}")
        
        service_token = create_access_token(identity="webhook_service", expires_delta=None)
        analyzer = get_media_analyzer_for_model(model_name, service_token)
        
        if analyzer is None:
            return {"error": f"Model '{model_name}' not available", "view": view}
        
        file_extension = os.path.splitext(file_path)[1].lower()
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if file_extension in ['.jpg', '.jpeg', '.png']:
                result = loop.run_until_complete(analyzer.analyze_image(file_path, view))
            else:
                result = loop.run_until_complete(analyzer.analyze_video(file_path, view))
                
        finally:
            loop.close()
        
        if "error" in result:
            return result
            
        return {
            "score": result.get("score", {}),
            "measurements": result.get("measurements", {}),
            "keypoints": result.get("keypoints", []),
            "view": result.get("detected_view", view),
            "model": model_name,
            "file_type": "image" if file_extension in ['.jpg', '.jpeg', '.png'] else "video"
        }
            
    except Exception as e:
        print(f"Error during inference: {str(e)}")
        return {"error": f"Inference failed: {str(e)}", "view": view}

def create_view_result_structure(result):
    """Create standardized view result structure"""
    return {
        "score": {
            "knee_angle": result.get("score", {}).get("knee_angle", "unknown"),
            "head_tilt": result.get("score", {}).get("head_tilt", "unknown"),
            "arm_angle": result.get("score", {}).get("arm_angle", "unknown"),
            "arm_bent_angle": result.get("score", {}).get("arm_bent_angle", "unknown"),
            "leg_spread": result.get("score", {}).get("leg_spread", "unknown"),
            "back_angle": result.get("score", {}).get("back_angle", "unknown")
        },
        "measurements": {
            "knee_angle": result.get("measurements", {}).get("knee_angle", "unknown"),
            "head_tilt": result.get("measurements", {}).get("head_tilt", "unknown"),
            "arm_angle": result.get("measurements", {}).get("arm_angle", "unknown"),
            "arm_bent_angle": result.get("measurements", {}).get("arm_bent_angle", "unknown"),
            "leg_spread": result.get("measurements", {}).get("leg_spread", "unknown"),
            "back_angle": result.get("measurements", {}).get("back_angle", "unknown")
        },
        "keypoints": result.get("keypoints", [])
    }

def process_session_files(user_id, session_id, model_name, app):
    """Process all files in a session folder and aggregate results"""
    with app.app_context():
        try:
            print(f"Processing session: {user_id}/{session_id} with model {model_name}")
            
            # Find or create analysis record
            analysis = Analysis.query.filter_by(user_id=user_id, filename=session_id).first()
            if not analysis:
                analysis = Analysis(
                    user_id=user_id,
                    filename=session_id,
                    posture_result="{}",
                    feedback="",
                    status="in_progress"
                )
                db.session.add(analysis)
                db.session.commit()
            else:
                analysis.status = "in_progress"
                db.session.commit()
            
            # List all files in the session folder
            folder_prefix = f"{user_id}/{session_id}/"
            objects = list(minio_client.list_objects('videos', prefix=folder_prefix, recursive=True))
            
            if not objects:
                analysis.status = "failed"
                analysis.feedback = "No files found in session"
                db.session.commit()
                return
            
            print(f"Found {len(objects)} files in session")
            
            # Process each file
            session_results = {}
            
            for obj in objects:
                file_key = obj.object_name
                filename = os.path.basename(file_key)
                base_name = os.path.splitext(filename)[0]
                
                # Extract view from filename (format: model_view)
                if '_' in base_name:
                    _, view = base_name.split('_', 1)
                else:
                    # Skip files that don't follow the expected format
                    print(f"Skipping file with invalid format: {filename}")
                    continue
                
                print(f"Processing file {filename} for view {view}")
                
                # Download and process file
                file_extension = os.path.splitext(file_key)[1]
                with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                
                try:
                    decoded_key = unquote(file_key)
                    minio_client.fget_object('videos', decoded_key, tmp_path)
                    
                    # Run inference
                    result = run_inference_on_media(tmp_path, view, model_name)
                    
                    if "error" not in result:
                        session_results[view] = result
                        print(f"Successfully processed {view}")
                    else:
                        print(f"Error processing {view}: {result['error']}")
                        
                except Exception as e:
                    print(f"Error processing file {file_key}: {str(e)}")
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            
            # Update analysis with results
            if session_results:
                # Create simplified format with only uploaded views
                simplified_results = {}
                
                for view, result in session_results.items():
                    simplified_results[view] = create_view_result_structure(result)
                
                feedback = generate_session_feedback(session_results)
                
                analysis.posture_result = json.dumps(simplified_results)
                analysis.feedback = feedback
                analysis.status = "completed"
                db.session.commit()
                
                print(f"Session analysis completed for {session_id}")
            else:
                analysis.status = "failed"
                analysis.feedback = "All files failed to process"
                db.session.commit()
                print(f"Session analysis failed for {session_id}")
                
        except Exception as e:
            print(f"Error processing session: {str(e)}")
            traceback.print_exc()
            if 'analysis' in locals():
                analysis.status = "failed"
                analysis.feedback = f"Processing error: {str(e)}"
                db.session.commit()

def generate_session_feedback(session_results):
    """Generate feedback based on all views in the session"""
    feedback_parts = []
    
    for view, result in session_results.items():
        if "score" in result:
            scores = result["score"]
            
            if isinstance(scores, dict):
                score_values = [v for v in scores.values() if isinstance(v, (int, float))]
                if score_values:
                    avg_score = sum(score_values) / len(score_values) * 100
                    
                    if avg_score >= 90:
                        feedback_parts.append(f"{view.title()} view: Excellent posture!")
                    elif avg_score >= 80:
                        feedback_parts.append(f"{view.title()} view: Good posture with minor improvements needed.")
                    elif avg_score >= 70:
                        feedback_parts.append(f"{view.title()} view: Fair posture, consider adjustments.")
                    else:
                        feedback_parts.append(f"{view.title()} view: Poor posture, significant improvements needed.")
    
    if not feedback_parts:
        return "Analysis completed but no feedback could be generated."
    
    return " ".join(feedback_parts)

def delayed_session_processing(user_id, session_id, model_name, app):
    """Wrapper function for delayed session processing"""
    process_session_files(user_id, session_id, model_name, app)

@minio_hook_bp.route('/webhook', methods=['POST'])
def minio_webhook():
    """Handle MinIO webhook notifications for media uploads"""
    try:
        data = request.get_json()
        
        # Track sessions that need processing (to avoid duplicate processing)
        sessions_to_process = set()
        
        for record in data.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            if bucket != 'videos':
                continue

            user_id, session_id, view, model_name = parse_minio_key(key)
            if not all([user_id, session_id, view, model_name]):
                continue
            
            session_key = (user_id, session_id, model_name)
            sessions_to_process.add(session_key)
        
        # Process each unique session
        for user_id, session_id, model_name in sessions_to_process:
            print(f"Starting session processing: {user_id}/{session_id} with model {model_name}")
            
            from flask import current_app
            # Capture the app object before starting the timer
            app = current_app._get_current_object()
            
            # Add a small delay to allow all files to be uploaded
            threading.Timer(
                2.0,  # 2 second delay
                delayed_session_processing,
                args=(user_id, session_id, model_name, app)
            ).start()
        
        return jsonify({
            "message": "Processing started", 
            "sessions_queued": len(sessions_to_process)
        }), 202
        
    except Exception as e:
        print(f"ERROR in webhook handler: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
