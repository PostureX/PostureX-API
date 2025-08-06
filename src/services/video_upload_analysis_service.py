import cv2
import numpy as np
import asyncio
import websockets
import json
import base64
import os
import math
import uuid
from datetime import datetime
import pytz
from typing import Dict, List
from ..config.websocket_config import WEBSOCKET_HOST
from flask_jwt_extended import get_jwt_identity, decode_token
from flask import request
from .analysis_bucket_minio import save_detailed_analysis_data
from .minio import client as minio_client

# Singapore timezone
SGT = pytz.timezone('Asia/Singapore')

class MediaAnalysisService:
    """Service for analyzing videos and images using the WebSocket inference service"""

    def __init__(self, websocket_host=WEBSOCKET_HOST, websocket_port=8894, service_token=None):
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.service_token = service_token
    
    def is_video_file(self, file_path: str) -> bool:
        """Check if file is a video based on extension"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        return os.path.splitext(file_path.lower())[1] in video_extensions
    
    def is_image_file(self, file_path: str) -> bool:
        """Check if file is an image based on extension"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        return os.path.splitext(file_path.lower())[1] in image_extensions
    
    async def analyze_image(self, image_path: str, view: str = None, user_id: str = None, session_id: str = None) -> Dict:
        """
        Analyze a single image file using WebSocket connection similar to JavaScript client
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return {"error": f"Could not load image: {image_path}", "view": view}
            
            # Add token as query parameter for authentication
            uri = f"ws://{self.websocket_host}:{self.websocket_port}?token={self.service_token}"
            
            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                print('Connected to WebSocket')
                
                # Wait for authentication response (automatic with query parameter)
                auth_response = await websocket.recv()
                auth_data = json.loads(auth_response)
                
                # Handle authentication response
                if auth_data.get('status') == 'authenticated':
                    print(f'Authentication successful, user ID: {auth_data.get("user_id")}')
                else:
                    return {"error": f"Authentication failed: {auth_data.get('error', 'Unknown error')}", "view": view}

                # Convert image to base64
                frame_b64 = self.frame_to_base64(image)
                
                # Send image for inference
                message = {
                    "image": frame_b64
                }
                await websocket.send(json.dumps(message))
                
                # Receive keypoints and posture score
                response = await websocket.recv()
                result = json.loads(response)
                
                if result:
                    keypoints = result.get("keypoints", {})
                    posture_score = result.get("posture_score", {})
                    measurements = result.get("measurements", {})
                    raw_scores_percent = result.get("raw_scores_percent", {})

                    # Extract the detected side from posture_score if available
                    detected_view = posture_score.pop("side")
                    print(f"Detected view: {detected_view}, result: {result}")
                    
                    # Handle front/back disambiguation for image analysis too
                    if view == 'back' and detected_view == 'front':
                        detected_view = 'back'
                        print(f"Image: User specified 'back' view, treating detected 'front' as 'back'")
                    elif view == 'front' and detected_view == 'front':
                        detected_view = 'front'
                        print(f"Image: User specified 'front' view, confirmed by model detection")
                    
                    # Save detailed analysis data to MinIO if user_id and session_id are provided
                    if user_id and session_id:
                        detailed_data = {
                            "file_type": "image",
                            "view": view,
                            "detected_view": detected_view,
                            "analysis_timestamp": datetime.now(SGT).isoformat(),
                            "image_data": {
                                "keypoints": keypoints,
                                "score": posture_score,  # This already has 'side' popped out
                                "raw_scores_percent": raw_scores_percent,
                                "measurements": measurements
                            }
                        }
                        save_detailed_analysis_data(user_id, session_id, detected_view, detailed_data)
                    
                    # Calculate overall posture score from numeric values only (exclude 'side' field)
                    numeric_scores = {k: v for k, v in posture_score.items() if k != "side" and isinstance(v, (int, float))}
                    overall_posture_score = sum(numeric_scores.values()) / len(numeric_scores.values()) if numeric_scores else 0
                    
                    return {
                        "keypoints": keypoints,
                        "detected_view": detected_view,
                        "overall_posture_score": overall_posture_score,
                        "score": posture_score,
                        "raw_scores_percent": raw_scores_percent,
                        "measurements": measurements,
                        "frame_count": 1,
                        "total_frames": 1,
                        "analysis_timestamp": datetime.now(SGT).isoformat(),
                        "file_type": "image",
                    }
                
                else:
                    return {"error": f"Invalid response from inference service: {result}", "view": view}
            
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed unexpectedly in analyze_image: {e}")
            return {"error": f"WebSocket connection closed: {e}", "view": view}
        except websockets.exceptions.InvalidURI as e:
            print(f"Invalid WebSocket URI in analyze_image: {e}")
            return {"error": f"Invalid WebSocket URI: {e}", "view": view}
        except websockets.exceptions.InvalidHandshake as e:
            print(f"WebSocket handshake failed in analyze_image: {e}")
            return {"error": f"WebSocket handshake failed: {e}", "view": view}
        except Exception as e:
            print(f"Error in analyze_image: {str(e)}")
            return {"error": str(e), "view": view}
    
    async def analyze_video(self, video_path: str, view: str = None, user_id: str = None, session_id: str = None) -> Dict:
        """
        Analyze a video file by sending frames to the WebSocket inference service

        Returns aggregated results including posture scores, measurements, and keypoints.
        """
        analysis_id = str(uuid.uuid4())[:8]
        print(f"[{analysis_id}] Starting video analysis for {video_path}")
        
        try:
            # Try different OpenCV backends for better compatibility
            cap = None
            backends = [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_ANY]
            
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(video_path, backend)
                    if cap.isOpened():
                        print(f"[{analysis_id}] Successfully opened video with backend: {backend}")
                        break
                    else:
                        cap.release()
                        cap = None
                except Exception as e:
                    print(f"[{analysis_id}] Failed to open video with backend {backend}: {e}")
                    if cap:
                        cap.release()
                    cap = None
            
            if cap is None:
                return {"error": f"Could not open video file: {video_path}", "view": view}
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            if total_frames <= 0:
                cap.release()
                return {"error": f"Invalid video file - no frames detected: {video_path}", "view": view}
            
            # Frame skip interval (process every nth frame)
            frame_skip = 2  # Process every 5th frame (0, 5, 10, 15, etc.)
            
            print(f"[{analysis_id}] Video info: {total_frames} frames, {fps} FPS")
            print(f"[{analysis_id}] Frame skip interval: {frame_skip}, will process approximately {total_frames // frame_skip} frames")

            frame_scores = []
            frame_measurements = []
            raw_scores_percent_list = []
            frame_idx = 0
            processed_frame_count = 0
            
            # Collect detailed frame data for MinIO storage
            detailed_frames_data = []
            
            # Connect to WebSocket inference service
            uri = f"ws://{self.websocket_host}:{self.websocket_port}?token={self.service_token}"
            
            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as websocket:
                print(f'[{analysis_id}] Connected to WebSocket for video analysis')
                
                # Wait for authentication response (automatic with query parameter)
                auth_response = await websocket.recv()
                auth_data = json.loads(auth_response)
                
                # Handle authentication response
                if auth_data.get('status') == 'authenticated':
                    print(f'[{analysis_id}] Authentication successful, user ID: {auth_data.get("user_id")}')
                else:
                    cap.release()
                    return {"error": f"Authentication failed: {auth_data.get('error', 'Unknown error')}", "view": view}
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Only process every nth frame based on frame_skip interval
                    if frame_idx % frame_skip == 0:
                        processed_frame_count += 1
                        print(f"[{analysis_id}] Processing frame {frame_idx}/{total_frames} (processed: {processed_frame_count})")
                        try:
                            # Convert frame to base64
                            frame_b64 = self.frame_to_base64(frame)
                            
                            # Send frame for inference
                            message = {
                                "image": frame_b64
                            }
                            await websocket.send(json.dumps(message))
                            
                            # Receive keypoints and posture score
                            response = await websocket.recv()
                            result = json.loads(response)
                            
                            if "keypoints" in result and "posture_score" in result:
                                keypoints = result.get("keypoints", {})
                                posture_score = result.get("posture_score", {})
                                measurements = result.get("measurements", {})
                                raw_scores_percent = result.get("raw_scores_percent", {})
                                
                                frame_scores.append(posture_score)
                                frame_measurements.append(measurements)
                                raw_scores_percent_list.append(raw_scores_percent)
                                
                                # Collect detailed frame data for MinIO storage
                                if user_id and session_id:
                                    frame_data = {
                                        "frame_index": frame_idx,
                                        "timestamp": frame_idx / fps if fps > 0 else 0,
                                        "keypoints": keypoints,
                                        "score": posture_score.copy(),  # Make a copy since we'll modify posture_score later
                                        "raw_scores_percent": raw_scores_percent,
                                        "measurements": measurements
                                    }
                                    detailed_frames_data.append(frame_data)
                            else:
                                print(f"[{analysis_id}] Invalid result for frame {frame_idx}: {result}")

                        except Exception as e:
                            print(f"[{analysis_id}] Error processing frame {frame_idx}: {e}")
                    
                    frame_idx += 1
            
            cap.release()
            
            print(f"[{analysis_id}] Finished processing video. Total frames: {total_frames}, Processed frames: {len(frame_scores)}, Expected frames: {processed_frame_count}")
            
            if len(frame_scores) == 0:
                return {"error": "No frames were successfully processed", "view": view}
            
            # Calculate final analysis results
            result = self.aggregate_frame_scores(frame_scores, frame_measurements, raw_scores_percent_list, view, total_frames)
            result["file_type"] = "video"
            
            # Save detailed frame data to MinIO if user_id and session_id are provided
            if user_id and session_id and detailed_frames_data:
                detected_view = result.get("detected_view", view)  # Use the most common detected side
                
                # Create aggregate results without 'side' field in score
                aggregate_score = result.get("score", {}).copy()
                if 'side' in aggregate_score:
                    del aggregate_score['side']
                
                detailed_data = {
                    "file_type": "video",
                    "view": view,
                    "detected_view": detected_view,
                    "analysis_timestamp": datetime.now(SGT).isoformat(),
                    "total_frames": total_frames,
                    "processed_frames": len(detailed_frames_data),
                    "frame_skip_interval": frame_skip,
                    "frames_data": detailed_frames_data,
                    "aggregate_results": {
                        "score": aggregate_score,  # Score without 'side' field
                        "raw_score_percent": result.get("raw_scores_percent", {}),
                        "measurements": result.get("measurements", {}),
                        "side_detection_summary": result.get("side_detection_summary", {})
                    }
                }
                save_detailed_analysis_data(user_id, session_id, view, detailed_data)
            
            return result
            
        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket connection closed unexpectedly in analyze_video: {e}")
            return {"error": f"WebSocket connection closed: {e}", "view": view}
        except websockets.exceptions.InvalidURI as e:
            print(f"Invalid WebSocket URI in analyze_video: {e}")
            return {"error": f"Invalid WebSocket URI: {e}", "view": view}
        except websockets.exceptions.InvalidHandshake as e:
            print(f"WebSocket handshake failed in analyze_video: {e}")
            return {"error": f"WebSocket handshake failed: {e}", "view": view}
        except Exception as e:
            print(f"Error in analyze_video: {str(e)}")
            return {"error": str(e), "view": view}
    
    def frame_to_base64(self, frame) -> str:
        """Convert OpenCV frame to base64 string"""
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        return frame_b64

    def aggregate_frame_scores(self, frame_scores: List[Dict], frame_measurements: List[Dict], raw_scores_percent: List[Dict], view: str, total_frames: int) -> Dict:
        """Aggregate frame scores and measurements into final analysis result"""
        if not frame_scores:
            return {"error": "No frames processed", "view": view}
        
        # Group frames by detected side and count occurrences
        side_counts = {}
        frames_by_side = {}
        measurements_by_side = {}
        raw_scores_by_side = {}
        
        for i, score in enumerate(frame_scores):
            if isinstance(score, dict) and 'side' in score:
                detected_side = score['side']
                
                # Count occurrences of each side
                if detected_side not in side_counts:
                    side_counts[detected_side] = 0
                    frames_by_side[detected_side] = []
                    measurements_by_side[detected_side] = []
                    raw_scores_by_side[detected_side] = []
                
                side_counts[detected_side] += 1
                frames_by_side[detected_side].append(score)
                
                # Add corresponding measurements and raw scores if available
                if i < len(frame_measurements):
                    measurements_by_side[detected_side].append(frame_measurements[i])
                if i < len(raw_scores_percent):
                    raw_scores_by_side[detected_side].append(raw_scores_percent[i])
        
        # Find the most common detected side
        if not side_counts:
            return {"error": "No valid side detection found in frames", "view": view}
        
        most_common_side = max(side_counts, key=side_counts.get)
        print(f"Side detection counts: {side_counts}")
        print(f"Most common detected side: {most_common_side} ({side_counts[most_common_side]} frames)")
        
        # Handle front/back disambiguation using user-provided view
        # The model can only detect left/right/front, but cannot distinguish front from back
        # So if user specified 'back' and model detected 'front', trust the user
        final_detected_view = most_common_side
        if view == 'back' and most_common_side == 'front':
            final_detected_view = 'back'
            print(f"User specified 'back' view, treating detected 'front' as 'back'")
        elif view == 'front' and most_common_side == 'front':
            final_detected_view = 'front'
            print(f"User specified 'front' view, confirmed by model detection")
        
        # Use only frames from the most common detected side for aggregation
        selected_frame_scores = frames_by_side[most_common_side]
        selected_measurements = measurements_by_side[most_common_side]
        selected_raw_scores = raw_scores_by_side[most_common_side]
        
        # Calculate average posture scores (excluding 'side' field)
        avg_scores = {}
        for score in selected_frame_scores:
            if isinstance(score, dict):
                for metric, value in score.items():
                    if metric == 'side':  # Skip the 'side' field during averaging
                        continue
                    if metric not in avg_scores:
                        avg_scores[metric] = []
                    if isinstance(value, (int, float)):
                        avg_scores[metric].append(value)
        
        final_scores = {}
        for metric, values in avg_scores.items():
            if values:
                final_scores[metric] = np.mean(values)

        # Calculate average raw scores percent
        avg_raw_scores = {}
        for raw_score in selected_raw_scores:
            if isinstance(raw_score, dict):
                for metric, value in raw_score.items():
                    if metric not in avg_raw_scores:
                        avg_raw_scores[metric] = []
                    if isinstance(value, (int, float)):
                        avg_raw_scores[metric].append(value)
        
        final_raw_scores_percent = {}
        for metric, values in avg_raw_scores.items():
            if values:
                final_raw_scores_percent[metric] = np.mean(values)  
        
        # Calculate average measurements
        avg_measurements = {}
        for measurements in selected_measurements:
            if isinstance(measurements, dict):
                for metric, value in measurements.items():
                    if metric not in avg_measurements:
                        avg_measurements[metric] = []
                    if isinstance(value, (int, float)):
                        avg_measurements[metric].append(value)
        
        # Calculate averages for measurements
        final_measurements = {}
        for metric, values in avg_measurements.items():
            if values:
                final_measurements[metric] = np.mean(values)

        # Calculate overall score from numeric values only (exclude 'side' field)
        numeric_scores = {k: v for k, v in final_scores.items() if k != "side" and isinstance(v, (int, float))}
        overall_score = np.mean(list(numeric_scores.values())) if numeric_scores else 0
        
        # Create a copy of final_scores for the main result (includes 'side')
        final_scores_with_side = final_scores.copy()
        final_scores_with_side['side'] = final_detected_view
        
        result = {
            "overall_posture_score": overall_score,
            "score": final_scores_with_side,  # This includes 'side' for main API response
            "raw_scores_percent": final_raw_scores_percent,
            "measurements": final_measurements,
            "detected_view": final_detected_view,  # Use the final determined view (handles front/back)
            "view": view,  # Keep original view for reference
            "frame_count": len(selected_frame_scores),  # Count of frames used for aggregation
            "total_frames": total_frames,
            "side_detection_summary": {
                "side_counts": side_counts,
                "most_common_side": most_common_side,
                "final_detected_view": final_detected_view,
                "user_specified_view": view,
                "frames_used_for_aggregation": len(selected_frame_scores)
            },
            "analysis_timestamp": asyncio.get_event_loop().time()
        }

        return result

def delete_session_video_files(user_id: str, session_id: str) -> bool:
    """
    Delete all video files for a session from the videos bucket
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        videos_bucket = "videos"
        
        # Check if videos bucket exists
        if not minio_client.bucket_exists(videos_bucket):
            print(f"Videos bucket '{videos_bucket}' does not exist")
            return True  # Consider this successful since there are no files to delete
        
        prefix = f"{user_id}/{session_id}/"
        objects = minio_client.list_objects(videos_bucket, prefix=prefix, recursive=True)
        
        deleted_count = 0
        for obj in objects:
            minio_client.remove_object(videos_bucket, obj.object_name)
            deleted_count += 1
            print(f"Deleted video file: {obj.object_name}")
            
        print(f"Deleted {deleted_count} video files for session {session_id}")
        return True
        
    except Exception as e:
        print(f"Error deleting session video files: {str(e)}")
        return False

VideoAnalysisService = MediaAnalysisService
