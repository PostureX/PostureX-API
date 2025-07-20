from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from src.config.app_config import AppConfig
from src.config.database import db, migrate
from src.controllers import auth_bp, analysis_bp
from src.utils import setup_logging
from src import cli
from src.config.dev_config import DevConfig
from src.config.production_config import ProductionConfig

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
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {"status": "healthy"}, 200
    
    return app
