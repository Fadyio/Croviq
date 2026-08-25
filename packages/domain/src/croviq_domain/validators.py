from datetime import datetime


def validate_timezone_aware(v: datetime) -> datetime:
    """Validate that a datetime object is timezone-aware."""
    if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
        raise ValueError("Timestamp must be timezone-aware (e.g. UTC)")
    return v
