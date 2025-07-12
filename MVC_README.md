# MVC Structure for PostureX API

## Overview
This is the MVC (Model-View-Controller) version of the PostureX API, refactored from the original monolithic `api.py` file to follow proper separation of concerns.

## Project Structure

```
app/
├── __init__.py              # Flask application factory
├── config/
│   ├── __init__.py
│   ├── app_config.py        # Flask app configuration
│   ├── database.py          # Database configuration
│   └── websocket_config.py  # WebSocket server configuration
├── models/
│   ├── __init__.py
│   ├── user.py             # User data model
│   └── analysis.py         # Analysis and inference data models
├── controllers/
│   ├── __init__.py
│   ├── auth_controller.py   # Authentication routes and logic
│   ├── analysis_controller.py # Analysis management routes
│   └── inference_controller.py # Live inference routes
├── services/
│   ├── __init__.py
│   └── websocket_service.py # WebSocket communication service
└── utils/
    ├── __init__.py
    └── helpers.py          # Utility functions
main.py                     # Application entry point
```

## Key Components

### Configuration Layer (`app/config/`)
- **app_config.py**: Flask application settings, JWT configuration
- **database.py**: PostgreSQL connection settings and management
- **websocket_config.py**: WebSocket server configurations for CX/GY models

### Data Models (`app/models/`)
- **user.py**: User authentication and profile models
- **analysis.py**: Analysis storage and pose inference result models

### Controllers (`app/controllers/`)
- **auth_controller.py**: Handles login, logout, registration, profile management
- **analysis_controller.py**: Manages saving, retrieving, and deleting analysis results
- **inference_controller.py**: Handles live inference requests to WebSocket servers

### Services (`app/services/`)
- **websocket_service.py**: Manages communication with external WebSocket inference servers

### Utilities (`app/utils/`)
- **helpers.py**: Common utility functions for logging, validation, response formatting

## Usage

### Running the Application
```bash
python main.py
```

The application will start on `http://localhost:5000` with the same API endpoints as the original `api.py`.

### API Endpoints

#### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and set JWT cookie
- `POST /api/auth/logout` - Logout and clear JWT cookie
- `GET /api/auth/profile` - Get user profile (requires authentication)

#### Analysis Management
- `POST /api/analysis/save` - Save analysis results
- `GET /api/analysis/list` - Get user's analyses
- `GET /api/analysis/<id>` - Get specific analysis
- `DELETE /api/analysis/<id>` - Delete analysis

#### Live Inference
- `GET /api/live_inferencing/models` - Get available models
- `POST /api/live_inferencing/<model_name>` - Perform inference

#### System
- `GET /api/health` - Health check endpoint

## Benefits of MVC Structure

1. **Separation of Concerns**: Each component has a single responsibility
2. **Maintainability**: Easier to modify individual components without affecting others
3. **Testability**: Controllers and services can be unit tested independently
4. **Scalability**: Easy to add new features by extending existing patterns
5. **Code Reusability**: Services and utilities can be shared across controllers

## Migration from Original api.py

This MVC structure maintains 100% API compatibility with the original `api.py` file. All endpoints work identically, but the code is now organized into logical, maintainable components.

To use this version instead of the original:
1. Ensure all dependencies from `requirements.txt` are installed
2. Make sure PostgreSQL database and WebSocket servers are running
3. Run `python main.py` instead of `python api.py`

The original `api.py` file remains unchanged and can still be used if preferred.
