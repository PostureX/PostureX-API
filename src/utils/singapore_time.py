"""
Singapore timezone utilities for consistent time handling across the application
"""
from datetime import datetime
import pytz

# Singapore timezone using pytz
SINGAPORE_TZ = pytz.timezone('Asia/Singapore')


def get_singapore_now():
    """Get current datetime in Singapore timezone"""
    return datetime.now(SINGAPORE_TZ)


def get_singapore_timestamp():
    """Get current timestamp in Singapore timezone"""
    return get_singapore_now().timestamp()


def utc_to_singapore(utc_dt):
    """
    Convert UTC datetime to Singapore timezone
    
    Args:
        utc_dt: datetime object (assumed to be UTC if naive)
    
    Returns:
        datetime object in Singapore timezone
    """
    if utc_dt is None:
        return None
    
    if utc_dt.tzinfo is None:
        # Assume UTC if no timezone info
        utc_dt = pytz.utc.localize(utc_dt)
    
    return utc_dt.astimezone(SINGAPORE_TZ)


def singapore_to_utc(sgt_dt):
    """
    Convert Singapore datetime to UTC
    
    Args:
        sgt_dt: datetime object in Singapore timezone
    
    Returns:
        datetime object in UTC (timezone-naive for database storage)
    """
    if sgt_dt is None:
        return None
    
    if sgt_dt.tzinfo is None:
        # Assume Singapore timezone if no timezone info
        sgt_dt = SINGAPORE_TZ.localize(sgt_dt)
    
    return sgt_dt.astimezone(pytz.utc).replace(tzinfo=None)


def get_singapore_week_boundaries():
    """
    Get current week boundaries (Monday to Sunday) in Singapore timezone
    
    Returns:
        tuple: (start_of_week_sgt, end_of_week_sgt, start_of_week_utc, end_of_week_utc)
    """
    today = get_singapore_now()
    days_since_monday = today.weekday()  # Monday is 0, Sunday is 6
    
    start_of_week = today - timedelta(days=days_since_monday)
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    # Convert to UTC for database comparison
    start_of_week_utc = singapore_to_utc(start_of_week)
    end_of_week_utc = singapore_to_utc(end_of_week)
    
    return start_of_week, end_of_week, start_of_week_utc, end_of_week_utc


def format_singapore_datetime(dt, format_string="%A, %d %B %Y %I:%M %p SGT"):
    """
    Format datetime in Singapore timezone
    
    Args:
        dt: datetime object (will be converted to Singapore time if needed)
        format_string: strftime format string
    
    Returns:
        formatted datetime string
    """
    if dt is None:
        return None
    
    sgt_dt = utc_to_singapore(dt)
    return sgt_dt.strftime(format_string)


def get_current_singapore_date():
    """Get current date in Singapore timezone (YYYY-MM-DD format)"""
    return get_singapore_now().strftime("%Y-%m-%d")


def get_current_singapore_datetime_iso():
    """Get current datetime in Singapore timezone as ISO string"""
    return get_singapore_now().isoformat()
