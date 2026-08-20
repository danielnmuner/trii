from __future__ import annotations

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime


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

from snapshot_metrics import extract_metric_values, parse_metric_keys
from stats_engine import build_stat_item


def _sample_snapshot() -> dict:
    return {
        "best_bid_price": 43800,
        "best_ask_price": 43900,
        "best_bid_quantity": 1200,
        "best_ask_quantity": 300,
        "bid_levels": [
            {"level": 1, "quantity": 1200, "price": 43800},
            {"level": 2, "quantity": 2400, "price": 43780},
            {"level": 3, "quantity": 800, "price": 43760},
            {"level": 4, "quantity": 600, "price": 43740},
            {"level": 5, "quantity": 400, "price": 43720},
        ],
        "ask_levels": [
            {"level": 1, "quantity": 300, "price": 43900},
            {"level": 2, "quantity": 700, "price": 43920},
            {"level": 3, "quantity": 900, "price": 43940},
            {"level": 4, "quantity": 500, "price": 43960},
            {"level": 5, "quantity": 600, "price": 43980},
        ],
        "last_price": 43860,
        "daily_change_amount": -700,
        "daily_change_percent": -157,
        "traded_volume": 50256,
        "traded_value": 2213492380,
    }


def test_extract_metric_values_keeps_only_official_statistical_metrics() -> None:
    metrics = extract_metric_values(_sample_snapshot())

    assert set(metrics) == {
        "spread_bps",
        "obi_l1",
        "obi_top_5",
        "book_pressure_ratio",
        "depth_weighted_microprice_deviation",
    }
    assert "spread" not in metrics
    assert "bid_depth_total_5" not in metrics
    assert "ask_depth_total_5" not in metrics
    assert "last_price" not in metrics
    assert "daily_change_amount" not in metrics
    assert "daily_change_percent" not in metrics
    assert "traded_volume" not in metrics
    assert "traded_value" not in metrics
    assert "mid_price" not in metrics
    assert "microprice" not in metrics


def test_extract_metric_values_computes_expected_microstructure_values() -> None:
    metrics = extract_metric_values(_sample_snapshot())

    assert metrics["book_pressure_ratio"] == Decimal("1.8")
    assert metrics["obi_l1"] == Decimal("0.6")
    assert metrics["obi_top_5"] == Decimal("0.2857142857142857142857142857")


def test_build_stat_item_uses_welford_incrementally_for_market_sample() -> None:
    first = build_stat_item(
        None,
        symbol="NUCO",
        metric="obi_l1",
        captured_at="2026-08-20T10:15:00-05:00",
        snapshot_checksum="checksum-1",
        value=Decimal("0.10"),
        updated_at=datetime.fromisoformat("2026-08-20T10:15:10-05:00"),
    )
    second = build_stat_item(
        first,
        symbol="NUCO",
        metric="obi_l1",
        captured_at="2026-08-20T10:16:00-05:00",
        snapshot_checksum="checksum-2",
        value=Decimal("0.30"),
        updated_at=datetime.fromisoformat("2026-08-20T10:16:10-05:00"),
    )

    assert first["pk"] == "NUCO"
    assert first["sample_name"] == "all_time_market_sample"
    assert first["sample_count"] == 1
    assert first["mean"] == Decimal("0.10")
    assert first["m2"] == Decimal("0")
    assert first["stddev"] == Decimal("0")

    assert second["sample_count"] == 2
    assert second["mean"] == Decimal("0.20")
    assert second["m2"] == Decimal("0.0200")
    assert second["stddev"] == Decimal("0.1414213562373095048801688724")


def test_extract_metric_values_can_be_filtered_by_enabled_metric_keys() -> None:
    metrics = extract_metric_values(
        _sample_snapshot(),
        ("obi_l1", "spread_bps"),
    )

    assert set(metrics) == {"obi_l1", "spread_bps"}


def test_parse_metric_keys_defaults_to_all_supported_metrics() -> None:
    metric_keys = parse_metric_keys(None)

    assert metric_keys == (
        "spread_bps",
        "obi_l1",
        "obi_top_5",
        "book_pressure_ratio",
        "depth_weighted_microprice_deviation",
    )
