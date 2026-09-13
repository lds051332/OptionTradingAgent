from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def is_us_equity_rth(now: datetime | None = None) -> bool:
    current = now.astimezone(NY) if now is not None else datetime.now(NY)
    if current.weekday() >= 5:
        return False
    return time(9, 30) <= current.time() < time(16, 0)
