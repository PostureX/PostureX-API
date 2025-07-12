from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

from ..config.database import DatabaseConfig
from ..models.analysis import Analysis

analysis_bp = Blueprint('analysis', __name__)

class AnalysisController:
    """Controller for analysis-related operations"""
    
    def __init__(self):
        self.db_config = DatabaseConfig()
    
    def get_db_connection(self):
        """Get database connection"""
        return self.db_config.get_connection()

    def save_analysis(self, user_id, video_url, text):
        """Save analysis results to database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """INSERT INTO spfposture.analysis (user_id, video_url, text, created_at) 
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (user_id, video_url, text, datetime.now())
            )
            analysis_id = cursor.fetchone()[0]
            conn.commit()
            
            return {"message": "Analysis saved successfully", "analysis_id": analysis_id}, 201
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_user_analyses(self, user_id):
        """Get all analyses for a user"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                """SELECT id, created_at, video_url, text
                   FROM spfposture.analysis 
                   WHERE user_id = %s 
                   ORDER BY created_at DESC""",
                (user_id,)
            )
            analyses = cursor.fetchall()
            # Convert each analysis dict to Analysis model
            return [Analysis.from_dict(dict(analysis)).to_dict() for analysis in analyses], 200
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()
    
    def get_analysis_detail(self, user_id, analysis_id):
        """Get detailed analysis by ID"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(
                """SELECT * FROM spfposture.analysis 
                   WHERE id = %s AND user_id = %s""",
                (analysis_id, user_id)
            )
            analysis_data = cursor.fetchone()
            
            if not analysis_data:
                return {"error": "Analysis not found"}, 404

            # Convert analysis_data to Analysis model
            user = Analysis.from_dict(dict(analysis_data))
            return user.to_dict(), 200

        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()
    
    def delete_analysis(self, user_id, analysis_id):
        """Delete analysis by ID"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM spfposture.analysis WHERE id = %s AND user_id = %s",
                (analysis_id, user_id)
            )
            
            if cursor.rowcount == 0:
                return {"error": "Analysis not found"}, 404
            
            conn.commit()
            return {"message": "Analysis deleted successfully"}, 200
            
        except Exception as e:
            return {"error": str(e)}, 500
        finally:
            if 'conn' in locals():
                conn.close()

# Initialize controller
analysis_controller = AnalysisController()

@analysis_bp.route('/save', methods=['POST'])
@jwt_required()
def save_analysis():
    """Save analysis results"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not all(k in data for k in ('video_url', 'text')):
        return jsonify({"error": "Missing required fields"}), 400
    
    result, status = analysis_controller.save_analysis(
        user_id,
        data['video_url'],
        data['text'],
    )
    return jsonify(result), status

@analysis_bp.route('/list', methods=['GET'])
@jwt_required()
def list_analyses():
    """Get all analyses for current user"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_user_analyses(user_id)
    return jsonify(result), status

@analysis_bp.route('/<int:analysis_id>', methods=['GET'])
@jwt_required()
def get_analysis(analysis_id):
    """Get specific analysis by ID"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_analysis_detail(user_id, analysis_id)
    return jsonify(result), status

@analysis_bp.route('/<int:analysis_id>', methods=['DELETE'])
@jwt_required()
def delete_analysis(analysis_id):
    """Delete specific analysis by ID"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.delete_analysis(user_id, analysis_id)
    return jsonify(result), status
