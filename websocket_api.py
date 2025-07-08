import asyncio
import websockets
import numpy as np
import cv2
import base64
import json
from mmpose.apis import MMPoseInferencer
import itertools

from helper import *

# --------- USER CONFIGURABLE CONSTANTS ---------
MODEL_CONFIG = './posture-x-models/td-hm_res152_8xb32-210e_coco-wholebody-256x192.py'  # or your wholebody config
CHECKPOINT_PATH = './posture-x-models/best_coco-wholebody_AP_epoch_210.pth'           # or your wholebody checkpoint
DEVICE = 'cuda'                                                                 # set to 'cuda' for GPU, 'cpu' for CPU
HOST = '10.3.250.181'
PORT = 8891
# -----------------------------------------------

# Load model per gpu at startup
NUM_GPUS = 4
inferencers = [
    MMPoseInferencer(MODEL_CONFIG, pose2d_weights=CHECKPOINT_PATH, device=f'cuda:{i}')
    for i in range(NUM_GPUS)
]

gpu_cycle = itertools.cycle(range(NUM_GPUS))


async def handle_inference(websocket):
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

            # Select next GPU inferencer
            gpu_index = next(gpu_cycle)
            inferencer = inferencers[gpu_index]

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

async def main():
    async with websockets.serve(handle_inference, HOST, PORT):
        print(f"WebSocket server started at ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    asyncio.run(main())
