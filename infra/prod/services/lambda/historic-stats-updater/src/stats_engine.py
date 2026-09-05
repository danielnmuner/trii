from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from snapshot_metrics import to_decimal


SAMPLE_NAME = "all_time_market_sample"
STATS_SUMMARY_KEY = "stats_summary"
SUMMARY_METRIC_FIELDS = (
    "metric",
    "sample_count",
    "mean",
    "m2",
    "stddev",
    "min_value",
    "max_value",
    "latest_value",
)


def _reconstructed_m2(previous_item: dict[str, Any] | None) -> Decimal:
    if not previous_item:
        return Decimal("0")
    previous_m2 = to_decimal(previous_item.get("m2"))
    if previous_m2 is not None:
        return previous_m2
    previous_stddev = to_decimal(previous_item.get("stddev"))
    previous_count = int(previous_item.get("sample_count") or 0)
    if previous_stddev is None or previous_count <= 1:
        return Decimal("0")
    return (previous_stddev * previous_stddev) * Decimal(previous_count - 1)


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
    previous_count = int(previous_item.get("sample_count") or 0) if previous_item else 0
    previous_mean = (
        to_decimal(previous_item.get("mean"))
        if previous_item and previous_item.get("mean") is not None
        else None
    )
    if previous_mean is None:
        previous_mean = (
            to_decimal(previous_item.get("latest_value"))
            if previous_item and previous_item.get("latest_value") is not None
            else value
        )
    previous_m2 = _reconstructed_m2(previous_item)
    previous_min = to_decimal(previous_item.get("min_value")) if previous_item else value
    previous_max = to_decimal(previous_item.get("max_value")) if previous_item else value

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

    stats_version = int(previous_item.get("stats_version") or 0) + 1 if previous_item else 1

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


def build_stats_summary_item(
    previous_item: dict[str, Any] | None,
    *,
    symbol: str,
    captured_at: str,
    snapshot_checksum: str,
    metric_values: dict[str, Decimal],
    updated_at: datetime,
) -> dict[str, Any]:
    previous_metrics = previous_item.get("metrics") if previous_item else None
    if not isinstance(previous_metrics, dict):
        previous_metrics = {}

    updated_metrics: dict[str, dict[str, Any]] = {}
    metric_order = list(metric_values)
    for metric in metric_order:
        previous_metric_item = previous_metrics.get(metric)
        if not isinstance(previous_metric_item, dict):
            previous_metric_item = None
        updated_metric_item = build_stat_item(
            previous_metric_item,
            symbol=symbol,
            metric=metric,
            captured_at=captured_at,
            snapshot_checksum=snapshot_checksum,
            value=metric_values[metric],
            updated_at=updated_at,
        )
        updated_metrics[metric] = {
            field_name: updated_metric_item[field_name]
            for field_name in SUMMARY_METRIC_FIELDS
        }

    for metric_name, previous_metric_item in previous_metrics.items():
        if metric_name in updated_metrics or not isinstance(previous_metric_item, dict):
            continue
        updated_metrics[str(metric_name)] = dict(previous_metric_item)

    previous_version = int(previous_item.get("stats_version") or 0) if previous_item else 0
    missing_metrics = [
        metric_name
        for metric_name in metric_order
        if metric_name not in updated_metrics
    ]

    return {
        "pk": symbol,
        "sk": STATS_SUMMARY_KEY,
        "symbol": symbol,
        "record_type": STATS_SUMMARY_KEY,
        "metric_count": len(updated_metrics),
        "metrics": updated_metrics,
        "missing_metrics": missing_metrics,
        "last_source_captured_at": captured_at,
        "last_source_checksum": snapshot_checksum,
        "last_updated_at": updated_at.isoformat(),
        "stats_scope": SAMPLE_NAME,
        "stats_version": previous_version + 1,
    }
