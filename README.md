# PostureX-API Backend Documentation

A comprehensive Flask-based REST API for posture analysis with real-time inference capabilities, file upload handling, and multi-model support. Built with Flask, MinIO object storage, WebSocket services, and PostgreSQL.

---

## 🏗️ Table of Contents
- [Project Architecture](#🏗️-project-architecture)
- [Features](#✨-features)
- [Quick Start](#🚀-quick-start)
- [API Documentation](#api-documentation)
- [Model Selection](#🤖-model-selection)
- [Development](#🔧-development)
- [Troubleshooting](#🛠️-troubleshooting)
- [Database Schema](#database-schema)
- [Configuration](#⚙️-configuration)
- [Contributing](#🤝-contributing)
- [License](#📄-license)
- [Support](#🆘-support)

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

See [QUICKSTART.md](QUICKSTART.md) for step-by-step setup instructions for both [manual](QUICKSTART.md#manual-deployment) and [Docker Compose](QUICKSTART.md#docker-compose-deployment) deployment.

---

## API Documentation

- [API Documentation](/API_ROUTES.md)
  - [Authentication](/API_ROUTES.md#authentication)
  - [File Upload & Analysis](/API_ROUTES.md#file-upload--analysis)
  - [Analysis Management](/API_ROUTES.md#analysis-management)

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
