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

_opportunity_spec = importlib.util.spec_from_file_location(
    "historic_stats_updater_opportunity_events",
    UPDATER_SRC / "opportunity_events.py",
)
assert _opportunity_spec is not None and _opportunity_spec.loader is not None
_opportunity_module = importlib.util.module_from_spec(_opportunity_spec)
_opportunity_spec.loader.exec_module(_opportunity_module)
build_triggered_z_scores = _opportunity_module.build_triggered_z_scores
build_zscore_opportunity_item = _opportunity_module.build_zscore_opportunity_item
summarize_approved_position = _opportunity_module.summarize_approved_position


def test_build_triggered_z_scores_keeps_only_metrics_over_threshold() -> None:
    stat_items = {
        "obi_l1": {
            "latest_value": Decimal("0.50"),
            "mean": Decimal("0.10"),
            "stddev": Decimal("0.20"),
            "sample_count": 10,
        },
        "spread_bps": {
            "latest_value": Decimal("50"),
            "mean": Decimal("45"),
            "stddev": Decimal("10"),
            "sample_count": 12,
        },
    }

    triggered = build_triggered_z_scores(stat_items)

    assert triggered == {
        "obi_l1": {
            "sample_value": Decimal("0.50"),
            "z_score": Decimal("2"),
        }
    }


def test_summarize_approved_position_uses_fifo_to_keep_remaining_cost_basis() -> None:
    orders = [
        {
            "created_at": "2025-08-10T09:00:00-05:00",
            "normalized_status": "approved",
            "order_side": "buy",
            "filled_quantity": 10,
            "price_per_share": 100,
            "record_checksum": "buy-1",
        },
        {
            "created_at": "2025-08-15T09:00:00-05:00",
            "normalized_status": "approved",
            "order_side": "buy",
            "filled_quantity": 10,
            "price_per_share": 120,
            "record_checksum": "buy-2",
        },
        {
            "created_at": "2025-08-20T09:00:00-05:00",
            "normalized_status": "approved",
            "order_side": "sell",
            "filled_quantity": 5,
            "price_per_share": 130,
            "record_checksum": "sell-1",
        },
    ]

    summary = summarize_approved_position(orders, "ISA")

    assert summary["symbol"] == "ISA"
    assert summary["approved_buy_quantity"] == Decimal("20")
    assert summary["approved_sell_quantity"] == Decimal("5")
    assert summary["available_quantity"] == Decimal("15")
    assert summary["weighted_average_price"] == Decimal("113.3333333333333333333333333")


def test_build_zscore_opportunity_item_keeps_only_required_context() -> None:
    snapshot = {
        "symbol": "NUCO",
        "captured_at": "2026-08-21T10:56:08.134-05:00",
        "captured_date": "2026-08-21",
        "snapshot_checksum": "checksum-1",
        "last_price": 44000,
        "daily_change_amount": 120,
        "daily_change_percent": 0.28,
        "previous_close": 43880,
        "high_price": 44100,
        "low_price": 43750,
        "bid_levels": [{"price": 43990, "quantity": 200}],
        "ask_levels": [{"price": 44010, "quantity": 180}],
    }
    triggered_z_scores = {
        "obi_l1": {
            "sample_value": Decimal("0.5"),
            "z_score": Decimal("2.1"),
        }
    }
    position_summary = {
        "symbol": "NUCO",
        "approved_buy_quantity": Decimal("100"),
        "approved_sell_quantity": Decimal("20"),
        "available_quantity": Decimal("80"),
        "weighted_average_price": Decimal("43000"),
    }

    item = build_zscore_opportunity_item(
        snapshot,
        triggered_z_scores,
        position_summary,
        datetime.fromisoformat("2026-08-21T10:56:08.645401-05:00"),
    )

    assert item["snapshot_checksum"] == "checksum-1"
    assert item["symbol_captured_at"] == "NUCO#2026-08-21T10:56:08.134-05:00"
    assert item["triggered_z_scores"] == triggered_z_scores
    assert item["approved_position_summary"]["available_quantity"] == Decimal("80")
    assert "best_bid_price" not in item
    assert "best_ask_price" not in item
