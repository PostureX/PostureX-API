from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies
)
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import bcrypt
from datetime import datetime, timedelta
import secrets

# Load environment variables
load_dotenv()

db_config = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

app = Flask(__name__)
app.config.update({
    'JWT_SECRET_KEY': os.getenv('JWT_SECRET', secrets.token_hex(32)),
    'JWT_TOKEN_LOCATION': ['cookies'],
    'JWT_COOKIE_SECURE': False,  # Set to True in production with HTTPS
    'JWT_COOKIE_SAMESITE': 'Lax',
    'JWT_COOKIE_CSRF_PROTECT': False,  # Set to True in production for additional security
    'JWT_ACCESS_COOKIE_PATH': '/',
    'JWT_REFRESH_COOKIE_PATH': '/',
    'JWT_ACCESS_TOKEN_EXPIRES': timedelta(hours=3)
})

jwt = JWTManager(app)
CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://127.0.0.1:5173"])


schema_name = 'spfposture'

# Database connection helper
def get_db_connection():
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

# Authentication Routes
@app.route('/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        name = data.get('name')
        password = data.get('password')

        if not name or not password:
            return jsonify({'message': 'Name and password are required'}), 400

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'message': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute(f"SELECT id FROM {schema_name}.users WHERE name = %s", (name,))
        if cur.fetchone():
            return jsonify({'message': 'User already exists'}), 409
        
        # Insert new user
        cur.execute(
            f"INSERT INTO {schema_name}.users (name, password) VALUES (%s, %s) RETURNING id",
            (name, hashed_password.decode('utf-8'))
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        
        # Generate token and set cookies
        access_token = create_access_token(identity=str(user_id))
        refresh_token = create_refresh_token(identity=str(user_id))
        
        resp = jsonify({
            'message': 'User registered successfully',
            'user_id': user_id
        })
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        
        return resp, 201
        
    except Exception as e:
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        name = data.get('name')
        password = data.get('password')
        
        if not name or not password:
            return jsonify({'message': 'name and password are required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'message': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get user by name
        cur.execute(f"SELECT id, name, password FROM {schema_name}.users WHERE name = %s", (name,))
        user = cur.fetchone()
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'message': 'Invalid credentials'}), 401
        
        # Generate tokens and set cookies
        access_token = create_access_token(identity=str(user['id']))
        refresh_token = create_refresh_token(identity=str(user['id']))
        
        resp = jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'name': user['name'],
            }
        })
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        
        return resp, 200
        
    except Exception as e:
        return jsonify({'message': f'Login failed: {str(e)}'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    resp = jsonify({'message': 'Logout successful'})
    unset_jwt_cookies(resp)
    return resp, 200

@app.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    new_token = create_access_token(identity=current_user_id)
    resp = jsonify({'message': 'Token refreshed'})
    set_access_cookies(resp, new_token)
    return resp, 200

@app.route('/api/analysis', methods=['POST'])
@jwt_required()
def create_user_analysis():
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        analysis_data = data.get('text')
        video_url = data.get('video_url')
        
        if not analysis_data or not video_url:
            return jsonify({'message': 'Analysis data and video URL are required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'message': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # Insert new analysis data for the user
        cur.execute(
            f"""
            INSERT INTO {schema_name}.analysis (user_id, video_url, text) 
            VALUES (%s, %s, %s) RETURNING id
            """,
            (current_user_id, video_url, analysis_data)
        )
        analysis_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({
            'message': 'User analysis created successfully',
            'analysis_id': analysis_id
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Failed to create user analysis: {str(e)}'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/api/analysis', methods=['GET'])
@jwt_required()
def get_user_all_analysis():
    try:
        current_user_id = int(get_jwt_identity())
        conn = get_db_connection()
        if not conn:
            return jsonify({'message': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get analysis data for specific user
        cur.execute(f"SELECT * FROM {schema_name}.analysis WHERE user_id=%s", (current_user_id,))
        analysis_data = cur.fetchall()
        
        return jsonify({
            'message': 'User analysis data retrieved successfully',
            'data': analysis_data
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to retrieve user analysis: {str(e)}'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/api/analysis/<int:analysis_id>', methods=['GET'])
@jwt_required()
def get_user_specific_analysis(analysis_id):
    try:
        current_user_id = int(get_jwt_identity())
        conn = get_db_connection()
        if not conn:
            return jsonify({'message': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get analysis data for specific analysis_id
        cur.execute(f"SELECT * FROM {schema_name}.analysis WHERE id=%s AND user_id=%s", (analysis_id, current_user_id))
        analysis_data = cur.fetchall()
        
        return jsonify({
            'message': 'User analysis data retrieved successfully',
            'data': analysis_data
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to retrieve user analysis: {str(e)}'}), 500
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/api/inference/cx_model', methods=['GET'])
@jwt_required()
def cx_model_inference():
    try:
        current_user_id = int(get_jwt_identity())
        # Placeholder for CX model inference
        # You can integrate your ML model here
        
        # Example response structure
        inference_result = {
            'model': 'cx_model',
            'user_id': current_user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'predictions': {
                'posture_score': 85.5,
                'risk_level': 'low',
                'recommendations': [
                    'Maintain current posture',
                    'Take breaks every 30 minutes'
                ]
            }
        }
        
        return jsonify({
            'message': 'CX model inference completed',
            'data': inference_result
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'CX model inference failed: {str(e)}'}), 500

@app.route('/api/inference/gy_model', methods=['GET'])
@jwt_required()
def gy_model_inference():
    try:
        current_user_id = int(get_jwt_identity())
        # Placeholder for GY model inference
        # You can integrate your ML model here
        
        # Example response structure
        inference_result = {
            'model': 'gy_model',
            'user_id': current_user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'predictions': {
                'posture_score': 78.2,
                'risk_level': 'medium',
                'recommendations': [
                    'Adjust monitor height',
                    'Improve chair ergonomics',
                    'Practice neck stretches'
                ]
            }
        }
        
        return jsonify({
            'message': 'GY model inference completed',
            'data': inference_result
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'GY model inference failed: {str(e)}'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'message': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

