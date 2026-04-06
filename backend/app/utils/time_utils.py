"""Timestamp utilities for market data processing."""

from datetime import datetime, timezone, timedelta
from typing import Optional


def ms_to_datetime(timestamp_ms: int) -> datetime:
    """Convert millisecond timestamp to timezone-aware datetime."""
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)


def datetime_to_ms(dt: datetime) -> int:
    """Convert datetime to millisecond timestamp."""
    return int(dt.timestamp() * 1000)


def now_utc() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def now_ms() -> int:
    """Get current time as millisecond timestamp."""
    return datetime_to_ms(now_utc())


def window_start(window_seconds: int, reference: Optional[datetime] = None) -> datetime:
    """Calculate the start of a time window ending at reference (or now)."""
    ref = reference or now_utc()
    return ref - timedelta(seconds=window_seconds)


def format_duration_ms(ms: float) -> str:
    """Format millisecond duration as human-readable string."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        return f"{ms / 60000:.1f}m"
