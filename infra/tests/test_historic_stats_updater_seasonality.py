from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path


UPDATER_SRC = (
    Path(__file__).resolve().parents[1]
    / "prod"
    / "services"
    / "lambda"
    / "historic-stats-updater"
    / "src"
)
if str(UPDATER_SRC) not in sys.path:
    sys.path.insert(0, str(UPDATER_SRC))

_seasonality_spec = importlib.util.spec_from_file_location(
    "historic_stats_updater_seasonality",
    UPDATER_SRC / "seasonality_profile.py",
)
assert _seasonality_spec is not None and _seasonality_spec.loader is not None
_seasonality_module = importlib.util.module_from_spec(_seasonality_spec)
_seasonality_spec.loader.exec_module(_seasonality_module)
build_seasonality_profile_item = _seasonality_module.build_seasonality_profile_item


def assert_decimal_close(actual: Decimal, expected: Decimal, tolerance: str = "1e-24") -> None:
    assert abs(actual - expected) <= Decimal(tolerance)


def test_live_seasonality_profile_accumulates_intraday_state_and_rates() -> None:
    first_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T09:00:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a1",
        "traded_volume": 100,
        "traded_value": 1000,
    }
    second_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T09:15:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a2",
        "traded_volume": 140,
        "traded_value": 1560,
    }

    profile_after_first = build_seasonality_profile_item(
        None,
        snapshot=first_snapshot,
        previous_snapshot=None,
        updated_at=datetime.fromisoformat("2026-08-17T09:00:30-05:00"),
    )
    assert profile_after_first is not None
    assert profile_after_first["total_snapshots_processed"] == 1
    assert "pending_day" not in profile_after_first

    profile_after_second = build_seasonality_profile_item(
        profile_after_first,
        snapshot=second_snapshot,
        previous_snapshot=first_snapshot,
        updated_at=datetime.fromisoformat("2026-08-17T09:15:30-05:00"),
    )
    assert profile_after_second is not None
    assert profile_after_second["total_snapshots_processed"] == 2
    assert profile_after_second["total_days_processed"] == 0
    assert profile_after_second["pending_day"]["trading_date"] == "2026-08-17"

    monday_bucket = profile_after_second["weekly_profile"]["1"]["hours"]["09:00"]
    assert monday_bucket["accumulated_volume"] == Decimal("40")
    assert monday_bucket["accumulated_value"] == Decimal("560")
    assert monday_bucket["delta_samples"] == 1
    assert monday_bucket["bucket_vwap"] == Decimal("14")
    assert monday_bucket["volume_share_stats"]["sample_count"] == 0
    assert monday_bucket["vwap_stats"]["sample_count"] == 0
    assert monday_bucket["volume_rate_stats"]["sample_count"] == 1
    assert monday_bucket["volume_rate_stats"]["mu"] == Decimal("2") / Decimal("45")
    assert monday_bucket["volume_rate_stats"]["variance"] == Decimal("0")
    assert monday_bucket["value_rate_stats"]["sample_count"] == 1
    assert monday_bucket["value_rate_stats"]["mu"] == Decimal("28") / Decimal("45")
    assert monday_bucket["value_rate_stats"]["variance"] == Decimal("0")


def test_live_seasonality_profile_finalizes_pending_day_on_next_trading_day() -> None:
    first_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T09:00:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a1",
        "traded_volume": 100,
        "traded_value": 1000,
    }
    second_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T09:15:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a2",
        "traded_volume": 140,
        "traded_value": 1560,
    }
    next_day_first_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-18T09:00:00-05:00",
        "captured_date": "2026-08-18",
        "snapshot_checksum": "checksum-b1",
        "traded_volume": 200,
        "traded_value": 2600,
    }

    profile = build_seasonality_profile_item(
        None,
        snapshot=first_snapshot,
        previous_snapshot=None,
        updated_at=datetime.fromisoformat("2026-08-17T09:00:30-05:00"),
    )
    assert profile is not None
    profile = build_seasonality_profile_item(
        profile,
        snapshot=second_snapshot,
        previous_snapshot=first_snapshot,
        updated_at=datetime.fromisoformat("2026-08-17T09:15:30-05:00"),
    )
    assert profile is not None

    finalized_profile = build_seasonality_profile_item(
        profile,
        snapshot=next_day_first_snapshot,
        previous_snapshot=second_snapshot,
        updated_at=datetime.fromisoformat("2026-08-18T09:00:30-05:00"),
    )
    assert finalized_profile is not None
    assert finalized_profile["total_snapshots_processed"] == 3
    assert finalized_profile["total_days_processed"] == 1
    assert "pending_day" not in finalized_profile

    monday_profile = finalized_profile["weekly_profile"]["1"]
    assert monday_profile["days_processed"] == 1
    assert monday_profile["accumulated_day_volume"] == Decimal("40")
    assert monday_profile["accumulated_day_value"] == Decimal("560")

    monday_bucket = monday_profile["hours"]["09:00"]
    assert monday_bucket["volume_share_stats"]["sample_count"] == 1
    assert monday_bucket["volume_share_stats"]["mu"] == Decimal("1")
    assert monday_bucket["volume_share_stats"]["variance"] == Decimal("0")
    assert monday_bucket["vwap_stats"]["sample_count"] == 1
    assert monday_bucket["vwap_stats"]["mu"] == Decimal("14")
    assert monday_bucket["vwap_stats"]["variance"] == Decimal("0")
