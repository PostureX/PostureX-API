# PostureX-API Backend Documentation

A comprehensive Flask-based REST API for posture analysis with real-time inference capabilities, file upload handling, and multi-model support. Built with Flask, MinIO object storage, WebSocket services, and PostgreSQL.

---

## 🏗️ Table of Contents
- [Project Architecture](#project-architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
  - [Authentication](#authentication)
  - [File Upload & Analysis](#file-upload--analysis)
  - [Analysis Management](#analysis-management)
- [Model Selection](#model-selection)
- [WebSocket Services](#websocket-services)
- [MinIO Integration](#minio-integration)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Project Architecture

```
PostureX-API/
├── src/
│   ├── config/           # Configuration files
│   │   ├── app_config.py
│   │   ├── database.py
│   │   └── websocket_config.py
│   ├── controllers/      # API route handlers
│   │   ├── auth_controller.py
│   │   ├── video_controller.py
│   │   ├── analysis_controller.py
│   │   └── minio_video_controller.py
│   ├── models/           # Database models
│   │   ├── user.py
│   │   └── analysis.py
│   ├── services/         # Business logic services
│   │   ├── minio.py
│   │   └── video_upload_analysis_service.py
│   └── utils/            # Utility functions
├── websocket_script_for_model_server/
│   ├── websocket_model_inference_service.py
│   └── websocket_config.py
├── migrations/           # Database migrations
├── app.py               # Application entry point
├── requirements.txt     # Python dependencies
└── docker-compose.yml   # Docker configuration
```

---

## ✨ Features

### 🔐 **Authentication System**
- JWT-based authentication with secure cookies
- User registration, login, and profile management
- Protected routes with role-based access

### 📁 **File Upload & Storage**
- **Unified Upload API**: Single endpoint for 1-4 files with explicit view specification
- **View-Specific Analysis**: Users specify actual camera angle (front, left, right, back)
- **Session-Based Processing**: Multiple files grouped by session for comprehensive analysis
- **MinIO Integration**: Scalable object storage with webhook processing
- **Model Selection**: Choose between different AI models (CX, GY)

### 🤖 **AI Model Support**
- **Multiple Models**: Support for different pose estimation models
- **WebSocket Inference**: Real-time pose analysis via WebSocket connections
- **Dynamic Port Selection**: Automatic model-to-port mapping
- **Error Handling**: Graceful fallback and error reporting

### 📊 **Analysis Management**
- **Asynchronous Processing**: Background analysis with status tracking
- **Result Storage**: JSON-based posture results with measurements
- **Feedback Generation**: Automated posture feedback based on scores
- **Progress Tracking**: Real-time status updates (pending/in_progress/completed/failed)

### 🔄 **Real-time Processing**
- **Webhook Integration**: MinIO-triggered automatic processing
- **Race Condition Handling**: Database locks for concurrent uploads
- **Retry Mechanisms**: Exponential backoff for failed operations

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database
- MinIO server
- CUDA-compatible GPU (for AI models)

### 1. Environment Setup

**Clone the repository:**
```bash
git clone <repository-url>
cd PostureX-API
```

**Install dependencies:**
```bash
# Flask API dependencies
pip install -r requirements.txt
```

**Environment configuration:**
```bash
cp .env.example .env
# Edit .env with your database and MinIO settings
```

### 2. Database Setup


**Step 1: Initialize Alembic (first time only):**
```bash
flask db init
```

**Step 2: Create Database Schema (if not already created):**
```bash
flask create-schema
```

**Step 3: Generate Migration Scripts:**
```bash
flask db migrate -m "init table"
```

**Step 4: Apply Migrations:**
```bash
flask db upgrade
```

> **Note:**
> If this is not your first time running migrations and you see errors about Alembic version, run the following SQL command in your database to reset Alembic:
> ```sql
> delete from alembic_version;
> ```

### 3. Start Services

**Start the Flask API:**
```bash
python app.py
```
- API available at: `http://localhost:5000`

### 4. Set up WebSocket Model Server:
**1. Upload PostureX-API\websocket_script_for_model_server folder to the model server**
**2. Setup environment if not setup:**

```bash
# On the model server, navigate to the uploaded folder and install dependencies:
cd /path/to/destination/websocket_script_for_model_server
pip install -r websocket_requirements.txt

# Ensure your AI model config and weights are also uploaded to `posture-x-models` folder on the server
# Or update the model paths in websocket_config.py to match your server's model locations
```

**Start the WebSocket Model Server:**
```bash
python websocket_model_inference_service.py
```
- CX Model: `ws://localhost:8894`
- GY Model: `ws://localhost:8893`

### 5. Create/Start MinIO Server:

**Step 1: Create MinIO Docker Container**
```bash
# Pull MinIO image
docker pull minio/minio:latest

# Create MinIO container with persistent storage
docker run -d \
  --name minio-server \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=ROOTUSER" \
  -e "MINIO_ROOT_PASSWORD=POSTUREX" \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

**Step 2: Access MinIO Console**
- MinIO Console: `http://localhost:9001`
- Username: `ROOTUSER`
- Password: `POSTUREX`

**Step 3: Configure Webhook**
Using MinIO Client (mc) in the docker container terminal
```bash
# Creating alias
docker exec minio-server mc alias set local http://localhost:9000 ROOTUSER POSTUREX

# Configure webhook endpoint
docker exec minio-server mc admin config set local notify_webhook:1 \
  endpoint="http://host.docker.internal:5000/api/minio/webhook" \

# Set webhook notification for PUT events
docker exec minio-server mc event add local/videos arn:minio:sqs::1:webhook --event put

# Restart MinIO to apply webhook configuration
docker restart minio-server
```
- MinIO API Endpoint: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

---

## 🤖 Model Selection

### Available Models

The system supports multiple AI models for pose estimation:

#### CX Model
- **Status**: ✅ Fully operational
- **Port**: 8894
- **Description**: High-accuracy posture analysis model
- **Configuration**: MMPose-based ResNet152

#### GY Model
- **Status**: ⚠️ Placeholder (development)
- **Port**: 8893
- **Description**: Alternative model (not yet configured)

### Model Usage

**Specify model in upload:**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@video.mp4" \
  -F "model=cx" \
  http://localhost:5000/api/video/upload
```

**Filename format:**
- Single upload: `modelname_originalfilename.ext`
- Multi-view: `modelname_view.ext`

**Error handling:**
If an invalid or unavailable model is specified, the API returns:
```json
{
  "error": "Invalid model: invalid_model. Available models: ['cx']",
  "available_models": ["cx"]
}
```

---

## ⚙️ Configuration

### Environment Variables


Create a `.env` file in the root directory:

```bash
# Database Configuration
DB_NAME=postgres
DB_USER=postgres
SCHEMA_NAME=spfposture
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# API Base URL
API_BASE_URL=http://address:port

# JWT Configuration
JWT_SECRET=salt

# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=ROOTUSER
MINIO_SECRET_KEY=POSTUREX
MINIO_SECURE=false
```

### WebSocket Model Configuration

**Model Service Configuration (`websocket_script_for_model_server/`):**

```python
WEBSOCKET_CONFIG = {
    'cx': {
        'port': 8894,
        'model_path': 'path/to/cx/model',
        'config_path': 'path/to/cx/config'
    },
    'gy': {
        'port': 8893,
        'model_path': 'path/to/gy/model',  # Not yet configured
        'config_path': 'path/to/gy/config'  # Not yet configured
    }
}
```

Ensure that the `websocket_model_inference_service.py` file is updated to include any new models or configurations.

---

### Database Schema

**Users Table:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Analysis Table:**
```sql
CREATE TABLE analysis (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(255),
    posture_result TEXT,
    feedback TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔧 Development

### Project Structure

```
PostureX-API/
├── api.py                          # Main Flask application
├── websocket_api.py               # WebSocket service entry point
├── requirements.txt               # Python dependencies
├── README.md                      # This documentation
├── .env.example                   # Environment variables template
├── src/
│   ├── controllers/
│   │   ├── auth_controller.py     # Authentication endpoints
│   │   ├── video_controller.py    # File upload endpoints
│   │   ├── minio_video_controller.py  # MinIO webhook handler
│   │   └── analysis_controller.py # Analysis management
│   ├── models/
│   │   ├── user.py               # User database model
│   │   └── analysis.py           # Analysis database model
│   ├── services/
│   │   ├── media_analysis_service.py  # Analysis orchestration
│   │   ├── minio_service.py      # MinIO client wrapper
│   │   └── websocket_client.py   # WebSocket communication
│   └── utils/
│       ├── auth.py               # JWT utilities
│       └── database.py           # Database configuration
└── websocket_script_for_model_server/
    ├── websocket_model_inference_service.py  # Model server
    ├── pose_estimation_service.py            # Pose analysis logic
    └── requirements.txt                      # Model server dependencies
```

### Adding New Models

**1. Configure WebSocket endpoint:**
```python
# In websocket_script_for_model_server/websocket_model_inference_service.py
WEBSOCKET_CONFIG = {
    'your_model': {
        'port': 8895,
        'model_path': 'path/to/your/model',
        'config_path': 'path/to/your/config'
    }
}
```

**2. Update model mapping:**
```python
# In src/controllers/minio_video_controller.py
def get_media_analyzer_for_model(model_name):
    model_ports = {
        'cx': 8894,
        'gy': 8893,
        'your_model': 8895  # Add your model here
    }
```

**3. Test model availability:**
```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@test.mp4" \
  -F "model=your_model" \
  http://localhost:5000/api/video/upload
```

### Testing

**Run unit tests:**
```bash
python -m pytest tests/
```

**Test endpoints:**
```bash
# Test authentication
curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  http://localhost:5000/auth/login

# Test file upload
curl -X POST -H "Authorization: Bearer <token>" \
  -F "file=@test.mp4" -F "model=cx" \
  http://localhost:5000/api/video/upload
```

---

## 🛠️ Troubleshooting

### Common Issues

**1. WebSocket Connection Failed**
```
Error: Connection refused to ws://localhost:8894
```
**Solution:** Ensure the WebSocket model server is running:
```bash
python websocket_script_for_model_server/websocket_model_inference_service.py
```

**2. MinIO Upload Failed**
```
Error: Failed to upload file to MinIO
```
**Solution:** Check MinIO service and credentials:
```bash
# Test MinIO connection
curl http://localhost:9000/minio/health/live
```

**3. Database Connection Error**
```
Error: database "posturex_db" does not exist
```
**Solution:** Create the database:
```bash
createdb posturex_db
python setup_database.py
```

**4. JWT Token Invalid**
```
Error: Token has expired
```
**Solution:** Login again to get a fresh token:
```bash
curl -X POST /auth/login -d '{"email":"user@example.com","password":"password"}'
```

**5. Model Not Available**
```
Error: Invalid model: invalid_model
```
**Solution:** Use an available model (`cx`) or configure the requested model.

### Debug Mode

**Enable debug logging:**
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python api.py
```

**WebSocket debug:**
```bash
# Enable verbose logging in WebSocket service
python websocket_api.py --debug
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Write unit tests for new features

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Contact the development team
- Check the troubleshooting section above

---

**Made with ❤️ by the PostureX Team**
