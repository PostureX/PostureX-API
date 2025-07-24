from .auth_controller import auth_bp
from .analysis_controller import analysis_bp
from .video_controller import video_bp
from .minio_video_controller import minio_hook_bp

__all__ = ['auth_bp', 'analysis_bp', 'video_bp', 'minio_hook_bp']
