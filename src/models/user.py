from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class User:
    """User model for authentication and user management"""
    id: Optional[int] = None
    email: str = ""
    name: str = ""
    password_hash: str = ""
    created_at: Optional[datetime] = None
    
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
        return cls(
            id=data.get('id'),
            email=data.get('email', ''),
            name=data.get('name', ''),
            password_hash=data.get('password_hash', ''),
            created_at=data.get('created_at')
        )
