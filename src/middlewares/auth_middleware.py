from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask import jsonify


def jwt_required_custom(fn):
    """
    Decorator to protect routes with JWT authentication and custom error handling.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
        except Exception as e:
            return jsonify({"message": f"Authentication required: {str(e)}"}), 401
        return fn(*args, **kwargs)

    return wrapper


def get_current_user_id():
    """
    Helper to get the current user ID from the JWT token.
    """
    return get_jwt_identity()
