# API Routes

## Authentication

### Register User
```
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "password": "securepassword"
}
```
**Response:**
```json
{
  "message": "User registered successfully",
  "name": "John Doe"
}
```

### Login
```
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```
**Response:**
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  },
  "access_token": "jwt_token_here"
}
```

### Logout
```
POST /auth/logout
Authorization: Bearer <jwt_token>
```

### Get Profile
```
GET /auth/profile
Authorization: Bearer <jwt_token>
```

---

## File Upload & Analysis

### Unified Upload API
Upload 1-4 files for posture analysis. Users must specify the actual view (front, left, right, back) for each file.

```
POST /api/video/upload
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

Form Data:
- session_id: "session_123" (required)
- model: "cx" (optional, defaults to "cx")
- front: <front_view_file> (optional)
- left: <left_view_file> (optional)  
- right: <right_view_file> (optional)
- back: <back_view_file> (optional)
```

**Single View Example:**
```javascript
const formData = new FormData();
formData.append('left', leftVideoFile);  // User specifies it's the left view
formData.append('session_id', 'session_123');
formData.append('model', 'cx');

fetch('/api/video/upload', {
    method: 'POST',
    body: formData,
    headers: { 'Authorization': 'Bearer ' + token }
});
```

**Multi-View Example:**
```javascript
const formData = new FormData();
formData.append('front', frontVideoFile);
formData.append('left', leftVideoFile);
formData.append('right', rightVideoFile);
formData.append('back', backVideoFile);
formData.append('session_id', 'session_123');
formData.append('model', 'cx');

fetch('/api/video/upload', {
    method: 'POST',
    body: formData,
    headers: { 'Authorization': 'Bearer ' + token }
});
```

**Response:**
```json
{
  "message": "All files uploaded successfully. 2 files uploaded. Analysis will begin automatically.",
  "session_id": "session_123",
  "model": "cx",
  "uploaded_files": {
    "left": {
      "file_url": "http://minio:9000/videos/user123/session_123/cx_left.mp4",
      "file_type": "video"
    },
    "right": {
      "file_url": "http://minio:9000/videos/user123/session_123/cx_right.mp4",
      "file_type": "video"
    }
  },
  "views_uploaded": ["left", "right"]
}
```

### Delete Files
```
POST /api/video/delete
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "filename": "cx_video.mp4"
}
```

### Delete Multi-view Session
```
POST /api/video/delete/multiview
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "session_id": "session_123"
}
```

---

## Analysis Management

### List User Analyses
```
GET /api/analysis/list
Authorization: Bearer <jwt_token>
```
**Response:**
```json
{
  "analyses": [
    {
      "id": 1,
      "created_at": "2025-01-15T10:30:00"
    }
  ]
}
```

### Get Analysis Details
```
GET /api/analysis/<analysis_id>
Authorization: Bearer <jwt_token>
```
**Response:**
```json
{
  "id": 1,
  "user_id": 123,
  "filename": "video",
  "posture_result": "{\"front\": {\"score\": {\"overall_score\": 85}, \"measurements\": {...}}}",
  "feedback": "Front view: Good posture with minor improvements needed.",
  "status": "completed",
  "created_at": "2025-01-15T10:30:00"
}
```

### Re-attempt Analysis
```
POST /api/analysis/reattempt/<analysis_id>
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "model": "cx"  // Optional: specify model to use (defaults to 'cx')
}
```
**Response:**
```json
{
  "message": "Analysis re-attempt initiated successfully",
  "analysis_id": 1,
  "model": "cx",
  "status": "in_progress"
}
```
**Error Response (Invalid Model):**
```json
{
  "error": "Invalid model: invalid_model. Available models: ['cx']",
  "available_models": ["cx"]
}
```

### Get Detailed Analysis Data
Get detailed frame-by-frame analysis data stored in MinIO:

```
GET /api/analysis/detailed/<session_id>
Authorization: Bearer <jwt_token>

# Optional: Get specific side data
GET /api/analysis/detailed/<session_id>?side=front
```
**Response (List available sides):**
```json
{
  "available_sides": ["front", "left"],
  "files": [
    "user123/session_456/detailed_front.json",
    "user123/session_456/detailed_left.json"
  ]
}
```
**Response (Specific side - Video):**
```json
{
  "file_type": "video",
  "view": "front",
  "detected_view": "front",
  "analysis_timestamp": 1641234567.89,
  "total_frames": 150,
  "processed_frames": 5,
  "frame_skip": 30,
  "frames_data": [
    {
      "frame_index": 0,
      "measurements": {...}
    },
    {
      "frame_index": 30,
      "measurements": {...}
    }
  ],
  "aggregated_results": {
    "confidence": 85.2,
    "keypoints": {...}
  }
}
```
**Response (Specific side - Image):**
```json
{
  "file_type": "image",
  "view": "front",
  "detected_view": "front", 
  "analysis_timestamp": 1641234567.89,
  "image_data": {
    "keypoints": {...},
    "measurements": {...}
  }
}
```

### Delete Analysis
```
DELETE /api/analysis/<analysis_id>
Authorization: Bearer <jwt_token>
```
**Response (Success):**
```json
{
  "message": "Analysis and associated files deleted successfully",
  "analysis_id": 123,
  "session_id": "session_456"
}
```
**Response (Partial Success):**
```json
{
  "message": "Analysis deleted from database, but some analysis files may remain in storage",
  "analysis_id": 123,
  "session_id": "session_456",
  "warning": "Failed to delete some analysis files from MinIO"
}
```