from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

from ..config.database import DatabaseConfig
from ..models.user import User

auth_bp = Blueprint('auth', __name__)

class AuthController:
    """Controller for authentication-related operations"""
    
    def __init__(self):
        self.db_config = DatabaseConfig()
    
    def get_db_connection(self):
        """Get database connection"""
        return self.db_config.get_connection()
    
    def register_user(self, email, name, password):
        """Register a new user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM spfposture.users WHERE email = %s",
                (email,)
            )
            if cursor.fetchone():
                return {"error": "User already exists"}, 400
            
            # Hash password and create user
            password_hash = generate_password_hash(password)
            cursor.execute(
                """INSERT INTO spfposture.users (email, name, password) 
                   VALUES (%s, %s, %s) RETURNING name""",
                (email, name, password_hash)
            )
            name = cursor.fetchone()[0]
            conn.commit()
            
            return {"message": "User registered successfully", "name": name}, 201
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()
    
    def login_user(self, email, password):
        """Authenticate user and create JWT token"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get user by email
            cursor.execute(
                "SELECT * FROM spfposture.users WHERE email = %s",
                (email,)
            )
            user_data = cursor.fetchone()
            
            if not user_data or not check_password_hash(user_data['password'], password):
                return {"error": "Invalid credentials"}, 401
            
            # Create JWT token
            access_token = create_access_token(
                identity=str(user_data['id']),
                expires_delta=timedelta(hours=3)
            )
            
            user = User.from_dict(user_data)
            
            return {
                "message": "Login successful",
                "user": user.to_dict(),
                "access_token": access_token
            }, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_user_profile(self, name):
        """Get user profile information"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                "SELECT name, email, name, created_at FROM spfposture.users WHERE name = %s",
                (name,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                return {"error": "User not found"}, 404
            
            user = User.from_dict(user_data)
            return {"user": user.to_dict()}, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()

# Initialize controller
auth_controller = AuthController()

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'name', 'password')):
        return jsonify({"error": "Missing required fields"}), 400
    
    result, status = auth_controller.register_user(
        data['email'], 
        data['name'], 
        data['password']
    )
    return jsonify(result), status

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and set JWT cookie"""
    data = request.get_json()
    if not data or not all(k in data for k in ('email', 'password')):
        return jsonify({"error": "Missing email or password"}), 400
    
    result, status = auth_controller.login_user(data['email'], data['password'])
    
    if status == 200:
        response = make_response(jsonify(result))
        response.set_cookie(
            'access_token_cookie',
            result['access_token'],
            max_age=timedelta(hours=3),
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite='Lax'
        )
        return response
    
    return jsonify(result), status

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user and clear JWT cookie"""
    response = make_response(jsonify({"message": "Logged out successfully"}))
    unset_jwt_cookies(response)
    return response

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    """Get current user's profile"""
    name = get_jwt_identity()
    result, status = auth_controller.get_user_profile(name)
    return jsonify(result), status
