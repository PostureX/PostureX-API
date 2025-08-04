from datetime import datetime, timedelta
import os

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    unset_jwt_cookies,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from src.config.database import db
from src.models.user import User

auth_bp = Blueprint("auth", __name__)


class AuthController:
    """Controller for authentication-related operations"""

    def register_user(self, email, name, password):
        """Register a new user"""
        try:
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                return {"error": "User already exists"}, 409

            # Hash password and create user
            password_hash = generate_password_hash(password)
            new_user = User(email=email, name=name, password_hash=password_hash)

            db.session.add(new_user)
            db.session.commit()

            # Create JWT token
            access_token = create_access_token(
                identity=str(new_user.id), expires_delta=timedelta(hours=3)
            )

            return {
                "message": "User registered successfully",
                "user": new_user.to_dict(),
                "token": access_token,
            }, 201

        except IntegrityError:
            db.session.rollback()
            return {"error": "User already exists"}, 409
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    def login_user(self, email, password):
        """Authenticate user and create JWT token"""
        try:
            # Get user by email
            user = User.query.filter_by(email=email).first()

            if not user or not check_password_hash(user.password_hash, password):
                return {"error": "Invalid credentials"}, 401

            # Create JWT token
            access_token = create_access_token(
                identity=str(user.id), expires_delta=timedelta(hours=3)
            )

            return {
                "message": "Login successful",
                "user": user.to_dict(),
                "token": access_token,
            }, 200

        except Exception as e:
            return {"error": str(e)}, 500

    def get_user_profile(self, user_id):
        """Get user profile information"""
        try:
            user = User.query.get(int(user_id))

            if not user:
                return {"error": "User not found"}, 404

            return {"user": user.to_dict()}, 200

        except Exception as e:
            return {"error": str(e)}, 500


# Initialize controller
auth_controller = AuthController()


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user"""
    data = request.get_json()
    if not data or not all(k in data for k in ("email", "name", "password")):
        return jsonify({"error": "Missing required fields"}), 400

    result, status = auth_controller.register_user(
        data["email"], data["name"], data["password"]
    )
    return jsonify(result), status


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login user and set JWT cookie"""
    data = request.get_json()
    if not data or not all(k in data for k in ("email", "password")):
        return jsonify({"error": "Missing email or password"}), 400

    result, status = auth_controller.login_user(data["email"], data["password"])

    if status == 200:
        response = make_response(jsonify(result))
        response.set_cookie(
            "access_token_cookie",
            result["token"],
            max_age=timedelta(hours=3),
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="Lax",
        )
        return response

    return jsonify(result), status


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout user and clear JWT cookie"""
    response = make_response(jsonify({"message": "Logged out successfully"}))
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    """Get current user's profile"""
    user_id = get_jwt_identity()
    result, status = auth_controller.get_user_profile(user_id)
    return jsonify(result), status


# New endpoint to validate session (check if user is logged in)
@auth_bp.route("/validate-session", methods=["GET"])
@jwt_required()
def validate_session():
    """Validate if the user is logged in (JWT cookie present and valid)"""
    user_id = get_jwt_identity()
    result, status = auth_controller.get_user_profile(user_id)
    if status == 200:
        return jsonify({"logged_in": True, "user": result["user"]}), 200
    else:
        return (
            jsonify(
                {
                    "logged_in": False,
                    "error": result.get("error", "access_token_cookie not found"),
                }
            ),
            status,
        )


# New endpoint to generate WebSocket token
@auth_bp.route("/ws-token", methods=["GET"])
@jwt_required()
def generate_ws_token():
    """Generate a short-lived one-time token for WebSocket authentication"""
    user_id = get_jwt_identity()

    ws_token = create_access_token(
        identity=str(user_id),
        expires_delta=timedelta(minutes=5),
        additional_claims={"ws_auth": True, "one_time": True},
    )

    return (
        jsonify(
            {
                "ws_token": ws_token,
                "expires_in": 300,
                "message": "WebSocket token generated successfully",
            }
        ),
        200,
    )


@auth_bp.route("/gen-tele-link", methods=["GET"])
@jwt_required()
def generate_telegram_link():
    user_id = get_jwt_identity()
    result, status = auth_controller.get_user_profile(user_id)

    if status == 200:
        telegram_link = f"https://t.me/{os.getenv('TELEGRAM_BOT_USERNAME', 'posturexBot')}?start={user_id}"
        user = User.query.get(user_id)

        # set telegram link expiry
        user.tele_link_expires_at = datetime.now() + timedelta(seconds=60)
        db.session.commit()

        return (
            jsonify(
                {
                    "telegram_link": telegram_link,
                    "expires_at": user.tele_link_expires_at.timestamp(),
                }
            ),
            200,
        )
    else:
        return jsonify({"error": result.get("error", "User not found")}), status
