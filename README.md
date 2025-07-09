# SPF Posture Backend API Documentation

This backend is built with Flask and provides authentication, user analysis, and inference endpoints for the SPF Posture application. All authentication uses JWT tokens stored in cookies. CORS is enabled for `http://localhost:5173` and `http://127.0.0.1:5173`.

## Authentication Routes

### Register
- **POST** `/auth/register`
- **Body:** `{ "name": string, "password": string }`
- **Response:** User ID, sets JWT cookies
- **Notes:** Registers a new user. Returns 409 if user exists.

### Login
- **POST** `/auth/login`
- **Body:** `{ "name": string, "password": string }`
- **Response:** User info, sets JWT cookies
- **Notes:** Logs in a user. Returns 401 if credentials are invalid.

### Logout
- **POST** `/auth/logout`
- **Response:** Success message, unsets JWT cookies
- **Auth:** Requires valid access token (JWT cookie)

### Refresh Token
- **POST** `/auth/refresh`
- **Response:** New access token set in cookie
- **Auth:** Requires valid refresh token (JWT cookie)

## User Analysis Routes

### Create Analysis
- **POST** `/api/analysis`
- **Body:** `{ "text": string, "video_url": string }`
- **Response:** Analysis ID
- **Auth:** Requires valid access token

### Get All Analyses
- **GET** `/api/analysis`
- **Response:** List of analyses for the current user
- **Auth:** Requires valid access token

### Get Specific Analysis
- **GET** `/api/analysis/<analysis_id>`
- **Response:** Analysis data for the given ID (if owned by user)
- **Auth:** Requires valid access token

## Inference Routes

### CX Model Inference
- **GET** `/api/inference/cx_model`
- **Response:** Example inference result for CX model
- **Auth:** Requires valid access token

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
  - GY model connects to WebSocket server on port 8892
  - Connects to respective WebSocket servers for real-time posture analysis

## WebSocket Servers

### CX Model WebSocket Server (`websocket_cx_api.py`)
- **URL:** `ws://10.3.250.181:8891`
- **Purpose:** Real-time pose inference using the CX model with MMPose
- **Configuration:** Uses actual model files and GPU acceleration
- **Message Format:** `{ "image": "base64-encoded-image-string" }`
- **Response:** `{ "keypoints": [...], "posture_score": number, "model": "cx" }`
- **Dependencies:** Requires MMPose, CUDA, and helper functions

### GY Model WebSocket Server (`websocket_gy_api.py`)
- **URL:** `ws://10.3.250.181:8892`
- **Purpose:** Placeholder server for GY model (returns mock data)
- **Configuration:** All model parameters set to None
- **Message Format:** `{ "image": "base64-encoded-image-string" }`
- **Response:** `{ "keypoints": [...], "posture_score": 75.0, "model": "gy", "note": "..." }`
- **Note:** Returns fixed mock keypoints for testing until GY model is implemented

## Error Handling
- **404:** `{ "message": "Endpoint not found" }`
- **500:** `{ "message": "Internal server error" }`

## Notes
- All requests that require authentication must include cookies. On the frontend, use `credentials: 'include'` (fetch) or `withCredentials: true` (axios).
- JWT cookies are set for both access and refresh tokens.
- CORS is configured for local development.
- For live inferencing, you can either use the REST API endpoints or connect directly to the WebSocket servers for better performance.
- The `/api/models` endpoint provides skeleton connection data for frontend pose visualization.

## Model Configuration
- **CX Model**: 
  - Model Config: `./posture-x-models/td-hm_res152_8xb32-210e_coco-wholebody-256x192.py`
  - Checkpoint: `./posture-x-models/best_coco-wholebody_AP_epoch_210.pth`
  - Device: `cuda` (GPU acceleration with 4 GPUs)
  - Status: Fully configured and operational
- **GY Model**: 
  - Model Config: `None`
  - Checkpoint: `None` 
  - Device: `None`
  - Status: Placeholder - returns mock data

## Running the Application

### Start All Servers
You need to run these commands in **separate terminals**:

```bash
# Terminal 1 - Flask REST API
python api.py

# Terminal 2 - CX Model WebSocket Server
python websocket_cx_api.py

# Terminal 3 - GY Model WebSocket Server (Optional - for testing)
python websocket_gy_api.py
```

### Expected Output
- **Flask API**: Runs on `http://localhost:5000`
- **CX WebSocket**: Runs on `ws://10.3.250.181:8891`
- **GY WebSocket**: Runs on `ws://10.3.250.181:8892`

## Usage Examples

### REST API Live Inference
```javascript
// Login first
const loginResponse = await fetch('http://localhost:5000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ name: 'username', password: 'password' })
});

// Get available models
const modelsResponse = await fetch('http://localhost:5000/api/models', {
  credentials: 'include'
});

// Send image for inference
const inferenceResponse = await fetch('http://localhost:5000/api/live_inferencing/cx', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ image: base64ImageString })
});
```

### Direct WebSocket Connection
```javascript
const ws = new WebSocket('ws://10.3.250.181:8891'); // CX model
ws.onopen = () => {
  ws.send(JSON.stringify({ image: base64ImageString }));
};
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Keypoints:', data.keypoints);
  console.log('Posture Score:', data.posture_score);
};
```

## Dependencies
Make sure to install the required packages:
```bash
pip install -r requirements.txt
```

Key dependencies include:
- **Flask & Flask-CORS** - Web framework and CORS handling
- **Flask-JWT-Extended** - JWT authentication with cookies
- **psycopg2** - PostgreSQL database connection
- **websockets** - WebSocket client functionality for REST API
- **bcrypt** - Password hashing
- **MMPose** - Pose estimation (for CX model only)
- **OpenCV** - Image processing
- **NumPy** - Numerical operations

### Additional Requirements for CX Model
The CX WebSocket server requires:
- CUDA-compatible GPU
- MMPose library with dependencies
- Model files in `./posture-x-models/` directory
- Helper functions in `helper.py`

### File Structure
```
PostureX-API/
├── api.py                 # Flask REST API server
├── websocket_cx_api.py    # CX model WebSocket server
├── websocket_gy_api.py    # GY model WebSocket server (placeholder)
├── helper.py              # Helper functions for image processing
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not tracked)
└── posture-x-models/      # Model files directory
    ├── td-hm_res152_8xb32-210e_coco-wholebody-256x192.py
    └── best_coco-wholebody_AP_epoch_210.pth
```
