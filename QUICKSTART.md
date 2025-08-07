# 🚀 Quick Start

There are two ways to host the PostureX-API backend:

---

## 1. [Manual](#manual-deployment)

You install and run all dependencies (Python, PostgreSQL, MinIO, etc.) directly on your machine or server. This gives you full control and is useful for development, debugging, or custom production setups.  
See the detailed steps below for manual setup.

---

## 2. [Docker Compose (recommended)](#docker-compose-deployment)

You use Docker Compose to orchestrate all services (Flask API, PostgreSQL, MinIO, etc.) in isolated containers with a single command. This is the recommended way for most users, as it simplifies setup, ensures environment consistency, and makes deployment and scaling easier.

---

Continue with the instructions below for your chosen deployment method.

## Manual Deployment

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

## Docker Compose Deployment

Before proceeding, ensure you have the WebSocket model server set up and running.  
Refer to the [WebSocket setup guide](#4-set-up-websocket-model-server) above for details.

### Step 1: Set up your environment file

Copy the example environment file and edit as needed:
```bash
cp .env.example .env
```
Make sure to set values for `TELEGRAM_BOT_TOKEN` and `GEMINI_API_KEY` in your `.env` file.

[Where to get the telegram bot token?](https://core.telegram.org/bots#how-do-i-create-a-bot)

[Where to get the Gemini API key?](https://aistudio.google.com/apikey)

Also make sure to set `WEBSOCKET_HOST` to the host endpoint of your websocket model server.

You may modify any of the environment variables if you know what you are doing, but its advised to keep to the defaults.

### Step 2: Start all services with Docker Compose

Build and start all containers in detached mode:
```bash
docker compose up --build -d
```

- The Flask API will be available at `http://localhost:5000`
- MinIO will be available at `http://localhost:9000` (API) and `http://localhost:9001` (console)

> **Tip:**  
> To stop all services, run:
> ```bash
> docker compose down
> ```

### Step 3: Modify Hosts File (important!)

**Windows**

Add `127.0.0.1 minio` to the `C:\Windows\System32\drivers\etc\hosts` file.

**Unix**

`sudo echo "127.0.0.1       minio" >> /etc/hosts`

This is neccessary as the presigned URL is generated using an internal Docker network hostname (e.g., minio:9000), but the client attempts to access it using an external hostname or IP (e.g., localhost:9000 or the host's IP address). The signature is tied to the hostname used during signing.
