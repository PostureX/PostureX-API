import asyncio
import websockets
import json
import itertools
import numpy as np
import cv2
import base64
from flask_jwt_extended import decode_token
from jwt.exceptions import InvalidTokenError
from mmpose.apis import MMPoseInferencer
from ..config.websocket_config import WEBSOCKET_HOST, MODEL_CONFIGS

# Load model per gpu at startup for multiple models
NUM_GPUS = 4
model_names = list(MODEL_CONFIGS.keys())
inferencers = {
    model_name: [
        MMPoseInferencer(MODEL_CONFIGS[model_name]["model_config"], pose2d_weights=MODEL_CONFIGS[model_name]["checkpoint_path"], device=f'cuda:{i}')
        for i in range(NUM_GPUS)
    ] if MODEL_CONFIGS[model_name]["model_config"] is not None else None
    for model_name in model_names
}

gpu_cycle = itertools.cycle(range(NUM_GPUS))


async def authenticate_websocket(websocket):
    """Authenticate WebSocket connection using JWT token from cookies"""
    try:
        # Wait for authentication message with cookies
        auth_message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        auth_data = json.loads(auth_message)
        
        # Extract JWT token from cookies
        cookies = auth_data.get('cookies', '')
        token = None
        
        # Parse cookies to find access_token_cookie
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if cookie.startswith('access_token_cookie='):
                token = cookie.split('=', 1)[1]
                break
        
        if not token:
            await websocket.send(json.dumps({'error': 'No JWT token found in cookies'}))
            return False
        
        # Validate JWT token
        try:
            decoded_token = decode_token(token)
            user_id = decoded_token.get('sub')  # 'sub' is the subject (user_id)
            
            if not user_id:
                await websocket.send(json.dumps({'error': 'Invalid token: no user ID'}))
                return False
            
            # Send successful authentication response
            await websocket.send(json.dumps({'status': 'authenticated', 'user_id': user_id}))
            return True
            
        except InvalidTokenError as e:
            await websocket.send(json.dumps({'error': f'Invalid JWT token: {str(e)}'}))
            return False
            
    except asyncio.TimeoutError:
        await websocket.send(json.dumps({'error': 'Authentication timeout'}))
        return False
    except json.JSONDecodeError:
        await websocket.send(json.dumps({'error': 'Invalid JSON in authentication message'}))
        return False
    except Exception as e:
        await websocket.send(json.dumps({'error': f'Authentication failed: {str(e)}'}))
        return False

def decode_image_from_base64(img_b64):
    """Decode base64 image string to opencv/numpy image format"""
    try:
        # Decode base64 string to bytes
        img_bytes = base64.b64decode(img_b64)
        
        # Convert bytes to numpy array
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        
        # Decode image using OpenCV
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        return img
    except Exception:
        return None
    
def posture_score_from_keypoints(keypoints):
    """Calculate posture score from keypoints"""
    #Will write this when the metric is defined
    return 100

async def handle_inference(websocket, model_name: str):
    """Handle WebSocket connection with JWT authentication and inference"""
    # Perform authentication handshake
    if not await authenticate_websocket(websocket):
        await websocket.close()
        return
    
    # Check if model exists and has inferencers
    if model_name not in inferencers or inferencers[model_name] is None:
        await websocket.send(json.dumps({'error': f'Model {model_name} not available or not configured'}))
        await websocket.close()
        return
    
    async for message in websocket:
        try:
            data = json.loads(message)
            img_b64 = data.get('image')
            if img_b64 is None:
                await websocket.send(json.dumps({'error': 'No image provided'}))
                continue

            img = decode_image_from_base64(img_b64)
            if img is None:
                await websocket.send(json.dumps({'error': 'Invalid image data'}))
                continue

            # Select next GPU inferencer for the specific model
            gpu_index = next(gpu_cycle)
            inferencer = inferencers[model_name][gpu_index]

            # Run inference
            result_generator = inferencer(img, return_vis=False)
            result = next(result_generator)

            preds = result.get('predictions', None)
            if not preds or not isinstance(preds, list) or len(preds[0]) == 0:
                await websocket.send(json.dumps({'error': 'No person detected'}))
                continue

            keypoints = preds[0][0]['keypoints']
            posture_score = posture_score_from_keypoints(keypoints)

            await websocket.send(json.dumps({'keypoints': keypoints, 'posture_score': posture_score}))

        except Exception as e:
            await websocket.send(json.dumps({'error': str(e)}))

async def start_model_server(model_name: str):
    port = MODEL_CONFIGS[model_name]['port']
    print(f"Starting WebSocket server for model '{model_name}' at ws://{WEBSOCKET_HOST}:{port}")
    async with websockets.serve(lambda ws: handle_inference(ws, model_name), WEBSOCKET_HOST, port):
        await asyncio.Future()  # run forever

async def main():
    # Start a server for each model in MODEL_CONFIGS
    servers = [start_model_server(model_name) for model_name in MODEL_CONFIGS]
    await asyncio.gather(*servers)
 
if __name__ == '__main__':
    asyncio.run(main())