from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime

@dataclass
class Analysis:
    """Analysis model for storing analysis results"""
    id: Optional[int] = None
    user_id: int = 0
    video_url: str = ""  # Base64 encoded image or data
    text: str = ""  # JSON string of analysis results
    created_at: Optional[datetime] = None
    
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
        return cls(
            id=data.get('id'),
            user_id=data.get('user_id', 0),
            video_url=data.get('video_url', ''),
            text=data.get('text', ''),
            created_at=data.get('created_at')
        )

@dataclass
class PoseKeypoint:
    """Individual pose keypoint with coordinates and confidence"""
    x: float
    y: float
    confidence: float

@dataclass 
class InferenceResult:
    """Result from pose inference containing keypoints and metadata"""
    keypoints: List[PoseKeypoint]
    bbox: Optional[List[float]] = None
    bbox_score: Optional[float] = None
    
    def to_dict(self):
        """Convert inference result to dictionary"""
        return {
            'keypoints': [[kp.x, kp.y, kp.confidence] for kp in self.keypoints],
            'bbox': self.bbox,
            'bbox_score': self.bbox_score
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create InferenceResult from dictionary"""
        keypoints = []
        if 'keypoints' in data:
            for kp_data in data['keypoints']:
                if len(kp_data) >= 3:
                    keypoints.append(PoseKeypoint(kp_data[0], kp_data[1], kp_data[2]))
        
        return cls(
            keypoints=keypoints,
            bbox=data.get('bbox'),
            bbox_score=data.get('bbox_score')
        )
