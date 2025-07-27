# MinIO Webhook Video Analysis Setup

This document explains how to set up and use the automatic video analysis feature with MinIO webhooks.

## Overview

The system automatically analyzes videos uploaded to MinIO and stores posture analysis results in the database. It supports both single-view and multi-view (front, left, right, back) video analysis.

## Architecture

1. **Video Upload**: Users upload videos via `/api/video/upload`
2. **MinIO Webhook**: MinIO triggers a webhook when videos are uploaded
3. **Background Processing**: Videos are analyzed frame-by-frame using pose estimation
4. **Database Storage**: Results are stored in the `analysis` table with progress tracking
5. **User Notification**: Frontend can poll for progress and completion status

## Setup Instructions

### 1. Database Migration

Run the migration to add the progress field:

```bash
flask db upgrade
```

### 2. MinIO Webhook Configuration

Configure MinIO to send webhook events to your Flask app:

```bash
# Set up MinIO client (mc)
mc alias set myminio http://localhost:9000 minioadmin minioadmin

# Add webhook notification for the videos bucket
mc event add myminio/videos arn:minio:sqs::1:webhook --event put
```

Or using MinIO environment variables:

```env
MINIO_NOTIFY_WEBHOOK_ENABLE_1=on
MINIO_NOTIFY_WEBHOOK_ENDPOINT_1=http://your-flask-app/webhook/minio/video
MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_1=your-auth-token  # optional
```

### 3. WebSocket Service (Optional)

Ensure your WebSocket inference service is running on the configured port (default: 8001).

## API Usage

### Single Video Upload

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@exercise_video.mp4" \
  http://localhost:5000/api/video/upload
```

### Multi-View Upload

For multi-view analysis, include `session_id` and `view` parameters:

```bash
# Upload front view
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@front_view.mp4" \
  -F "session_id=session_123" \
  -F "view=front" \
  http://localhost:5000/api/video/upload

# Upload left view
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@left_view.mp4" \
  -F "session_id=session_123" \
  -F "view=left" \
  http://localhost:5000/api/video/upload

# Upload right view
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@right_view.mp4" \
  -F "session_id=session_123" \
  -F "view=right" \
  http://localhost:5000/api/video/upload

# Upload back view
curl -X POST \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "video=@back_view.mp4" \
  -F "session_id=session_123" \
  -F "view=back" \
  http://localhost:5000/api/video/upload
```

### Check Analysis Progress

```bash
curl -X GET \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:5000/api/analysis/ANALYSIS_ID
```

Response example:
```json
{
  "id": 1,
  "user_id": 123,
  "filename": "session_123",
  "status": "in_progress",
  "progress": 75,
  "posture_result": "{\"front\": {\"overall_score\": 85}, \"left\": {\"overall_score\": 82}, \"right\": {\"overall_score\": 80}}",
  "feedback": "Front view: Good posture. Left view: Minor improvements needed.",
  "created_at": "2025-07-22T12:00:00Z"
}
```

## File Naming Convention

### Single View
- MinIO Path: `{user_id}/{filename}.mp4`
- Session ID: `filename` (without extension)

### Multi-View
- MinIO Path: `{user_id}/{session_id}/{view}.mp4`
- Session ID: User-provided session identifier
- Views: `front`, `left`, `right`, `back`

## Database Schema

The `analysis` table stores results:

```sql
CREATE TABLE analysis (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,  -- session_id for grouping
    posture_result TEXT NOT NULL,  -- JSON string
    feedback TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100
    created_at TIMESTAMP DEFAULT NOW()
);
```

## JSON Score Format

### Single View
```json
{
  "single": {
    "overall_score": 85,
    "view": "single",
    "frame_count": 120,
    "metrics": {
      "general_posture": 0.85
    }
  }
}
```

### Multi-View
```json
{
  "front": {
    "overall_score": 85,
    "view": "front",
    "frame_count": 120,
    "metrics": {
      "foot_alignment": 0.8
    }
  },
  "left": {
    "overall_score": 82,
    "view": "left", 
    "frame_count": 115,
    "metrics": {
      "back_angle": 5.2,
      "head_tilt": -2.1
    }
  },
  "right": {
    "overall_score": 80,
    "view": "right",
    "frame_count": 118,
    "metrics": {
      "back_angle": 4.8,
      "head_tilt": -1.8
    }
  },
  "back": {
    "overall_score": 78,
    "view": "back",
    "frame_count": 122,
    "metrics": {
      "shoulder_alignment": 0.9
    }
  }
}
```

## Status Values

- `pending`: Analysis not started
- `in_progress`: Currently analyzing videos
- `completed`: All videos analyzed successfully
- `failed`: Analysis failed due to error

## Progress Calculation

- **Single View**: 0% → 100% when analysis completes
- **Multi-View**: 25% per view (front, left, right, back)

## Frontend Integration

### Polling for Progress

```javascript
async function checkAnalysisProgress(analysisId) {
  const response = await fetch(`/api/analysis/${analysisId}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const analysis = await response.json();
  
  if (analysis.status === 'completed') {
    console.log('Analysis complete!', analysis.posture_result);
    return true;
  } else if (analysis.status === 'failed') {
    console.error('Analysis failed');
    return true;
  } else {
    console.log(`Progress: ${analysis.progress}%`);
    return false;
  }
}

// Poll every 2 seconds
const pollInterval = setInterval(async () => {
  const isComplete = await checkAnalysisProgress(analysisId);
  if (isComplete) {
    clearInterval(pollInterval);
  }
}, 2000);
```

## Troubleshooting

### Webhook Not Triggered
1. Check MinIO configuration: `mc admin config get myminio notify_webhook`
2. Verify webhook endpoint is accessible from MinIO
3. Check MinIO logs for webhook errors

### Analysis Fails
1. Check video format is supported (MP4 recommended)
2. Verify WebSocket inference service is running
3. Check application logs for error details

### Slow Analysis
1. Reduce frame sampling rate in `VideoAnalysisService`
2. Use smaller video files for testing
3. Ensure sufficient GPU memory for inference

## Configuration

Key environment variables:

```env
# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false

# WebSocket Configuration
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8001

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost/dbname
```
