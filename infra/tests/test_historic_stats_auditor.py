from __future__ import annotations

import sys
from datetime import datetime
from decimal import Decimal
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

from stats_auditor import audit_stat_item, recompute_statistics
from stats_engine import build_stat_item


def _build_incremental_item(values: list[Decimal]) -> dict:
    item = None
    for index, value in enumerate(values, start=1):
        item = build_stat_item(
            item,
            symbol="NUCO",
            metric="obi_l1",
            captured_at=f"2026-08-20T10:{10 + index:02d}:00-05:00",
            snapshot_checksum=f"checksum-{index}",
            value=value,
            updated_at=datetime.fromisoformat(f"2026-08-20T10:{10 + index:02d}:10-05:00"),
        )
    assert item is not None
    return item


def test_recompute_statistics_matches_expected_sample_formula() -> None:
    values = [Decimal("0.10"), Decimal("0.30"), Decimal("-0.20")]

    recomputed = recompute_statistics(values)

    assert recomputed["sample_count"] == 3
    assert recomputed["mean"] == Decimal("0.06666666666666666666666666667")
    assert recomputed["m2"] == Decimal("0.1266666666666666666666666667")
    assert recomputed["stddev"] == Decimal("0.2516611478423583232412228269")
    assert recomputed["min_value"] == Decimal("-0.20")
    assert recomputed["max_value"] == Decimal("0.30")
    assert recomputed["latest_value"] == Decimal("-0.20")


def test_auditor_accepts_incremental_welford_result() -> None:
    values = [Decimal("0.10"), Decimal("0.30"), Decimal("-0.20"), Decimal("0.40")]
    actual_item = _build_incremental_item(values)

    audit = audit_stat_item(actual_item, values)

    assert audit["ok"] is True
    assert audit["mismatches"] == []


def test_auditor_reports_statistical_mismatches_clearly() -> None:
    values = [Decimal("0.10"), Decimal("0.30"), Decimal("-0.20")]
    actual_item = _build_incremental_item(values)
    actual_item["stddev"] = Decimal("999")
    actual_item["sample_count"] = 99

    audit = audit_stat_item(actual_item, values)

    assert audit["ok"] is False
    assert audit["mismatches"] == [
        {
            "field": "sample_count",
            "expected": 3,
            "actual": 99,
        },
        {
            "field": "stddev",
            "expected": "0.2516611478423583232412228269",
            "actual": "999",
        },
    ]
