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
    
    async def analyze_media(self, file_path: str, view: str) -> Dict:
        """
        Analyze a video or image file by sending frames to the WebSocket inference service
        """
        if self.is_image_file(file_path):
            return await self.analyze_image(file_path, view)
        elif self.is_video_file(file_path):
            return await self.analyze_video(file_path, view)
        else:
            return {"error": f"Unsupported file type: {file_path}", "view": view}
    
    async def analyze_image(self, image_path: str, view: str = None) -> Dict:
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
            
            # Configure connection with timeout and proper settings for websockets 15.0.1
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
                
                if "keypoints" in result and "posture_score" in result:
                    keypoints = result["keypoints"]
                    posture_score = result["posture_score"]
                    measurements = result.get("measurements", {})

                    # Extract the detected side from posture_score if available
                    detected_view = posture_score.pop("side")
                    print(f"Detected view: {detected_view}, result: {result}")
                    
                    # Calculate confidence from numeric values only (exclude 'side' field)
                    numeric_scores = {k: v for k, v in posture_score.items() if k != "side" and isinstance(v, (int, float))}
                    confidence = sum(numeric_scores.values()) / len(numeric_scores.values()) if numeric_scores else 0
                    
                    return {
                        "keypoints": keypoints,
                        "detected_view": detected_view,
                        "confidence": confidence,
                        "score": posture_score,
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
    
    async def analyze_video(self, video_path: str, view: str = None) -> Dict:
        """
        Analyze a video file by sending frames to the WebSocket inference service
        """
        try:
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Process every nth frame to reduce computation
            frame_skip = max(1, total_frames // 15)  # Process ~15 frames max

            frame_scores = []
            frame_keypoints = []
            frame_measurements = []
            frame_idx = 0
            
            # Connect to WebSocket inference service
            uri = f"ws://{self.websocket_host}:{self.websocket_port}?token={self.service_token}"
            
            # Configure connection with timeout and proper settings for websockets 15.0.1
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
                                keypoints = result["keypoints"]
                                posture_score = result["posture_score"]
                                measurements = result.get("measurements", {})
                                frame_scores.append(posture_score)
                                frame_measurements.append(measurements)
                                frame_keypoints.append(keypoints)

                        except Exception as e:
                            print(f"Error processing frame {frame_idx}: {e}")
                    
                    frame_idx += 1
            
            cap.release()
            
            # Calculate final analysis results
            result = self.aggregate_frame_scores(frame_scores, frame_measurements, view, total_frames)
            result["file_type"] = "video"
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
    
    def aggregate_frame_scores(self, frame_scores: List[Dict], frame_measurements: List[Dict], view: str, total_frames: int) -> Dict:
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
            "confidence": overall_score,
            "score": final_scores,
            "measurements": final_measurements,
            "view": detected_side,
            "frame_count": len(frame_scores),
            "total_frames": total_frames,
            "analysis_timestamp": asyncio.get_event_loop().time()
        }
        
        return result
    
    def analyze_media_sync(self, file_path: str, view: str) -> Dict:
        
        """Synchronous wrapper for media analysis"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.analyze_media(file_path, view))
        except Exception as e:
            return {"error": str(e), "file_path": file_path}
        finally:
            loop.close()

VideoAnalysisService = MediaAnalysisService
