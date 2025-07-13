# PostureX-API Backend Documentation

This backend provides authentication, user analysis, and real-time pose inference for the PostureX application. It is built with Flask (REST API) and Python asyncio (WebSocket services).

---

## Table of Contents
- [Project Structure](#project-structure)
- [How to Run](#how-to-run)
- [REST API Routes](#rest-api-routes)
  - [Authentication](#authentication)
  - [User Analysis](#user-analysis)
  - [Live Inference](#live-inference)
- [WebSocket Services](#websocket-services)
- [Model Configuration](#model-configuration)
- [Error Handling](#error-handling)
- [Dependencies](#dependencies)
- [Database Migrations](#database-migrations)
- [Current Models](#current-models)

---

## Project Structure
```
src/
├── config/           # App, database, and websocket configs
├── controllers/      # Route handlers (auth, analysis, inference)
├── models/           # Data models (User, Analysis)
├── services/         # WebSocket model servers
├── utils/            # Helper functions
├── __init__.py       # Flask app factory
app.py               # App entry point
```

---

## How to Run

**1. Install dependencies:**
```bash
pip install -r flask_requirements.txt
```

**2. Start the Flask REST API:**
```bash
python app.py
```
- Runs on `http://localhost:5000`

**3. Start the WebSocket Model Service:**
```bash
python src/services/websocket_models.py
```
- Starts a WebSocket server for each model (CX, GY) on their configured ports.

**Note:** Run each service in a separate terminal.

---

## REST API Routes

### Authentication

- **Register:**  
  `POST /api/auth/register`  
  **Body:** `{ "email": string, "name": string, "password": string }`  
  **Response:** `{ "message": "...", "name": string }`  
  **Notes:** Registers a new user. Returns error if user exists.

- **Login:**  
  `POST /api/auth/login`  
  **Body:** `{ "email": string, "password": string }`  
  **Response:** `{ "message": "...", "user": {...}, "access_token": string }`  
  **Notes:** Sets JWT cookie for authentication.

- **Logout:**  
  `POST /api/auth/logout`  
  **Response:** `{ "message": "Logged out successfully" }`  
  **Auth:** Requires valid JWT cookie.

- **Profile:**  
  `GET /api/auth/profile`  
  **Response:** `{ "user": {...} }`  
  **Auth:** Requires valid JWT cookie.

---

### User Analysis

- **Create Analysis:**  
  `POST /api/analysis/save`  
  **Body:** `{ "video_url": string, "text": string }`  
  **Response:** `{ "message": "...", "analysis_id": int }`  
  **Auth:** Requires valid JWT cookie.

- **List Analyses:**  
  `GET /api/analysis/list`  
  **Response:** `{ "analyses": [ ... ] }`  
  **Auth:** Requires valid JWT cookie.

- **Get Analysis:**  
  `GET /api/analysis/<analysis_id>`  
  **Response:** `{ ...analysis data... }`  
  **Auth:** Requires valid JWT cookie.

- **Delete Analysis:**  
  `DELETE /api/analysis/<analysis_id>`  
  **Response:** `{ "message": "Analysis deleted successfully" }`  
  **Auth:** Requires valid JWT cookie.

---

## WebSocket Services

- **Service File:** `src/services/websocket_models.py`
- **Purpose:** Serves real-time pose inference for each model (CX, GY) on separate ports.
- **Authentication:** Requires JWT token (sent in cookies) for each connection.
- **Message Format:**  
  - **Request:** `{ "image": "base64-encoded-image-string" }`  
  - **Response:** `{ "keypoints": [...], "posture_score": number }`
- **How to Connect:**  
  - CX: `ws://<host>:8891`  
  - GY: `ws://<host>:8892`

---

## Model Configuration

- **CX Model:**  
  - Config: `./posture-x-models/td-hm_res152_8xb32-210e_coco-wholebody-256x192.py`
  - Checkpoint: `./posture-x-models/best_coco-wholebody_AP_epoch_210.pth`
  - Device: `cuda` (4 GPUs)
  - Status: Fully operational

- **GY Model:**  
  - Config: `None`
  - Checkpoint: `None`
  - Device: `None`
  - Status: Placeholder (returns mock data)

---

## Error Handling

- **404:** `{ "error": "Endpoint not found" }`
- **500:** `{ "error": "Internal server error" }`
- **Other errors:** Standardized error messages in JSON

---

## Dependencies

Install all required packages:
```bash
pip install -r flask_requirements.txt
```
- Flask, Flask-JWT-Extended, Flask-CORS
- psycopg2
- websockets
- numpy, opencv-python
- mmpose (for CX model)
- bcrypt

---

## Database Migrations

**1. Initialize migration repository (first time only):**
```bash
flask db init
```

**2. Create a migration after changing models:**
```bash
flask db migrate -m "Describe your change"
```

**3. Apply migrations to the database:**
```bash
flask db upgrade
```

**4. (Optional) Check migration status/history:**
```bash
flask db history
flask db current
```

**5. (Optional) Rollback migration:**
```bash
flask db downgrade
```

---

## Current Models

### User Model (`src/models/user.py`)
```python
class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'spfposture'}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade='all, delete-orphan')
```

### Analysis Model (`src/models/analysis.py`)
```python
class Analysis(db.Model):
    __tablename__ = 'analysis'
    __table_args__ = {'schema': 'spfposture'}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('spfposture.users.id'), nullable=False)
    video_url = db.Column(db.Text, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

---

## Notes

- All authenticated requests require cookies (JWT).
- CORS is enabled for local development.
- For best performance, use direct WebSocket connections for live inference.
- The backend is modular: REST API and WebSocket services run independently.

---

**For more details, see the code in `src/controllers/`, `src/services/`, and `src/config/`.**
