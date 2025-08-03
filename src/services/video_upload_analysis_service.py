import cv2
import numpy as np
import asyncio
import websockets
import json
import base64
import os
import math
from typing import Dict, List
from ..config.websocket_config import WEBSOCKET_HOST
from flask_jwt_extended import get_jwt_identity, decode_token
from flask import request
from .analysis_bucket_minio import save_detailed_analysis_data
from .minio import client as minio_client

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
    
    async def analyze_media(self, file_path: str, view: str, user_id: str = None, session_id: str = None) -> Dict:
        """
        Analyze a video or image file by sending frames to the WebSocket inference service
        """
        if self.is_image_file(file_path):
            return await self.analyze_image(file_path, view, user_id, session_id)
        elif self.is_video_file(file_path):
            return await self.analyze_video(file_path, view, user_id, session_id)
        else:
            return {"error": f"Unsupported file type: {file_path}", "view": view}
    
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
                    
                    # Save detailed analysis data to MinIO if user_id and session_id are provided
                    if user_id and session_id:
                        detailed_data = {
                            "file_type": "image",
                            "view": view,
                            "detected_view": detected_view,
                            "analysis_timestamp": asyncio.get_event_loop().time(),
                            "image_data": {
                                "keypoints": keypoints,
                                "score": posture_score,
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
                        "analysis_timestamp": asyncio.get_event_loop().time(),
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
        try:
            # Try different OpenCV backends for better compatibility
            cap = None
            backends = [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_ANY]
            
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(video_path, backend)
                    if cap.isOpened():
                        print(f"Successfully opened video with backend: {backend}")
                        break
                    else:
                        cap.release()
                        cap = None
                except Exception as e:
                    print(f"Failed to open video with backend {backend}: {e}")
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
            
            # Process every nth frame to reduce computation
            frame_skip = max(1, total_frames // 5) if total_frames > 30 else 1
            
            print(f"Video info: {total_frames} frames, {fps} FPS")
            print(f"Frame skip value: {frame_skip}, will process approximately {total_frames // frame_skip} frames")

            frame_scores = []
            frame_measurements = []
            raw_scores_percent_list = []
            frame_idx = 0
            
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
                print('Connected to WebSocket for video analysis')
                
                # Wait for authentication response (automatic with query parameter)
                auth_response = await websocket.recv()
                auth_data = json.loads(auth_response)
                
                # Handle authentication response
                if auth_data.get('status') == 'authenticated':
                    print(f'Authentication successful, user ID: {auth_data.get("user_id")}')
                else:
                    cap.release()
                    return {"error": f"Authentication failed: {auth_data.get('error', 'Unknown error')}", "view": view}
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    if frame_idx % frame_skip == 0:
                        print(f"Processing frame {frame_idx}/{total_frames}")
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

                        except Exception as e:
                            print(f"Error processing frame {frame_idx}: {e}")
                    
                    frame_idx += 1
            
            cap.release()
            
            print(f"Finished processing video. Total frames: {total_frames}, Processed frames: {len(frame_scores)}")
            
            # Calculate final analysis results
            result = self.aggregate_frame_scores(frame_scores, frame_measurements, raw_scores_percent_list, view, total_frames)
            result["file_type"] = "video"
            
            # Save detailed frame data to MinIO if user_id and session_id are provided
            if user_id and session_id and detailed_frames_data:
                detected_view = result.get("view", view)
                detailed_data = {
                    "file_type": "video",
                    "view": view,
                    "detected_view": detected_view,
                    "analysis_timestamp": asyncio.get_event_loop().time(),
                    "total_frames": total_frames,
                    "processed_frames": len(detailed_frames_data),
                    "frame_skip": frame_skip,
                    "frames_data": detailed_frames_data,
                    "aggregate_results": {
                        "score": result.get("score", {}),
                        "raw_score_percent": result.get("raw_scores_percent", {}),
                        "measurements": result.get("measurements", {})
                    }
                }
                save_detailed_analysis_data(user_id, session_id, detected_view, detailed_data)
            
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

    def aggregate_frame_scores(self, frame_scores: List[Dict], frame_measurements: List[Dict], raw_scores_percent: List[Dict], frame_keypoints: List, view: str, total_frames: int) -> Dict:
        """Aggregate frame scores and measurements into final analysis result"""
        if not frame_scores:
            return {"error": "No frames processed", "view": view}
        
        # Use the provided view since users must specify the actual view
        detected_side = view  # Use the view provided by the user
        
        # Calculate average posture scores (excluding 'side' field)
        avg_scores = {}
        for score in frame_scores:
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

        #Calculate averege raw scores percent
        avg_raw_scores = {}
        for raw_score in raw_scores_percent:
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
        for measurements in frame_measurements:
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

        # Calculate overall score
        overall_score = np.mean(list(final_scores.values())) if final_scores else 0
        
        result = {
            "overall_posture_score": overall_score,
            "score": final_scores,
            "raw_scores_percent": final_raw_scores_percent,  # Changed from "final_raw_scores_percent"
            "measurements": final_measurements,
            "detected_view": detected_side,
            "frame_count": len(frame_scores),
            "total_frames": total_frames,
            "analysis_timestamp": asyncio.get_event_loop().time()
        }

        return result
    
    def analyze_media_sync(self, file_path: str, view: str, user_id: str = None, session_id: str = None) -> Dict:
        
        """Synchronous wrapper for media analysis"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.analyze_media(file_path, view, user_id, session_id))
        except Exception as e:
            return {"error": str(e), "file_path": file_path}
        finally:
            loop.close()

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
