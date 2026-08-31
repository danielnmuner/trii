from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


LAMBDA_SRC = (
    Path(__file__).resolve().parents[1]
    / "prod"
    / "services"
    / "lambda"
    / "historic-stats-updater"
    / "src"
)
if str(LAMBDA_SRC) not in sys.path:
    sys.path.insert(0, str(LAMBDA_SRC))

from data_quality import build_data_quality_item, is_market_session_timestamp, market_session_bounds


def test_market_session_bounds_follow_month_schedule() -> None:
    march_start, march_end = market_session_bounds(datetime(2026, 3, 20).date())
    december_start, december_end = market_session_bounds(datetime(2026, 12, 20).date())

    assert march_start.strftime("%H:%M") == "08:30"
    assert march_end.strftime("%H:%M") == "15:00"
    assert december_start.strftime("%H:%M") == "09:30"
    assert december_end.strftime("%H:%M") == "16:00"


def test_is_market_session_timestamp_rejects_weekends_and_off_hours() -> None:
    assert is_market_session_timestamp(datetime.fromisoformat("2026-08-20T10:00:00-05:00")) is True
    assert is_market_session_timestamp(datetime.fromisoformat("2026-08-20T07:59:00-05:00")) is False
    assert is_market_session_timestamp(datetime.fromisoformat("2026-08-22T10:00:00-05:00")) is False


def test_build_data_quality_item_starts_healthy_and_tracks_last_snapshot() -> None:
    item = build_data_quality_item(
        None,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T10:15:00-05:00"),
        previous_timestamp=None,
        updated_at=datetime.fromisoformat("2026-08-20T10:15:10-05:00"),
    )

    assert item is not None
    assert item["pk"] == "NUCO"
    assert item["sk"] == "data_quality"
    assert item["trading_date"] == "2026-08-20"
    assert item["quality_status"] == "healthy"
    assert item["gap_count"] == 0
    assert item["gap_warnings"] == []


def test_build_data_quality_item_ignores_snapshots_outside_market_hours() -> None:
    item = build_data_quality_item(
        None,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T18:10:00-05:00"),
        previous_timestamp=datetime.fromisoformat("2026-08-20T17:50:00-05:00"),
        updated_at=datetime.fromisoformat("2026-08-20T18:10:10-05:00"),
    )

    assert item is None


def test_build_data_quality_item_accumulates_multiple_gaps_during_the_day() -> None:
    first = build_data_quality_item(
        None,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T10:15:00-05:00"),
        previous_timestamp=None,
        updated_at=datetime.fromisoformat("2026-08-20T10:15:10-05:00"),
    )
    second = build_data_quality_item(
        first,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T10:29:00-05:00"),
        previous_timestamp=datetime.fromisoformat("2026-08-20T10:15:00-05:00"),
        updated_at=datetime.fromisoformat("2026-08-20T10:29:10-05:00"),
    )
    third = build_data_quality_item(
        second,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T14:45:00-05:00"),
        previous_timestamp=datetime.fromisoformat("2026-08-20T14:10:00-05:00"),
        updated_at=datetime.fromisoformat("2026-08-20T14:45:10-05:00"),
    )

    assert second is not None
    assert second["quality_status"] == "warning"
    assert second["gap_count"] == 1
    assert second["largest_gap_seconds"] == 840
    assert second["gap_warnings"][0]["duration_seconds"] == 840

    assert third is not None
    assert third["quality_status"] == "critical"
    assert third["gap_count"] == 2
    assert third["largest_gap_seconds"] == 2100
    assert third["largest_gap_started_at"] == "2026-08-20T14:10:00-05:00"
    assert third["largest_gap_ended_at"] == "2026-08-20T14:45:00-05:00"
    assert len(third["gap_warnings"]) == 2


def test_build_data_quality_item_reuses_single_record_and_resets_on_new_day() -> None:
    previous_day = build_data_quality_item(
        None,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T10:15:00-05:00"),
        previous_timestamp=None,
        updated_at=datetime.fromisoformat("2026-08-20T10:15:10-05:00"),
    )
    assert previous_day is not None

    previous_day = build_data_quality_item(
        previous_day,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-20T10:29:00-05:00"),
        previous_timestamp=datetime.fromisoformat("2026-08-20T10:15:00-05:00"),
        updated_at=datetime.fromisoformat("2026-08-20T10:29:10-05:00"),
    )
    assert previous_day is not None
    assert previous_day["gap_count"] == 1
    assert previous_day["stats_version"] == 2

    current_day = build_data_quality_item(
        previous_day,
        symbol="NUCO",
        current_timestamp=datetime.fromisoformat("2026-08-21T10:00:00-05:00"),
        previous_timestamp=datetime.fromisoformat("2026-08-20T14:59:00-05:00"),
        updated_at=datetime.fromisoformat("2026-08-21T10:00:10-05:00"),
    )

    assert current_day is not None
    assert current_day["sk"] == "data_quality"
    assert current_day["trading_date"] == "2026-08-21"
    assert current_day["gap_count"] == 0
    assert current_day["gap_warnings"] == []
    assert current_day["largest_gap_seconds"] == 0
    assert current_day["largest_gap_started_at"] is None
    assert current_day["largest_gap_ended_at"] is None
    assert current_day["quality_status"] == "healthy"
    assert current_day["stats_version"] == 3
