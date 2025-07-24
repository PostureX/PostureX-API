from flask import Blueprint, request, jsonify
from src.config.database import db
from src.models.analysis import Analysis
from src.services.minio import client as minio_client
from src.services.video_upload_analysis_service import MediaAnalysisService
from src.config.websocket_config import WEBSOCKET_HOST
from flask_jwt_extended import decode_token, get_jwt_identity, jwt_required, create_access_token
import json, threading, os, tempfile, asyncio
import numpy as np
from urllib.parse import unquote

minio_hook_bp = Blueprint('minio_hook', __name__)

def get_user_token():
    """Get the user's JWT token from cookies"""
    try:
        # Get token from request cookies
        token = request.cookies.get('access_token_cookie')
        
        if not token:
            raise ValueError("No access_token_cookie found in request")
        
        # Validate the token using Flask-JWT-Extended
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token.get('sub')
            print(f"Valid token found for user: {user_id}")
            return token
        except Exception as token_error:
            raise ValueError(f"Invalid or expired token: {token_error}")
            
    except Exception as e:
        print(f"Error getting user token: {e}")
        raise ValueError(f"Invalid or missing token: {e}")

# Initialize media analysis service for webhook processing (token will be set per request)
media_analyzer = None

def get_media_analyzer_for_model(model_name, service_token):
    """Get MediaAnalysisService instance configured for the specified model"""
    try:
        # Import the model configs
        from src.config.websocket_config import MODEL_CONFIGS
        
        # Check if model exists in configuration
        if model_name not in MODEL_CONFIGS:
            print(f"Error: Model '{model_name}' not found in configuration")
            return None
            
        model_config = MODEL_CONFIGS[model_name]
        
        # Check if model is properly configured
        if model_config.get('model_config') is None or model_config.get('checkpoint_path') is None:
            print(f"Error: Model '{model_name}' is not properly configured (missing model_config or checkpoint_path)")
            return None
            
        websocket_port = model_config.get('port', 8894)
        print(f"Using model '{model_name}' on port {websocket_port}")
        
        # Create MediaAnalysisService with the correct port
        return MediaAnalysisService(
            websocket_host=WEBSOCKET_HOST, 
            websocket_port=websocket_port, 
            service_token=service_token
        )
            
    except Exception as e:
        print(f"Error getting media analyzer for model {model_name}: {str(e)}")
        return None

# Helper: parse key like 'user_id/session_id/modelname_side.mp4' -> user_id, session_id, view, model_name
def parse_minio_key(key):
    try:
        decoded_key = unquote(key)
        print(f"Original key: {key}")
        print(f"Decoded key: {decoded_key}")
        
        parts = decoded_key.split('/')
        print(f"Split parts: {parts}")
        
        if len(parts) >= 2:
            user_id = parts[0]
            # If there are 3 parts, it's user_id/session_id/modelname_view.ext (multiview)
            if len(parts) == 3:
                session_id, filename = parts[1], parts[2]
                base_name = os.path.splitext(filename)[0]  # Remove extension: 'cx_front.mp4' -> 'cx_front'
                
                # Parse modelname_view format
                if '_' in base_name:
                    model_name, view = base_name.split('_', 1)
                    print(f"Multi-view: user_id={user_id}, session_id={session_id}, view={view}, model={model_name}")
                    return user_id, session_id, view, model_name
                else:
                    # Legacy format without model prefix - default to 'cx'
                    view = base_name
                    model_name = 'cx'
                    print(f"Multi-view (legacy): user_id={user_id}, session_id={session_id}, view={view}, model={model_name}")
                    return user_id, session_id, view, model_name
            # If there are 2 parts, it's user_id/modelname_filename.ext (single view)
            else:
                filename = parts[1]
                base_name = os.path.splitext(filename)[0]  # Remove extension
                
                # Parse modelname_filename format
                if '_' in base_name:
                    model_name, original_name = base_name.split('_', 1)
                    session_id = original_name  # Use original filename as session
                    view = 'single'
                    print(f"Single view: user_id={user_id}, session_id={session_id}, view={view}, model={model_name}")
                    return user_id, session_id, view, model_name
                else:
                    # Legacy format without model prefix - default to 'cx'
                    session_id = base_name
                    view = 'single'
                    model_name = 'cx'
                    print(f"Single view (legacy): user_id={user_id}, session_id={session_id}, view={view}, model={model_name}")
                    return user_id, session_id, view, model_name
        
        print(f"Invalid key format: {key}")
        return None, None, None, None
    except Exception as e:
        print(f"Error parsing key {key}: {str(e)}")
        return None, None, None, None

# Media processing function
def process_media_in_background(user_id, session_id, view, model_name, bucket, key, app):
    with app.app_context():
        analysis = None
        try:
            print(f"Background processing started for {key} with model {model_name}")
            
            # Update status to in_progress
            analysis = Analysis.query.filter_by(user_id=user_id, filename=session_id).first()
            if analysis:
                print(f"Found analysis {analysis.id}, updating to in_progress")
                analysis.status = "in_progress"
                db.session.commit()
            
            # Determine file extension for temporary file
            file_extension = os.path.splitext(key)[1]
            
            # Download media from MinIO to temp file
            # Create temp file with proper extension but close it immediately
            # so MinIO can write to it (Windows file locking issue)
            with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            decoded_key = unquote(key)
            print(f"Downloading {decoded_key} to {tmp_path}")
            minio_client.fget_object(bucket, decoded_key, tmp_path)
            

            try:
                # Run inference on media with the specified model
                print(f"Running inference on {tmp_path} for view {view} using model {model_name}")
                result = run_inference_on_media(tmp_path, view, model_name)
                # print(f"Inference result: {result}")
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    print(f"Cleaned up temp file {tmp_path}")

            # Update Analysis row with results
            if analysis and result:
                # Check if the result contains an error
                if "error" in result:
                    print(f"Analysis failed for {analysis.id}: {result['error']}")
                    analysis.status = "failed"
                    analysis.feedback = f"Analysis failed: {result['error']}"
                    db.session.commit()
                    return
                
                print(f"Updating analysis {analysis.id} with results for view {view}")
                
                # Use database lock to prevent race conditions between concurrent webhook threads
                # Retry mechanism for handling concurrent updates
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        # Start a new transaction for each retry
                        db.session.rollback()  # Clear any existing transaction
                        
                        # Query with lock and fresh data
                        locked_analysis = db.session.query(Analysis).filter_by(
                            user_id=user_id, filename=session_id
                        ).with_for_update().first()
                        
                        if not locked_analysis:
                            print(f"Analysis not found after lock for {user_id}/{session_id}")
                            break
                        
                        # Parse existing results
                        current_results = json.loads(locked_analysis.posture_result or '{}')
                        print(f"Current results before update: {list(current_results.keys())}")

                        # Extract score, measurements, and keypoints from result
                        score = result.get("score", {})
                        measurements = result.get("measurements", {})
                        keypoints = result.get("keypoints", [])
                        side = result.get("view", "unknown")

                        # Store score, measurements, and keypoints for this view
                        if view == 'single':
                            # For single view, add "side" key to indicate the view
                            current_results[view] = {
                                "score": score,
                                "measurements": measurements,
                                "keypoints": keypoints,
                                "side": side
                            }
                        else:
                            # For multi-view, no "side" key needed
                            current_results[view] = {
                                "score": score,
                                "measurements": measurements,
                                "keypoints": keypoints
                            }
                        
                        locked_analysis.posture_result = json.dumps(current_results)

                        # Calculate progress based on expected views
                        if view == 'single':
                            expected_views = {"single"}
                        else:
                            expected_views = {"front", "left", "right", "back"}

                        done_views = set(current_results.keys())
                        print(f"View {view} processed. Done views: {done_views}, Expected: {expected_views}")

                        # Mark as completed if all expected views are done
                        if expected_views.issubset(done_views):
                            locked_analysis.status = "completed"
                            locked_analysis.feedback = generate_feedback(current_results)
                            print(f"Analysis {locked_analysis.id} completed!")
                        else:
                            locked_analysis.status = "in_progress"
                            print(f"Analysis {locked_analysis.id} still in progress")

                        # Commit the transaction
                        db.session.commit()
                        print(f"Database updated for analysis {locked_analysis.id} - view {view} successful")
                        break  # Success, exit retry loop
                        
                    except Exception as db_error:
                        retry_count += 1
                        print(f"Database update error (attempt {retry_count}/{max_retries}): {str(db_error)}")
                        db.session.rollback()
                        
                        if retry_count >= max_retries:
                            print(f"Failed to update database after {max_retries} attempts")
                            raise db_error
                        else:
                            # Brief delay before retry
                            import time
                            time.sleep(0.1 * retry_count)  # Exponential backoff
            
        except Exception as e:
            print(f"Error processing media: {str(e)}")
            import traceback
            traceback.print_exc()
            if analysis:
                analysis.status = "failed"
                db.session.commit()

def run_inference_on_media(file_path, view, model_name):
    """Run pose inference on media file (image or video) using WebSocket service"""
    try:
        print(f"Starting WebSocket analysis for webhook processing: {file_path} with model {model_name}")
        
        # Get media analyzer configured for the specified model
        from flask_jwt_extended import create_access_token
        service_token = create_access_token(identity="webhook_service", expires_delta=None)
        
        analyzer = get_media_analyzer_for_model(model_name, service_token)
        if analyzer is None:
            error_msg = f"Model '{model_name}' is not available or not properly configured"
            print(f"Error: {error_msg}")
            return {"error": error_msg, "view": view, "model": model_name}
        
        # Determine file type
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Use actual WebSocket inference service (need to run async methods synchronously)
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if file_extension in ['.jpg', '.jpeg', '.png']:
                # Image analysis
                result = loop.run_until_complete(analyzer.analyze_image(file_path, view))
            else:
                # Video analysis 
                result = loop.run_until_complete(analyzer.analyze_video(file_path, view))
                
        finally:
            loop.close()
        
        # Transform WebSocket result to match expected webhook format
        if "error" in result:
            return {"error": result["error"], "view": view, "model": model_name}
            
        webhook_result = {
            "score": result.get("score", {}),
            "measurements": result.get("measurements", {}),
            "keypoints": result.get("keypoints", []),
            "view": result.get("detected_view", view),
            "model": model_name,
            "file_type": "image" if file_extension in ['.jpg', '.jpeg', '.png'] else "video",
            "frame_count": result.get("frame_count", 1)
        }
        
        return webhook_result
            
    except Exception as e:
        print(f"Error during WebSocket analysis: {str(e)}")
        return {"error": f"WebSocket analysis failed: {str(e)}", "view": view, "model": model_name}

def generate_feedback(score_dict):
    """Generate feedback based on posture scores"""
    feedback_parts = []
    
    for view, data in score_dict.items():
        if isinstance(data, dict) and "score" in data:
            score = data["score"]
            
            # Look for overall_score in the score dictionary
            if isinstance(score, dict) and "overall_score" in score:
                overall = score["overall_score"]
            else:
                continue  # Skip if no overall_score found
                
            if overall >= 90:
                feedback_parts.append(f"{view.title()} view: Excellent posture!")
            elif overall >= 80:
                feedback_parts.append(f"{view.title()} view: Good posture with minor improvements needed.")
            elif overall >= 70:
                feedback_parts.append(f"{view.title()} view: Fair posture, consider adjustments.")
            else:
                feedback_parts.append(f"{view.title()} view: Poor posture, significant improvements needed.")
    
    return " ".join(feedback_parts)

@minio_hook_bp.route('/webhook', methods=['POST'])
def minio_webhook():
    """Handle MinIO webhook notifications for media uploads (images and videos)"""
    try:
        # For webhook processing, we'll use a service token since MinIO webhooks don't have user cookies
        # We'll create a service token for internal webhook processing
        from flask_jwt_extended import create_access_token
        service_token = create_access_token(identity="webhook_service", expires_delta=None)
        
        data = request.get_json()
        
        for record in data.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Only process videos bucket (now handles both images and videos)
            if bucket != 'videos':
                print(f"Skipping non-videos bucket: {bucket}")
                continue

            user_id, session_id, view, model_name = parse_minio_key(key)
            if not all([user_id, session_id, view, model_name]):
                print(f"Invalid key format, skipping: {key}")
                continue
            
            print(f"Processing {key} with model: {model_name}")
            
            # Initialize media analyzer with the correct model
            global media_analyzer
            media_analyzer = get_media_analyzer_for_model(model_name, service_token)
            
            if media_analyzer is None:
                print(f"Failed to initialize media analyzer for model: {model_name}. Skipping processing.")
                continue
            
            # Find or create Analysis row
            analysis = Analysis.query.filter_by(user_id=user_id, filename=session_id).first()
            if not analysis:
                print(f"Creating new analysis for user_id={user_id}, session_id={session_id}")
                analysis = Analysis(
                    user_id=user_id,
                    filename=session_id, #Would just be the filename for single view
                    posture_result=json.dumps({}),
                    feedback="",
                    status="pending",
                )
                db.session.add(analysis)
                db.session.commit()
                print(f"Analysis created with ID: {analysis.id}")
            else:
                print(f"Found existing analysis with ID: {analysis.id}")
            
            # Start background processing
            print(f"Starting background thread for {key}, view={view}, model={model_name}")
            from flask import current_app
            threading.Thread(
                target=process_media_in_background, 
                args=(user_id, session_id, view, model_name, bucket, key, current_app._get_current_object()),
                daemon=True
            ).start()
        
        return jsonify({"message": "Processing started", "processed_count": len(data.get('Records', []))}), 202
        
    except Exception as e:
        print(f"ERROR in webhook handler: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@minio_hook_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook functionality"""
    data = request.get_json()
    return jsonify({"message": "Webhook received", "data": data}), 200

@minio_hook_bp.route('/test/parse', methods=['POST'])
def test_parse_key():
    """Test endpoint for parsing MinIO keys"""
    data = request.get_json()
    key = data.get('key', '')
    
    if not key:
        return jsonify({"error": "No key provided"}), 400
    
    user_id, session_id, view, model_name = parse_minio_key(key)
    
    return jsonify({
        "original_key": key,
        "parsed": {
            "user_id": user_id,
            "session_id": session_id,
            "view": view,
            "model_name": model_name
        }
    }), 200