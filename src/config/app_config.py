from datetime import timedelta
import secrets
import os
from src.config.database import db_config
from src.config.production_config import ProductionConfig
from src.config.dev_config import DevConfig

class AppConfig:
    """Application configuration"""
    
    def __init__(self):
        self.jwt_secret = os.getenv('JWT_SECRET')
        self.debug = os.getenv('DEBUG')
        self.cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173", os.getenv("API_BASE_URL")]
        self.dev_config = DevConfig()
        self.prod_config = ProductionConfig()
    
    def get_flask_config(self):
        """Get Flask configuration dictionary"""
        config = {
            'JWT_SECRET_KEY': self.jwt_secret,
            'JWT_TOKEN_LOCATION': ['cookies'],
            'JWT_COOKIE_SECURE': False,  # Set to True in production with HTTPS
            'JWT_COOKIE_SAMESITE': 'Lax',
            'JWT_COOKIE_CSRF_PROTECT': False,  # Set to True in production for additional security
            'JWT_ACCESS_COOKIE_PATH': '/',
            'JWT_REFRESH_COOKIE_PATH': '/',
            'JWT_ACCESS_TOKEN_EXPIRES': timedelta(hours=3),
            'DEBUG': self.debug
        }
        
        # Add SQLAlchemy configuration
        config.update(db_config.get_sqlalchemy_config())
        
        return config
    
    def get_cors_config(self):
        """Get CORS configuration"""
        return {
            'supports_credentials': True,
            'origins': self.cors_origins
        }
