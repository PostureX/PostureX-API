from datetime import datetime
from src.config.database import db, db_config

class User(db.Model):
    """User model for authentication and user management"""
    __tablename__ = 'users'
    __table_args__ = {'schema': db_config.schema_name}

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to analyses
    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        """Convert user object to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create User object from dictionary"""
        user = cls()
        user.email = data.get('email', '')
        user.name = data.get('name', '')
        user.password_hash = data.get('password_hash', '')
        if data.get('created_at'):
            user.created_at = data.get('created_at')
        return user
