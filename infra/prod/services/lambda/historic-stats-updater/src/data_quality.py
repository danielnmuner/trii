from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
EXPECTED_INTERVAL_SECONDS = 60
WARNING_GAP_SECONDS = 10 * 60
CRITICAL_GAP_SECONDS = 30 * 60
DATA_QUALITY_SCOPE = "intraday_data_quality"
DATA_QUALITY_RECORD_TYPE = "data_quality"


def parse_captured_at(raw_value: str) -> datetime:
    timestamp = datetime.fromisoformat(raw_value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def build_data_quality_sk() -> str:
    return DATA_QUALITY_RECORD_TYPE


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


def is_market_session_timestamp(timestamp: datetime) -> bool:
    if timestamp.weekday() >= 5:
        return False
    session_start, session_end = market_session_bounds(timestamp.date())
    return session_start <= timestamp <= session_end


def _gap_warning(previous_timestamp: datetime, current_timestamp: datetime) -> dict[str, Any] | None:
    if previous_timestamp.date() != current_timestamp.date():
        return None
    if not is_market_session_timestamp(previous_timestamp):
        return None
    if not is_market_session_timestamp(current_timestamp):
        return None

    duration_seconds = int((current_timestamp - previous_timestamp).total_seconds())
    if duration_seconds <= WARNING_GAP_SECONDS:
        return None

    severity = "critical" if duration_seconds >= CRITICAL_GAP_SECONDS else "warning"
    estimated_missing_snapshots = max((duration_seconds // EXPECTED_INTERVAL_SECONDS) - 1, 1)
    return {
        "started_at": previous_timestamp.isoformat(),
        "ended_at": current_timestamp.isoformat(),
        "duration_seconds": duration_seconds,
        "estimated_missing_snapshots": estimated_missing_snapshots,
        "severity": severity,
    }


def build_data_quality_item(
    previous_item: dict[str, Any] | None,
    *,
    symbol: str,
    current_timestamp: datetime,
    previous_timestamp: datetime | None,
    updated_at: datetime,
) -> dict[str, Any] | None:
    if not is_market_session_timestamp(current_timestamp):
        return None

    current_trading_date = current_timestamp.date().isoformat()
    previous_trading_date = str(previous_item.get("trading_date") or "").strip() if previous_item else ""
    reset_for_new_day = previous_trading_date != current_trading_date

    session_start, session_end = market_session_bounds(current_timestamp.date())
    gap_warnings = [] if reset_for_new_day else list(previous_item.get("gap_warnings", [])) if previous_item else []
    gap_count = 0 if reset_for_new_day else int(previous_item.get("gap_count", 0) or 0) if previous_item else 0
    largest_gap_seconds = 0 if reset_for_new_day else int(previous_item.get("largest_gap_seconds", 0) or 0) if previous_item else 0
    largest_gap_started_at = None if reset_for_new_day else previous_item.get("largest_gap_started_at") if previous_item else None
    largest_gap_ended_at = None if reset_for_new_day else previous_item.get("largest_gap_ended_at") if previous_item else None

    gap_warning = None
    if previous_timestamp is not None and not reset_for_new_day:
        gap_warning = _gap_warning(previous_timestamp, current_timestamp)

    if gap_warning is not None:
        gap_warnings.append(gap_warning)
        gap_count += 1
        if int(gap_warning["duration_seconds"]) >= largest_gap_seconds:
            largest_gap_seconds = int(gap_warning["duration_seconds"])
            largest_gap_started_at = gap_warning["started_at"]
            largest_gap_ended_at = gap_warning["ended_at"]

    quality_status = "healthy"
    if largest_gap_seconds >= CRITICAL_GAP_SECONDS:
        quality_status = "critical"
    elif gap_count > 0:
        quality_status = "warning"

    stats_version = int(previous_item["stats_version"]) + 1 if previous_item else 1
    return {
        "pk": symbol,
        "sk": build_data_quality_sk(),
        "symbol": symbol,
        "trading_date": current_trading_date,
        "sample_name": DATA_QUALITY_SCOPE,
        "expected_interval_seconds": EXPECTED_INTERVAL_SECONDS,
        "warning_gap_seconds": WARNING_GAP_SECONDS,
        "market_session_started_at": session_start.isoformat(),
        "market_session_ended_at": session_end.isoformat(),
        "last_snapshot_at": current_timestamp.isoformat(),
        "gap_count": gap_count,
        "largest_gap_seconds": largest_gap_seconds,
        "largest_gap_started_at": largest_gap_started_at,
        "largest_gap_ended_at": largest_gap_ended_at,
        "quality_status": quality_status,
        "gap_warnings": gap_warnings,
        "last_updated_at": updated_at.isoformat(),
        "stats_scope": DATA_QUALITY_SCOPE,
        "stats_version": stats_version,
    }
