from datetime import datetime
import pytz
from src.config.database import db, db_config

# Singapore timezone
SGT = pytz.timezone('Asia/Singapore')

def get_sgt_now():
    """Get current time in Singapore timezone"""
    return datetime.now(SGT)

class Analysis(db.Model):
    """Analysis model for storing analysis results"""
    __tablename__ = 'analysis'
    __table_args__ = {'schema': db_config.schema_name}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(f'{db_config.schema_name}.users.id'), nullable=False)
    session_id = db.Column(db.Text, nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='in_progress')  # e.g., 'in_progress', 'completed', 'failed'
    created_at = db.Column(db.DateTime, default=get_sgt_now)
    
    def __repr__(self):
        return f'<Analysis {self.id}>'
    
    def to_dict(self):
        """Convert analysis object to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'model_name': self.model_name,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Analysis object from dictionary"""
        analysis = cls()
        analysis.user_id = data.get('user_id', 0)
        analysis.session_id = data.get('session_id', '')
        analysis.model_name = data.get('model_name', '')
        analysis.status = data.get('status', 'pending')
        if data.get('created_at'):
            analysis.created_at = data.get('created_at')
        return analysis
