from datetime import datetime
from src.config.database import db, db_config

class Analysis(db.Model):
    """Analysis model for storing analysis results"""
    __tablename__ = 'analysis'
    __table_args__ = {'schema': db_config.schema_name}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f'{db_config.schema_name}.users.id'), nullable=False)
    session_id = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='in_progress')  # e.g., 'in_progress', 'completed', 'failed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Analysis {self.id}>'
    
    def to_dict(self):
        """Convert analysis object to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Analysis object from dictionary"""
        analysis = cls()
        analysis.user_id = data.get('user_id', 0)
        analysis.session_id = data.get('session_id', '')
        analysis.status = data.get('status', 'pending')
        if data.get('created_at'):
            analysis.created_at = data.get('created_at')
        return analysis
