from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from src.models.user_model import db, User
from src.services.jwt_service import create_tokens_and_set_cookies

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    if not name or not email or not password:
        return jsonify({"message": "Name, email, and password are required."}), 400
    if User.query.filter((User.name == name) | (User.email == email)).first():
        return jsonify({"message": "User already exists"}), 409
    hashed_password = generate_password_hash(password)
    user = User(name=name, email=email, password=hashed_password)
    db.session.add(user)
    db.session.commit()
    resp = jsonify({"message": "User registered successfully", "user": user.to_dict()})
    create_tokens_and_set_cookies(resp, user.id)
    return resp, 201


@auth.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    name = data.get("name")
    password = data.get("password")
    if not name or not password:
        return jsonify({"message": "Name and password are required."}), 400
    user = User.query.filter_by(name=name).first()
    if user and check_password_hash(user.password, password):
        resp = jsonify({"message": "Login successful", "user": user.to_dict()})
        create_tokens_and_set_cookies(resp, user.id)
        return resp, 200
    return jsonify({"message": "Invalid credentials"}), 401
