### GY Model Inference
- **GET** `/api/inference/gy_model`
- **Response:** Example inference result for GY model
- **Auth:** Requires valid access token

## Live Inferencing Routes

### Get Available Models
- **GET** `/api/models`
- **Response:** List of available models with their configurations and skeleton connections
- **Auth:** Requires valid access token
- **Notes:** Returns model information including WebSocket URLs and skeleton data for pose visualization

### Live Inference
- **POST** `/api/live_inferencing/<model_name>`
- **Body:** `{ "image": "base64-encoded-image-string" }`
- **Response:** Real-time inference results with keypoints and posture score
- **Auth:** Requires valid access token
- **Notes:** 
  - Available models: `cx`, `gy`
  - CX model connects to WebSocket server on port 8891
  - GY model connects to WebSocket server on port 8892 (placeholder)
  - The frontend can connect directly to WebSocket servers for real-time streaming

## WebSocket Servers

### CX Model WebSocket Server
- **File:** `websocket_cx_api.py`
- **URL:** `ws://10.3.250.181:8891`
- **Purpose:** Real-time pose inference using the CX model
- **Message Format:** `{ "image": "base64-encoded-image-string" }`
- **Response:** `{ "keypoints": [...], "posture_score": number, "model": "cx" }`

### GY Model WebSocket Server  
- **File:** `websocket_gy_api.py`
- **URL:** `ws://10.3.250.181:8892`
- **Purpose:** Placeholder for GY model (returns mock data)
- **Message Format:** `{ "image": "base64-encoded-image-string" }`
- **Response:** `{ "keypoints": [...], "posture_score": number, "model": "gy", "note": "..." }`

## Notes