import asyncio
import json
import os
import tempfile
import threading
import traceback
from datetime import timedelta
from urllib.parse import unquote

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token
from google import genai

from src.config.database import db
from src.config.websocket_config import WEBSOCKET_HOST
from src.models import Analysis, User
from src.services.analysis_bucket_minio import save_feedback_data, save_pdf_report
from src.services.minio import client as minio_client
from src.services.video_upload_analysis_service import MediaAnalysisService
from src.services.pdf_report_generator import generate_pdf_report
from src.services.telegram_bot import send_alert_sync

minio_hook_bp = Blueprint("minio_hook", __name__)


def get_media_analyzer_for_model(model_name, service_token):
    """Get MediaAnalysisService instance configured for the specified model"""
    try:
        from src.config.websocket_config import MODEL_CONFIGS

        if model_name not in MODEL_CONFIGS:
            print(f"Error: Model '{model_name}' not found in configuration")
            return None

        model_config = MODEL_CONFIGS[model_name]

        if (
            model_config.get("model_config") is None
            or model_config.get("checkpoint_path") is None
        ):
            print(f"Error: Model '{model_name}' is not properly configured")
            return None

        websocket_port = model_config.get("port", 8894)
        print(f"Using model '{model_name}' on port {websocket_port}")

        return MediaAnalysisService(
            websocket_host=WEBSOCKET_HOST,
            websocket_port=websocket_port,
            service_token=service_token,
        )

    except Exception as e:
        print(f"Error getting media analyzer for model {model_name}: {str(e)}")
        return None


def parse_minio_key(key):
    """Parse MinIO key to extract user_id, session_id, view, and model_name"""
    try:
        decoded_key = unquote(key)
        print(f"Parsing key: {decoded_key}")

        parts = decoded_key.split("/")

        if len(parts) == 3:  # user_id/session_id/model_view.ext
            user_id, session_id, filename = parts
            base_name = os.path.splitext(filename)[0]

            if "_" in base_name:
                model_name, view = base_name.split("_", 1)
                print(
                    f"Parsed: user_id={user_id}, session_id={session_id}, view={view}, model={model_name}"
                )
                return user_id, session_id, view, model_name

        print(f"Invalid key format: {key}")
        return None, None, None, None

    except Exception as e:
        print(f"Error parsing key {key}: {str(e)}")
        return None, None, None, None


def run_inference_on_media(file_path, view, model_name, user_id=None, session_id=None):
    """Run pose inference on media file using WebSocket service"""
    try:
        print(f"Starting inference for: {file_path} with model {model_name}")

        # Create a WebSocket token with proper claims for authentication
        service_token = create_access_token(
            identity="webhook_service",
            expires_delta=timedelta(minutes=5),
            additional_claims={"ws_auth": True, "one_time": True},
        )
        analyzer = get_media_analyzer_for_model(model_name, service_token)

        if analyzer is None:
            return {"error": f"Model '{model_name}' not available", "view": view}

        file_extension = os.path.splitext(file_path)[1].lower()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if file_extension in [".jpg", ".jpeg", ".png"]:
                result = loop.run_until_complete(
                    analyzer.analyze_image(file_path, view, user_id, session_id)
                )
            else:
                result = loop.run_until_complete(
                    analyzer.analyze_video(file_path, view, user_id, session_id)
                )

        finally:
            loop.close()

        if "error" in result:
            return result

        return {
            "score": result.get("score", {}),
            "raw_scores_percent": result.get("raw_scores_percent", {}),
            "measurements": result.get("measurements", {}),
            "view": result.get("detected_view", "unknown"),
            "model": model_name,
            "file_type": (
                "image" if file_extension in [".jpg", ".jpeg", ".png"] else "video"
            ),
        }

    except Exception as e:
        print(f"Error during inference: {str(e)}")
        return {"error": f"Inference failed: {str(e)}", "view": view}


# def create_view_result_structure(result):
#     """Create standardized view result structure"""
#     # The side information is now in the posture_score object
#     posture_score = result.get("score", {})
#     side = posture_score.get("side", None)

#     # Also check the detected_view from the main result
#     if side is None:
#         side = result.get("detected_view", None)

#     # Also check the view field from the main result
#     if side is None:
#         side = result.get("view", None)

#     if side is None:
#         return {
#             "score": "error(no side detected)",
#             "measurements": "error(no side detected)",
#             "keypoints": "error(no side detected)",
#         }

#     if side in ["left", "right"]:
#         return {
#             "score": {
#                 "knee_angle": posture_score.get("knee_angle", "unknown"),
#                 "head_tilt": posture_score.get("head_tilt", "unknown"),
#                 "arm_angle": posture_score.get("arm_angle", "unknown"),
#                 "arm_bent_angle": posture_score.get("arm_bent_angle", "unknown"),
#                 "leg_spread": posture_score.get("leg_spread", "unknown"),
#                 "back_angle": posture_score.get("back_angle", "unknown"),
#             },
#             "raw_scores_percent": result.get("raw_scores_percent", {}),
#             "measurements": {
#                 "knee_angle": result.get("measurements", {}).get(
#                     "knee_angle", "unknown"
#                 ),
#                 "head_tilt": result.get("measurements", {}).get("head_tilt", "unknown"),
#                 "arm_angle": result.get("measurements", {}).get("arm_angle", "unknown"),
#                 "arm_bent_angle": result.get("measurements", {}).get(
#                     "arm_bent_angle", "unknown"
#                 ),
#                 "leg_spread": result.get("measurements", {}).get(
#                     "leg_spread", "unknown"
#                 ),
#                 "back_angle": result.get("measurements", {}).get(
#                     "back_angle", "unknown"
#                 ),
#             },
#             "keypoints": result.get("keypoints", []),
#         }
#     elif side in ["front", "back"]:
#         return {
#             "score": {
#                 "foot_to_shoulder_offset": posture_score.get(
#                     "foot_to_shoulder_offset", 0.0
#                 )
#             },
#             "raw_scores_percent": result.get("raw_scores_percent", {}),
#             "measurements": {
#                 "foot_to_shoulder_offset_left": result.get("measurements", {}).get(
#                     "foot_to_shoulder_offset_left", "unknown"
#                 ),
#                 "foot_to_shoulder_offset_right": result.get("measurements", {}).get(
#                     "foot_to_shoulder_offset_right", "unknown"
#                 ),
#             },
#             "keypoints": result.get("keypoints", []),
#         }


def process_session_files(user_id, session_id, model_name, app):
    """Process all files in a session folder and aggregate results"""
    with app.app_context():
        try:
            print(f"Processing session: {user_id}/{session_id} with model {model_name}")

            # Find analysis record
            analysis = Analysis.query.filter_by(
                user_id=user_id, session_id=session_id
            ).first()
            if not analysis:
                print(
                    f"Warning: Analysis record not found for {user_id}/{session_id}, creating new one"
                )
                analysis = Analysis(
                    user_id=user_id,
                    session_id=session_id,
                    model_name=model_name,
                    status="in_progress",
                )
                db.session.add(analysis)
                db.session.commit()
            else:
                # Update status to in_progress if not already
                if analysis.status != "in_progress":
                    analysis.status = "in_progress"
                    db.session.commit()

            print(f"Processing session {session_id} with status: {analysis.status}")

            # List all files in the session folder
            folder_prefix = f"{user_id}/{session_id}/"
            objects = list(
                minio_client.list_objects(
                    "videos", prefix=folder_prefix, recursive=True
                )
            )

            if not objects:
                analysis.status = "failed"
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
                if "_" in base_name:
                    _, view = base_name.split("_", 1)
                else:
                    # Skip files that don't follow the expected format
                    print(f"Skipping file with invalid format: {filename}")
                    continue

                print(f"Processing file {filename} for view {view}")

                # Download and process file
                file_extension = os.path.splitext(file_key)[1]
                with tempfile.NamedTemporaryFile(
                    suffix=file_extension, delete=False
                ) as tmp_file:
                    tmp_path = tmp_file.name

                try:
                    decoded_key = unquote(file_key)
                    minio_client.fget_object("videos", decoded_key, tmp_path)

                    # Run inference with user_id and session_id for detailed data storage
                    result = run_inference_on_media(
                        tmp_path, view, model_name, user_id, session_id
                    )

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
                feedback = generate_session_feedback(session_results)

                # Save feedback to MinIO as JSON file
                save_feedback_data(user_id, session_id, feedback)

                # Generate PDF report
                pdf_bytes = generate_pdf_report(analysis, feedback)
                save_pdf_report(user_id, session_id, pdf_bytes)

                # Update analysis status to completed
                analysis.status = "completed"
                db.session.commit()

                send_alert_sync(user_id, analysis)

                print(f"Session analysis completed for {session_id}")
            else:
                analysis.status = "failed"
                db.session.commit()

                send_alert_sync(user_id, analysis)
                print(f"Session analysis failed for {session_id}")

        except Exception as e:
            print(f"Error processing session: {str(e)}")
            traceback.print_exc()
            # Make sure analysis exists before trying to update it
            try:
                if "analysis" not in locals() or analysis is None:
                    analysis = Analysis.query.filter_by(
                        user_id=user_id, session_id=session_id
                    ).first()
                    if not analysis:
                        analysis = Analysis(
                            user_id=user_id,
                            session_id=session_id,
                            status="failed",
                        )
                        db.session.add(analysis)
                    else:
                        analysis.status = "failed"
                else:
                    analysis.status = "failed"
                db.session.commit()

                send_alert_sync(user_id, analysis)
                
            except Exception as db_error:
                print(f"Error updating analysis record: {str(db_error)}")
                send_alert_sync(user_id, analysis)


def generate_session_feedback(session_results):
    """Generate feedback based on all views in the session"""
    client = genai.Client()
    prompt = (
        "You are an expert firearms posture coach and biomechanics analyst.\n\n"
        "Your task:\n"
        "Analyze a user’s fighting‑stance firearm posture using pose‑estimation JSON data (COCO‑WholeBody 133 keypoints) from up to four views: front, left, right, back.\n\n"
        "Input:\n"
        "A JSON object that may include any combination of sides (“front”, “left”, “right”, “back”). Each side contains:\n"
        '  - "score": metric scores relevant to that view\n'
        '  - "measurements": actual values or "unknown"\n'
        '  - "keypoints": raw pose‑estimation data\n\n'
        "For each side present, you must evaluate each **metric separately**, distinguishing:\n"
        "  - **Commendation**: what is good or optimal for that metric\n"
        "  - **Critique**: what deviates or needs improvement for that metric\n"
        "  - **Suggestions**: concrete, actionable steps to improve that metric\n\n"
        "If a metric is missing or marked “unknown”, note that analysis cannot be done for that metric.\n\n"
        "Expected output:\n"
        "Return a JSON structured as follows:\n\n"
        "{\n"
        '  "<side>": {\n'
        '    "<metric1>": {\n'
        '      "commendation": "...",\n'
        '      "critique": "...",\n'
        '      "suggestions": [ "...", "..." ]\n'
        "    },\n"
        '    "<metric2>": { ... },\n'
        "    ...\n"
        "  },\n"
        "  ...\n"
        "}\n\n"
        "Output the JSON object only—no additional prose outside of the JSON. Just JSON to allow json.loads() to work\n\n"
        "Keep feedback **succinct, actionable**, and **focused per metric**.\n"
        f"{session_results}"
    )

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    if response and response.text:
        try:
            json_str = response.text.strip("`json")
            feedback_json = json.loads(json_str)
            return feedback_json
        except json.JSONDecodeError:
            print("Error: Unable to parse feedback as JSON.")
            return {"error": "Invalid JSON response from Gemini API."}

    return response.text if response and response.text else "No feedback generated"


@minio_hook_bp.route("/webhook", methods=["POST"])
def minio_webhook():
    """Handle MinIO webhook notifications for media uploads"""
    try:
        data = request.get_json()

        # Track sessions that need processing (to avoid duplicate processing)
        sessions_to_process = set()

        for record in data.get("Records", []):
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            if bucket != "videos":
                continue

            user_id, session_id, view, model_name = parse_minio_key(key)
            if not all([user_id, session_id, view, model_name]):
                continue

            session_key = (user_id, session_id, model_name)
            sessions_to_process.add(session_key)

        # Process each unique session
        for user_id, session_id, model_name in sessions_to_process:
            print(
                f"Starting session processing: {user_id}/{session_id} with model {model_name}"
            )

            # Check if session is already being processed
            existing_analysis = Analysis.query.filter_by(
                user_id=user_id, session_id=session_id
            ).first()

            if existing_analysis and existing_analysis.status in ["in_progress", "completed"]:
                print(f"Session {session_id} is already being processed or completed, skipping")
                continue

            # Update status to in_progress to prevent duplicate processing
            if existing_analysis:
                existing_analysis.status = "in_progress"
                existing_analysis.model_name = model_name
                db.session.commit()
                print(f"Updated existing analysis {existing_analysis.id} status to in_progress")
            else:
                # This should rarely happen now since upload creates the record
                print(f"Creating new analysis record for {session_id} (upload didn't create one)")
                existing_analysis = Analysis(
                    user_id=user_id,
                    session_id=session_id,
                    model_name=model_name,
                    status="in_progress",
                )
                db.session.add(existing_analysis)
                db.session.commit()

            print(f"Marked session {session_id} as in_progress, scheduling processing")

            # Capture the app object before starting the timer
            app = current_app._get_current_object()

            # Add a small delay to allow all files to be uploaded
            threading.Timer(
                2.0,  # 2 second delay
                process_session_files,
                args=(user_id, session_id, model_name, app),
            ).start()

        return (
            jsonify(
                {
                    "message": "Processing started",
                    "sessions_queued": len(sessions_to_process),
                }
            ),
            202,
        )

    except Exception as e:
        print(f"ERROR in webhook handler: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
