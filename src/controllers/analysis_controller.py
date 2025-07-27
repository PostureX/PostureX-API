from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.config.database import db
from src.models.analysis import Analysis

analysis_bp = Blueprint("analysis", __name__)


class AnalysisController:
    """Controller for analysis-related operations"""

    def save_analysis(self, user_id, session_id, posture_result, feedback):
        """Save analysis results to database"""
        try:
            new_analysis = Analysis(
                user_id=user_id,
                session_id=session_id,
                posture_result=posture_result,  # Posture result in JSON format
                feedback=feedback,
            )
           
            db.session.add(new_analysis)
            db.session.commit()

            return {
                "message": "Analysis saved successfully",
                "analysis_id": new_analysis.id,
            }, 201

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    def get_user_analyses(self, user_id):
        """Get all analyses for a user"""
        try:
            analyses = (
                Analysis.query.filter_by(user_id=user_id)
                .order_by(Analysis.created_at.desc())
                .all()
            )
            return [analysis.to_dict() for analysis in analyses], 200

        except Exception as e:
            return {"error": str(e)}, 500

    def get_analysis_detail(self, user_id, analysis_id):
        """Get detailed analysis by ID"""
        try:
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()

            if not analysis:
                return {"error": "Analysis not found"}, 404

            return analysis.to_dict(), 200

        except Exception as e:
            return {"error": str(e)}, 500

    def delete_analysis(self, user_id, analysis_id):
        """Delete analysis by ID"""
        try:
            analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()

            if not analysis:
                return {"error": "Analysis not found"}, 404

            db.session.delete(analysis)
            db.session.commit()
            return {"message": "Analysis deleted successfully"}, 200

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500


# Initialize controller
analysis_controller = AnalysisController()


@analysis_bp.route("/save", methods=["POST"])
@jwt_required()
def save_analysis():
    """Save analysis results"""
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not all(k in data for k in ('session_id', 'posture_result', 'feedback')):
        return jsonify({"error": "Missing required fields"}), 400

    result, status = analysis_controller.save_analysis(
        user_id,
        data['session_id'],
        data["posture_result"],
        data['feedback'],
    )
    return jsonify(result), status


@analysis_bp.route("/list", methods=["GET"])
@jwt_required()
def list_analyses():
    """Get all analyses for current user"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_user_analyses(user_id)
    return jsonify(result), status


@analysis_bp.route("/<int:analysis_id>", methods=["GET"])
@jwt_required()
def get_analysis(analysis_id):
    """Get specific analysis by ID"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.get_analysis_detail(user_id, analysis_id)
    return jsonify(result), status


@analysis_bp.route("/<int:analysis_id>", methods=["DELETE"])
@jwt_required()
def delete_analysis(analysis_id):
    """Delete specific analysis by ID"""
    user_id = int(get_jwt_identity())
    result, status = analysis_controller.delete_analysis(user_id, analysis_id)
    return jsonify(result), status
