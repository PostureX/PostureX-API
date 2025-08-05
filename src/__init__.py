from datetime import datetime, timedelta
import pytz

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
from src.services.analysis_bucket_minio import get_detailed_analysis_data
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
        """Get all users (admin only) with average overall score and latest analysis datetime"""
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        
        try:
            # Singapore timezone
            SGT = pytz.timezone('Asia/Singapore')
            
            # Calculate current week boundaries (Monday to Sunday) in Singapore time
            today = datetime.now(SGT)
            days_since_monday = today.weekday()  # Monday is 0, Sunday is 6
            start_of_week = today - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            users = User.query.all()
            user_data = []
            
            for user in users:
                user_dict = user.to_dict()
                
                # Initialize stats
                user_dict['average_overall_score'] = 0.0
                user_dict['latest_analysis_datetime'] = None
                user_dict['total_analyses'] = 0
                user_dict['current_week_analyses'] = 0
                
                # Get user's analyses to calculate stats
                user_analyses = user.analyses
                if user_analyses:
                    user_dict['total_analyses'] = len(user_analyses)
                    
                    # Find latest analysis datetime
                    latest_analysis = max(user_analyses, key=lambda analysis: analysis.created_at)
                    user_dict['latest_analysis_datetime'] = latest_analysis.created_at.isoformat()
                    
                    # Filter analyses for current week only
                    current_week_analyses = []
                    for analysis in user_analyses:
                        # Convert analysis.created_at to SGT if it's naive (stored as SGT) or timezone-aware
                        analysis_time = analysis.created_at
                        if analysis_time.tzinfo is None:
                            # If stored as naive datetime (assuming it's already in SGT)
                            analysis_time = SGT.localize(analysis_time)
                        else:
                            # Convert to SGT if it's timezone-aware
                            analysis_time = analysis_time.astimezone(SGT)
                        
                        if start_of_week <= analysis_time <= end_of_week:
                            current_week_analyses.append(analysis)
                    
                    user_dict['current_week_analyses'] = len(current_week_analyses)
                    
                    # Calculate average overall score from current week's detailed analysis JSONs
                    total_scores = []
                    
                    for analysis in current_week_analyses:
                        try:
                            # Get all detailed analysis data for this session
                            detailed_data = get_detailed_analysis_data(str(user.id), analysis.session_id)
                            
                            # Process each side's data
                            for side, side_data in detailed_data.items():
                                aggregate_scores = side_data['aggregate_results'].get('score', {})
                                
                                # Sum all numeric score values (exclude 'side' field)
                                numeric_scores = [
                                    v for k, v in aggregate_scores.items() 
                                    if isinstance(v, (int, float))
                                ]
                                
                                overall_score = sum(numeric_scores)
                                total_scores.append(overall_score)
                        
                        except Exception as e:
                            print(f"Error processing analysis {analysis.id} for user {user.id}: {e}")
                            continue
                    
                    # Calculate average overall score for current week
                    if total_scores:
                        user_dict['average_overall_score'] = round(sum(total_scores) / len(total_scores), 3)
                
                user_data.append(user_dict)
            
            return jsonify({"users": user_data}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    @app.route('/api/user', methods=['GET'])
    @jwt_required()
    def get_current_user():
        """Get current user's data with average overall score and latest analysis datetime"""
        current_user_id = get_jwt_identity()
        
        try:
            # Singapore timezone
            SGT = pytz.timezone('Asia/Singapore')
            
            # Calculate current week boundaries (Monday to Sunday) in Singapore time
            today = datetime.now(SGT)
            days_since_monday = today.weekday()  # Monday is 0, Sunday is 6
            start_of_week = today - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            # Get current user
            user = User.query.get(current_user_id)
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            user_dict = user.to_dict()
            
            # Initialize stats
            user_dict['average_overall_score'] = 0.0
            user_dict['latest_analysis_datetime'] = None
            user_dict['total_analyses'] = 0
            user_dict['current_week_analyses'] = 0
            
            # Get user's analyses to calculate stats
            user_analyses = user.analyses
            if user_analyses:
                user_dict['total_analyses'] = len(user_analyses)
                
                # Find latest analysis datetime
                latest_analysis = max(user_analyses, key=lambda analysis: analysis.created_at)
                user_dict['latest_analysis_datetime'] = latest_analysis.created_at.isoformat()
                
                # Filter analyses for current week only
                current_week_analyses = []
                for analysis in user_analyses:
                    # Convert analysis.created_at to SGT if it's naive (stored as SGT) or timezone-aware
                    analysis_time = analysis.created_at
                    if analysis_time.tzinfo is None:
                        # If stored as naive datetime (assuming it's already in SGT)
                        analysis_time = SGT.localize(analysis_time)
                    else:
                        # Convert to SGT if it's timezone-aware
                        analysis_time = analysis_time.astimezone(SGT)
                    
                    if start_of_week <= analysis_time <= end_of_week:
                        current_week_analyses.append(analysis)
                
                user_dict['current_week_analyses'] = len(current_week_analyses)
                
                # Calculate average overall score from current week's detailed analysis JSONs
                total_scores = []
                
                for analysis in current_week_analyses:
                    try:
                        # Get all detailed analysis data for this session
                        detailed_data = get_detailed_analysis_data(str(user.id), analysis.session_id)
                        
                        # Process each side's data
                        for side, side_data in detailed_data.items():
                            aggregate_scores = side_data['aggregate_results'].get('score', {})
                            
                            # Sum all numeric score values (exclude 'side' field)
                            numeric_scores = [
                                v for k, v in aggregate_scores.items() 
                                if isinstance(v, (int, float))
                            ]
                            
                            overall_score = sum(numeric_scores)
                            total_scores.append(overall_score)
                    
                    except Exception as e:
                        print(f"Error processing analysis {analysis.id} for user {user.id}: {e}")
                        continue
                
                # Calculate average overall score for current week
                if total_scores:
                    user_dict['average_overall_score'] = round(sum(total_scores) / len(total_scores), 3)
            
            return jsonify({"user": user_dict}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
    @app.route('/api/user/<int:user_id>', methods=['GET'])
    @jwt_required()
    def get_user_by_id(user_id):
        """Get specific user data with average overall score and latest analysis datetime"""
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if current_user.is_admin:
            user_id_to_fetch = user_id
        else:
            user_id_to_fetch = current_user_id
        
        try:
            # Singapore timezone
            SGT = pytz.timezone('Asia/Singapore')
            
            # Calculate current week boundaries (Monday to Sunday) in Singapore time
            today = datetime.now(SGT)
            days_since_monday = today.weekday()  # Monday is 0, Sunday is 6
            start_of_week = today - timedelta(days=days_since_monday)
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            # Get specific user
            user = User.query.get(user_id_to_fetch)
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            user_dict = user.to_dict()
            
            # Initialize stats
            user_dict['average_overall_score'] = 0.0
            user_dict['latest_analysis_datetime'] = None
            user_dict['total_analyses'] = 0
            user_dict['current_week_analyses'] = 0
            
            # Get user's analyses to calculate stats
            user_analyses = user.analyses
            if user_analyses:
                user_dict['total_analyses'] = len(user_analyses)
                
                # Find latest analysis datetime
                latest_analysis = max(user_analyses, key=lambda analysis: analysis.created_at)
                user_dict['latest_analysis_datetime'] = latest_analysis.created_at.isoformat()
                
                # Filter analyses for current week only
                current_week_analyses = []
                for analysis in user_analyses:
                    # Convert analysis.created_at to SGT if it's naive (stored as SGT) or timezone-aware
                    analysis_time = analysis.created_at
                    if analysis_time.tzinfo is None:
                        # If stored as naive datetime (assuming it's already in SGT)
                        analysis_time = SGT.localize(analysis_time)
                    else:
                        # Convert to SGT if it's timezone-aware
                        analysis_time = analysis_time.astimezone(SGT)
                    
                    if start_of_week <= analysis_time <= end_of_week:
                        current_week_analyses.append(analysis)
                
                user_dict['current_week_analyses'] = len(current_week_analyses)
                
                # Calculate average overall score from current week's detailed analysis JSONs
                total_scores = []
                
                for analysis in current_week_analyses:
                    try:
                        # Get all detailed analysis data for this session
                        detailed_data = get_detailed_analysis_data(str(user.id), analysis.session_id)
                        
                        # Process each side's data
                        for side, side_data in detailed_data.items():
                            aggregate_scores = side_data['aggregate_results'].get('score', {})
                            
                            # Sum all numeric score values (exclude 'side' field)
                            numeric_scores = [
                                v for k, v in aggregate_scores.items() 
                                if isinstance(v, (int, float))
                            ]
                            
                            overall_score = sum(numeric_scores)
                            total_scores.append(overall_score)
                    
                    except Exception as e:
                        print(f"Error processing analysis {analysis.id} for user {user.id}: {e}")
                        continue
                
                # Calculate average overall score for current week
                if total_scores:
                    user_dict['average_overall_score'] = round(sum(total_scores) / len(total_scores), 3)
            
            return jsonify({"user": user_dict}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {"status": "healthy"}, 200
    
    return app
