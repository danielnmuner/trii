from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


def parse_captured_at(raw_value: str) -> datetime:
    timestamp = datetime.fromisoformat(raw_value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def market_session_bounds(trading_date: date) -> tuple[datetime, datetime]:
    # Month-level approximation from the provided BVC schedule:
    # Mar-Oct => 08:30-15:00, Nov-Feb => 09:30-16:00.
    if 3 <= trading_date.month <= 10:
        session_start = time(hour=8, minute=30)
        session_end = time(hour=15, minute=0)
    else:
        session_start = time(hour=9, minute=30)
        session_end = time(hour=16, minute=0)

    return (
        datetime.combine(trading_date, session_start, tzinfo=BOGOTA_TIMEZONE),
        datetime.combine(trading_date, session_end, tzinfo=BOGOTA_TIMEZONE),
    )
