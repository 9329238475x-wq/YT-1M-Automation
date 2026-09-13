from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def to_utc_iso(local_time: str, timezone: str = "Asia/Kolkata") -> str:
    """Convert an ISO local datetime to the UTC ISO format expected by YouTube."""
    dt = datetime.fromisoformat(local_time)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return dt.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
