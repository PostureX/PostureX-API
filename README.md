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

## Error Handling
- **404:** `{ "message": "Endpoint not found" }`
- **500:** `{ "message": "Internal server error" }`

## Notes
- All requests that require authentication must include cookies. On the frontend, use `credentials: 'include'` (fetch) or `withCredentials: true` (axios).
- JWT cookies are set for both access and refresh tokens.
- CORS is configured for local development.
