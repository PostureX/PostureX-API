from flask import Blueprint, request, jsonify, current_app, Flask
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_cors import CORS

from src.config.app_config import AppConfig
from src.config.database import db, migrate
from src.controllers import auth_bp, analysis_bp, video_bp, minio_hook_bp
from src.utils import setup_logging
from src import cli
from src.config.dev_config import DevConfig
from src.config.production_config import ProductionConfig
from src.models import User

app_configuration = DevConfig()

def create_app():
    """Application factory function"""
    app = Flask(__name__)
    
    # Setup logging
    setup_logging()
    
    # Load configuration
    app_config = AppConfig()
    app.config.update(app_config.get_flask_config())
    
    # Initialize extensions
    jwt = JWTManager(app)
    
    # Initialize SQLAlchemy and Flask-Migrate
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Register CLI commands
    cli.init_app(app)
    
    # Setup CORS with configuration
    cors_config = app_config.get_cors_config()
    CORS(app, 
         origins=cors_config['origins'],
         supports_credentials=cors_config['supports_credentials'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'])
    
    # Import models to ensure they are registered with SQLAlchemy
    from . import models
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')
    app.register_blueprint(video_bp, url_prefix='/api/video')

    # Register MinIO webhook blueprint
    app.register_blueprint(minio_hook_bp, url_prefix='/api/minio')

    @app.route("/api/users", methods=["GET"])
    @jwt_required()
    def get_all_users():
        """Get all users (admin only)"""
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        try:
            users = User.query.all()
            user_data = [user.to_dict() for user in users]
            return jsonify({"users": user_data}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {"status": "healthy"}, 200
    
    return app
