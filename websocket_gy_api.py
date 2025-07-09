import asyncio
import websockets
import numpy as np
import cv2
import base64
from mmpose.apis import MMPoseInferencer
import json

# --------- GY MODEL CONFIGURATION ---------
MODEL_CONFIG = None
CHECKPOINT_PATH = None
DEVICE = None
HOST = '10.3.250.181'
PORT = 8892
# ----------------------------------------

# Note: GY model configuration is set to None - model not yet implemented
# This is a placeholder server that returns mock data

async def handle_inference(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
            img_b64 = data.get('image')
            if img_b64 is None:
                await websocket.send(json.dumps({'error': 'No image provided'}))
                continue

            # Since GY model is not configured, return mock keypoints and posture score
            # This is placeholder data for testing purposes
            mock_keypoints = [
                [100, 50], [120, 60], [140, 70], [160, 80], [180, 90],   # Right arm
                [100, 50], [80, 60], [60, 70], [40, 80], [20, 90],       # Left arm
                [100, 120], [120, 140], [100, 160], [80, 180], [60, 200], # Body
                [140, 200], [160, 220], [100, 30]                        # Legs and head
            ]
            
            # Mock posture score
            mock_posture_score = 75.0

            await websocket.send(json.dumps({
                'keypoints': mock_keypoints,
                'posture_score': mock_posture_score,
                'model': 'gy',
                'note': 'This is a placeholder GY model with mock data. Model configuration is not yet implemented.'
            }))

        except Exception as e:
            await websocket.send(json.dumps({'error': str(e)}))

async def main():
    async with websockets.serve(handle_inference, HOST, PORT):
        print(f"GY Model WebSocket server (placeholder) started at ws://{HOST}:{PORT}")
        print("Note: GY model configuration is None - returning mock data")
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main())
