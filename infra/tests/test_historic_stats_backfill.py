from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path


BACKFILL_SRC = (
    Path(__file__).resolve().parents[1]
    / "prod"
    / "services"
    / "lambda"
    / "historic-stats-backfill"
    / "src"
)
if str(BACKFILL_SRC) not in sys.path:
    sys.path.insert(0, str(BACKFILL_SRC))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault(
    "ENABLED_STATISTICAL_METRICS",
    "spread_bps,obi_l1,obi_top_5,book_pressure_ratio,depth_weighted_microprice_deviation",
)

_handler_spec = importlib.util.spec_from_file_location(
    "historic_stats_backfill_handler",
    BACKFILL_SRC / "handler.py",
)
assert _handler_spec is not None and _handler_spec.loader is not None
_handler_module = importlib.util.module_from_spec(_handler_spec)
_handler_spec.loader.exec_module(_handler_module)
rebuild_stat_items_from_snapshots = _handler_module.rebuild_stat_items_from_snapshots


def assert_decimal_close(actual: Decimal, expected: Decimal, tolerance: str = "1e-24") -> None:
    assert abs(actual - expected) <= Decimal(tolerance)


def test_rebuild_stat_items_from_snapshots_recomputes_selected_metrics_only() -> None:
    snapshots = [
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-20T10:00:00-05:00",
            "snapshot_checksum": "checksum-1",
            "best_bid_price": 43800,
            "best_ask_price": 43900,
            "best_bid_quantity": 1200,
            "best_ask_quantity": 300,
            "bid_levels": [
                {"quantity": 1200},
                {"quantity": 2400},
                {"quantity": 800},
                {"quantity": 600},
                {"quantity": 400},
            ],
            "ask_levels": [
                {"quantity": 300},
                {"quantity": 700},
                {"quantity": 900},
                {"quantity": 500},
                {"quantity": 600},
            ],
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-20T10:01:00-05:00",
            "snapshot_checksum": "checksum-2",
            "best_bid_price": 43780,
            "best_ask_price": 43880,
            "best_bid_quantity": 1000,
            "best_ask_quantity": 500,
            "bid_levels": [
                {"quantity": 1000},
                {"quantity": 2200},
                {"quantity": 700},
                {"quantity": 500},
                {"quantity": 300},
            ],
            "ask_levels": [
                {"quantity": 500},
                {"quantity": 800},
                {"quantity": 1000},
                {"quantity": 400},
                {"quantity": 500},
            ],
        },
    ]

    rebuilt_items = rebuild_stat_items_from_snapshots(
        snapshots,
        ("obi_l1", "spread_bps"),
        datetime.fromisoformat("2026-08-20T11:00:00-05:00"),
    )

    assert set(rebuilt_items) == {("NUCO", "obi_l1"), ("NUCO", "spread_bps")}

    obi_l1_item = rebuilt_items[("NUCO", "obi_l1")]
    assert obi_l1_item["sample_count"] == 2
    assert obi_l1_item["latest_value"] == Decimal("0.3333333333333333333333333333")
    assert obi_l1_item["last_source_checksum"] == "checksum-2"

    spread_bps_item = rebuilt_items[("NUCO", "spread_bps")]
    assert spread_bps_item["sample_count"] == 2
    assert spread_bps_item["last_source_captured_at"] == "2026-08-20T10:01:00-05:00"
    assert spread_bps_item["stddev"] > 0


def test_rebuild_stat_items_from_snapshots_can_build_seasonality_profile() -> None:
    snapshots = [
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-17T09:00:00-05:00",
            "captured_date": "2026-08-17",
            "snapshot_checksum": "checksum-a1",
            "traded_volume": 100,
            "traded_value": 1000,
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-17T09:15:00-05:00",
            "captured_date": "2026-08-17",
            "snapshot_checksum": "checksum-a2",
            "traded_volume": 140,
            "traded_value": 1560,
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-17T09:45:00-05:00",
            "captured_date": "2026-08-17",
            "snapshot_checksum": "checksum-a3",
            "traded_volume": 200,
            "traded_value": 2460,
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-24T09:00:00-05:00",
            "captured_date": "2026-08-24",
            "snapshot_checksum": "checksum-b1",
            "traded_volume": 200,
            "traded_value": 2600,
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-24T09:15:00-05:00",
            "captured_date": "2026-08-24",
            "snapshot_checksum": "checksum-b2",
            "traded_volume": 250,
            "traded_value": 3350,
        },
        {
            "symbol": "NUCO",
            "captured_at": "2026-08-24T09:45:00-05:00",
            "captured_date": "2026-08-24",
            "snapshot_checksum": "checksum-b3",
            "traded_volume": 320,
            "traded_value": 4470,
        },
    ]

    rebuilt_items = rebuild_stat_items_from_snapshots(
        snapshots,
        ("seasonality_profile",),
        datetime.fromisoformat("2026-08-24T16:00:00-05:00"),
    )

    assert set(rebuilt_items) == {("NUCO", "seasonality_profile")}

    profile_item = rebuilt_items[("NUCO", "seasonality_profile")]
    assert profile_item["record_type"] == "seasonality_profile"
    assert profile_item["bucket_granularity_minutes"] == 30
    assert profile_item["total_days_processed"] == 2
    assert profile_item["total_snapshots_processed"] == 6
    assert profile_item["last_source_captured_at"] == "2026-08-24T09:45:00-05:00"

    monday_profile = profile_item["weekly_profile"]["1"]
    assert monday_profile["days_processed"] == 2
    assert monday_profile["accumulated_day_volume"] == Decimal("220")
    assert monday_profile["accumulated_day_value"] == Decimal("3330")
    assert set(monday_profile["hours"]) == {"09:00", "09:30"}

    first_half_hour_profile = monday_profile["hours"]["09:00"]
    assert first_half_hour_profile["accumulated_volume"] == Decimal("90")
    assert first_half_hour_profile["accumulated_value"] == Decimal("1310")
    assert first_half_hour_profile["delta_samples"] == 2
    assert first_half_hour_profile["bucket_vwap"] == Decimal("1310") / Decimal("90")
    assert first_half_hour_profile["volume_share_stats"]["sample_count"] == 2
    assert_decimal_close(
        first_half_hour_profile["volume_share_stats"]["variance"],
        Decimal("1") / Decimal("7200"),
    )
    assert first_half_hour_profile["vwap_stats"]["sample_count"] == 2
    assert_decimal_close(
        first_half_hour_profile["vwap_stats"]["variance"],
        Decimal("1") / Decimal("2"),
    )
    assert first_half_hour_profile["volume_rate_stats"]["sample_count"] == 2
    assert_decimal_close(
        first_half_hour_profile["volume_rate_stats"]["mu"],
        Decimal("1") / Decimal("20"),
    )
    assert_decimal_close(
        first_half_hour_profile["volume_rate_stats"]["variance"],
        Decimal("1") / Decimal("16200"),
    )
    assert first_half_hour_profile["value_rate_stats"]["sample_count"] == 2
    assert_decimal_close(
        first_half_hour_profile["value_rate_stats"]["mu"],
        Decimal("131") / Decimal("180"),
    )
    assert_decimal_close(
        first_half_hour_profile["value_rate_stats"]["variance"],
        Decimal("361") / Decimal("16200"),
    )

    second_half_hour_profile = monday_profile["hours"]["09:30"]
    assert second_half_hour_profile["accumulated_volume"] == Decimal("130")
    assert second_half_hour_profile["accumulated_value"] == Decimal("2020")
    assert second_half_hour_profile["delta_samples"] == 2
    assert second_half_hour_profile["bucket_vwap"] == Decimal("2020") / Decimal("130")
    assert second_half_hour_profile["volume_share_stats"]["sample_count"] == 2
    assert_decimal_close(
        second_half_hour_profile["volume_share_stats"]["variance"],
        Decimal("1") / Decimal("7200"),
    )
    assert second_half_hour_profile["vwap_stats"]["sample_count"] == 2
    assert_decimal_close(
        second_half_hour_profile["vwap_stats"]["variance"],
        Decimal("1") / Decimal("2"),
    )
    assert second_half_hour_profile["volume_rate_stats"]["sample_count"] == 2
    assert_decimal_close(
        second_half_hour_profile["volume_rate_stats"]["mu"],
        Decimal("13") / Decimal("360"),
    )
    assert_decimal_close(
        second_half_hour_profile["volume_rate_stats"]["variance"],
        Decimal("1") / Decimal("64800"),
    )
    assert second_half_hour_profile["value_rate_stats"]["sample_count"] == 2
    assert_decimal_close(
        second_half_hour_profile["value_rate_stats"]["mu"],
        Decimal("101") / Decimal("180"),
    )
    assert_decimal_close(
        second_half_hour_profile["value_rate_stats"]["variance"],
        Decimal("121") / Decimal("16200"),
    )
