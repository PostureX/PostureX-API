"""
Presigned URL caching utilities for MinIO operations
"""
import time
import threading
from datetime import timedelta
from typing import Optional, Tuple

# In-memory cache for presigned URLs
presigned_url_cache = {}
cache_lock = threading.Lock()

# Cache cleanup thread control
_cleanup_thread = None
_cleanup_running = False


def get_cache_key(bucket: str, file_path: str) -> str:
    """Generate a cache key for presigned URL"""
    return f"{bucket}:{file_path}"


def get_cached_presigned_url(bucket: str, file_path: str) -> Optional[str]:
    """Get cached presigned URL if still valid"""
    with cache_lock:
        cache_key = get_cache_key(bucket, file_path)
        cached_entry = presigned_url_cache.get(cache_key)
        
        if cached_entry:
            url, expires_at = cached_entry
            # Check if URL is still valid (with 5 minute buffer before expiration)
            if time.time() < (expires_at - 300):  # 300 seconds = 5 minutes buffer
                return url
            else:
                # Remove expired entry
                del presigned_url_cache[cache_key]
        
        return None


def cache_presigned_url(bucket: str, file_path: str, url: str, expires_delta: timedelta) -> None:
    """Cache a presigned URL with expiration time"""
    with cache_lock:
        cache_key = get_cache_key(bucket, file_path)
        expires_at = time.time() + expires_delta.total_seconds()
        presigned_url_cache[cache_key] = (url, expires_at)


def cleanup_expired_cache() -> None:
    """Clean up expired cache entries"""
    with cache_lock:
        current_time = time.time()
        expired_keys = [
            key for key, (url, expires_at) in presigned_url_cache.items()
            if current_time >= expires_at
        ]
        for key in expired_keys:
            del presigned_url_cache[key]
        
        if expired_keys:
            print(f"Cleaned up {len(expired_keys)} expired presigned URL cache entries")


def get_cache_stats() -> dict:
    """Get cache statistics"""
    with cache_lock:
        current_time = time.time()
        total_entries = len(presigned_url_cache)
        expired_entries = sum(
            1 for url, expires_at in presigned_url_cache.values()
            if current_time >= expires_at
        )
        valid_entries = total_entries - expired_entries
        
        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries
        }


def start_cache_cleanup_thread():
    """Start the background cache cleanup thread if not already running"""
    global _cleanup_thread, _cleanup_running
    
    if not _cleanup_running:
        _cleanup_running = True
        _cleanup_thread = threading.Thread(target=_cache_cleanup_worker, daemon=True)
        _cleanup_thread.start()


def _cache_cleanup_worker():
    """Background worker to clean up expired cache entries"""
    global _cleanup_running
    
    while _cleanup_running:
        try:
            cleanup_expired_cache()
            # Clean up every 5 minutes
            time.sleep(300)
        except Exception as e:
            print(f"Error in cache cleanup worker: {e}")
            time.sleep(60)  # Wait a minute before retrying


# Start cleanup thread when cache module is imported
start_cache_cleanup_thread()
