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
import asyncio
import websockets
import json
import cv2
import base64
import numpy as np
import math
import os

async def authenticate_websocket(websocket, service_token=None):
    """Send authentication message to WebSocket server"""
    try:
        # If a service token is provided (for webhook/internal calls), use it directly
        if service_token:
            auth_message = {
                "cookies": f"access_token_cookie={service_token}"
            }
            await websocket.send(json.dumps(auth_message))
            
            # Wait for authentication response
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_result = json.loads(response)
            
            if auth_result.get('status') == 'authenticated':
                return True
            else:
                print(f"Service token authentication failed: {auth_result}")
                return False
        
        try:
            # Try to get token from request cookies using Flask-JWT-Extended approach
            token = request.cookies.get('access_token_cookie')
            
            if not token:
                print("No JWT token found in cookies")
                await websocket.send(json.dumps({'error': 'No JWT token found'}))
                return False
            
            # Validate the token using Flask-JWT-Extended
            try:
                # This will raise an exception if token is invalid/expired
                decoded_token = decode_token(token)
                user_id = decoded_token.get('sub')  # 'sub' is the user ID in JWT
                print(f"Token validated for user: {user_id}")
            except Exception as token_error:
                print(f"Token validation failed: {token_error}")
                await websocket.send(json.dumps({'error': 'Invalid or expired token'}))
                return False
            
            # Send authentication message to WebSocket server
            auth_message = {
                "cookies": f"access_token_cookie={token}"
            }
            await websocket.send(json.dumps(auth_message))
            
            # Wait for authentication response
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_result = json.loads(response)
            
            if auth_result.get('status') == 'authenticated':
                return True
            else:
                print(f"Authentication failed: {auth_result}")
                return False
                
        except Exception as e:
            print(f"Error getting JWT token: {e}")
            return False
            
    except Exception as e:
        print(f"Authentication error: {e}")
        return False

def get_user_token():
    """Get the user's JWT token from cookies"""
    try:
        token = request.cookies.get('access_token_cookie')
        
        if not token:
            raise ValueError("No access_token_cookie found in request")
        
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
            
            uri = f"ws://{self.websocket_host}:{self.websocket_port}"
            
            async with websockets.connect(uri) as websocket:
                print('Connected to WebSocket')
                
                # Send authentication message with JWT token in cookies format (similar to JavaScript)
                auth_message = {
                    "cookies": f"access_token_cookie={self.service_token}"
                }
                await websocket.send(json.dumps(auth_message))
                
                # Wait for authentication response
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
                    return {
                        "keypoints": keypoints,
                        "detected_view": detected_view,
                        "confidence": sum(posture_score.values()) / len(posture_score.values()) if posture_score else 0,
                        "score": posture_score,
                        "measurements": measurements,
                        "frame_count": 1,
                        "total_frames": 1,
                        "analysis_timestamp": asyncio.get_event_loop().time(),
                        "file_type": "image",
                    }
                else:
                    return {"error": f"Invalid response from inference service: {result}", "view": view}
            
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
            uri = f"ws://{self.websocket_host}:{self.websocket_port}"
            
            async with websockets.connect(uri) as websocket:
                print('Connected to WebSocket for video analysis')
                
                # Send authentication message with JWT token in cookies format (similar to JavaScript)
                auth_message = {
                    "cookies": f"access_token_cookie={self.service_token}"
                }
                await websocket.send(json.dumps(auth_message))
                print('Sent authentication message')
                
                # Wait for authentication response
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
                                print("apple:", posture_score)
                                measurements = result.get("measurements", {})
                                frame_scores.append(posture_score)
                                frame_measurements.append(measurements)
                                frame_keypoints.append(keypoints)
                                print(f"Processed frame {frame_idx}, detected keypoints")

                        except Exception as e:
                            print(f"Error processing frame {frame_idx}: {e}")
                    
                    frame_idx += 1
            
            cap.release()
            
            # Calculate final analysis results
            result = self.aggregate_frame_scores(frame_scores, frame_measurements, view, total_frames)
            print("Aggregate_frame_scores:",result)
            result["file_type"] = "video"
            return result
            
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
        
        print("Avg_scores:", avg_scores)
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

# Fallback analysis for when WebSocket service is not available
def analyze_media_fallback(file_path: str, view: str) -> Dict:
    """
    Fallback media analysis using local processing
    This is a simplified version that doesn't use the WebSocket service
    """
    try:
        # Determine file type
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        
        file_ext = os.path.splitext(file_path.lower())[1]
        
        if file_ext in image_extensions:
            # Image analysis
            image = cv2.imread(file_path)
            if image is None:
                return {"error": f"Could not load image: {file_path}", "view": view}
            
            frame_count = 1
            total_frames = 1
            file_type = "image"
            
        elif file_ext in video_extensions:
            # Video analysis
            cap = cv2.VideoCapture(file_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
            
            cap.release()
            file_type = "video"
            
        else:
            return {"error": f"Unsupported file type: {file_ext}", "view": view}
        
        # Generate dummy scores based on view
        view_scores = {
            "front": {"overall_score": 85, "metrics": {"foot_alignment": 0.8}},
            "left": {"overall_score": 82, "metrics": {"back_angle": 5.2, "head_tilt": -2.1}},
            "right": {"overall_score": 80, "metrics": {"back_angle": 4.8, "head_tilt": -1.8}},
            "back": {"overall_score": 78, "metrics": {"shoulder_alignment": 0.9}}
        }
        
        base_score = view_scores.get(view, view_scores["front"])  # Default to front if unknown view
        
        return {
            "overall_score": base_score["overall_score"] + np.random.uniform(-5, 5),
            "view": view,
            "frame_count": frame_count,
            "total_frames": total_frames,
            "metrics": base_score["metrics"],
            "file_type": file_type
        }
        
    except Exception as e:
        return {"error": str(e), "view": view}

# Backward compatibility aliases
VideoAnalysisService = MediaAnalysisService
analyze_video_fallback = analyze_media_fallback
