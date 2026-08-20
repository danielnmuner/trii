from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from snapshot_metrics import to_decimal


SAMPLE_NAME = "all_time_market_sample"


def build_stat_item(
    previous_item: dict[str, Any] | None,
    *,
    symbol: str,
    metric: str,
    captured_at: str,
    snapshot_checksum: str,
    value: Decimal,
    updated_at: datetime,
) -> dict[str, Any]:
    previous_count = int(previous_item["sample_count"]) if previous_item else 0
    previous_mean = to_decimal(previous_item["mean"]) if previous_item else Decimal("0")
    previous_m2 = to_decimal(previous_item["m2"]) if previous_item else Decimal("0")
    previous_min = to_decimal(previous_item["min_value"]) if previous_item else value
    previous_max = to_decimal(previous_item["max_value"]) if previous_item else value

    sample_count = previous_count + 1
    delta = value - previous_mean
    mean = previous_mean + (delta / Decimal(sample_count))
    delta_2 = value - mean
    m2 = previous_m2 + (delta * delta_2)

    if sample_count > 1:
        variance = m2 / Decimal(sample_count - 1)
        stddev = variance.sqrt()
    else:
        stddev = Decimal("0")

    stats_version = int(previous_item["stats_version"]) + 1 if previous_item else 1

    return {
        "pk": symbol,
        "sk": metric,
        "symbol": symbol,
        "metric": metric,
        "sample_name": SAMPLE_NAME,
        "symbol_metric": f"{symbol}#{metric}",
        "sample_count": sample_count,
        "mean": mean,
        "m2": m2,
        "stddev": stddev,
        "min_value": value if previous_min is None else min(previous_min, value),
        "max_value": value if previous_max is None else max(previous_max, value),
        "latest_value": value,
        "last_source_captured_at": captured_at,
        "last_source_checksum": snapshot_checksum,
        "last_updated_at": updated_at.isoformat(),
        "stats_scope": SAMPLE_NAME,
        "stats_version": stats_version,
    }
