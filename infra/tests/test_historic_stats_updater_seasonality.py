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


def test_live_seasonality_profile_skips_same_open_bucket() -> None:
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T08:45:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a1",
        "traded_volume": 100,
        "traded_value": 1000,
    }
    snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T08:59:30-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a2",
        "traded_volume": 120,
        "traded_value": 1260,
    }

    profile = build_seasonality_profile_item(
        None,
        snapshot=snapshot,
        previous_snapshot=previous_snapshot,
        updated_at=datetime.fromisoformat("2026-08-17T09:00:00-05:00"),
    )

    assert profile is None


def test_live_seasonality_profile_writes_once_when_bucket_closes() -> None:
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T08:59:30-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a1",
        "traded_volume": 140,
        "traded_value": 1560,
    }
    snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T09:00:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a2",
        "traded_volume": 141,
        "traded_value": 1574,
    }

    profile = build_seasonality_profile_item(
        None,
        snapshot=snapshot,
        previous_snapshot=previous_snapshot,
        updated_at=datetime.fromisoformat("2026-08-17T09:00:30-05:00"),
    )

    assert profile is not None
    assert profile["last_source_captured_at"] == "2026-08-17T08:59:30-05:00"
    assert profile["total_snapshots_processed"] == 1
    assert profile["total_days_processed"] == 0
    assert profile["pending_day"]["trading_date"] == "2026-08-17"
    assert profile["pending_day"]["last_processed_bucket_key"] == "08:30"
    assert profile["pending_day"]["total_day_volume"] == Decimal("140")
    assert profile["pending_day"]["total_day_value"] == Decimal("1560")

    monday_bucket = profile["weekly_profile"]["1"]["hours"]["08:30"]
    assert monday_bucket["accumulated_volume"] == Decimal("140")
    assert monday_bucket["accumulated_value"] == Decimal("1560")
    assert monday_bucket["delta_samples"] == 1
    assert_decimal_close(monday_bucket["bucket_vwap"], Decimal("1560") / Decimal("140"))
    assert monday_bucket["volume_share_stats"]["sample_count"] == 0
    assert monday_bucket["vwap_stats"]["sample_count"] == 0


def test_live_seasonality_profile_finalizes_day_on_close_boundary() -> None:
    existing_profile = {
        "pk": "NUCO",
        "sk": "seasonality_profile",
        "symbol": "NUCO",
        "record_type": "seasonality_profile",
        "bucket_granularity_minutes": 30,
        "timezone": "America/Bogota",
        "total_days_processed": 0,
        "total_snapshots_processed": 1,
        "last_source_captured_at": "2026-08-17T08:59:30-05:00",
        "last_updated_at": "2026-08-17T09:00:30-05:00",
        "stats_scope": "weekly_intraday_seasonality",
        "stats_version": 1,
        "weekly_profile": {
            "1": {
                "weekday_label": "monday",
                "days_processed": 0,
                "accumulated_day_volume": Decimal("0"),
                "accumulated_day_value": Decimal("0"),
                "hours": {
                    "08:30": {
                        "accumulated_volume": Decimal("140"),
                        "accumulated_value": Decimal("1560"),
                        "delta_samples": 1,
                        "bucket_vwap": Decimal("1560") / Decimal("140"),
                        "volume_share_stats": {
                            "sample_count": 0,
                            "mu": Decimal("0"),
                            "m2": Decimal("0"),
                            "variance": Decimal("0"),
                            "sigma": Decimal("0"),
                        },
                        "vwap_stats": {
                            "sample_count": 0,
                            "mu": Decimal("0"),
                            "m2": Decimal("0"),
                            "variance": Decimal("0"),
                            "sigma": Decimal("0"),
                        },
                    }
                },
            }
        },
        "pending_day": {
            "trading_date": "2026-08-17",
            "weekday": "1",
            "last_source_captured_at": "2026-08-17T08:59:30-05:00",
            "total_day_volume": Decimal("140"),
            "total_day_value": Decimal("1560"),
            "last_processed_bucket_key": "08:30",
            "last_processed_total_volume": Decimal("140"),
            "last_processed_total_value": Decimal("1560"),
            "hours": {
                "08:30": {
                    "bucket_volume": Decimal("140"),
                    "bucket_value": Decimal("1560"),
                }
            },
        },
    }
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T14:59:30-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a3",
        "traded_volume": 200,
        "traded_value": 2360,
    }
    snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-17T15:00:00-05:00",
        "captured_date": "2026-08-17",
        "snapshot_checksum": "checksum-a4",
        "traded_volume": 200,
        "traded_value": 2360,
    }

    profile = build_seasonality_profile_item(
        existing_profile,
        snapshot=snapshot,
        previous_snapshot=previous_snapshot,
        updated_at=datetime.fromisoformat("2026-08-17T15:00:10-05:00"),
    )

    assert profile is not None
    assert profile["total_days_processed"] == 1
    assert profile["total_snapshots_processed"] == 2
    assert "pending_day" not in profile

    monday_profile = profile["weekly_profile"]["1"]
    assert monday_profile["days_processed"] == 1
    assert monday_profile["accumulated_day_volume"] == Decimal("200")
    assert monday_profile["accumulated_day_value"] == Decimal("2360")

    close_bucket = monday_profile["hours"]["14:30"]
    assert close_bucket["accumulated_volume"] == Decimal("60")
    assert close_bucket["accumulated_value"] == Decimal("800")
    assert close_bucket["delta_samples"] == 1
    assert_decimal_close(close_bucket["bucket_vwap"], Decimal("800") / Decimal("60"))

    opening_bucket = monday_profile["hours"]["08:30"]
    assert opening_bucket["volume_share_stats"]["sample_count"] == 1
    assert opening_bucket["volume_share_stats"]["mu"] == Decimal("140") / Decimal("200")
    assert opening_bucket["vwap_stats"]["sample_count"] == 1
    assert_decimal_close(opening_bucket["vwap_stats"]["mu"], Decimal("1560") / Decimal("140"))
