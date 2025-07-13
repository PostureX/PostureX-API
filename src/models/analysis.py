from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass
from ..config.database import db

class Analysis(db.Model):
    """Analysis model for storing analysis results"""
    __tablename__ = 'analysis'
    __table_args__ = {'schema': 'spfposture'}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('spfposture.users.id'), nullable=False)
    video_url = db.Column(db.Text, nullable=False)  # Base64 encoded image or data
    text = db.Column(db.Text, nullable=False)  # JSON string of analysis results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Analysis {self.id}>'
    
    def to_dict(self):
        """Convert analysis object to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'video_url': self.video_url,
            'text': self.text,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Analysis object from dictionary"""
        analysis = cls()
        analysis.user_id = data.get('user_id', 0)
        analysis.video_url = data.get('video_url', '')
        analysis.text = data.get('text', '')
        if data.get('created_at'):
            analysis.created_at = data.get('created_at')
        return analysis
