import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from snapshot_metrics import extract_metric_values
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["HISTORIC_STATS_TABLE"])
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


def _parse_captured_at(raw_value: str) -> datetime:
    timestamp = datetime.fromisoformat(str(raw_value))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def _build_bucket_time(captured_at: datetime) -> str:
    return captured_at.strftime("%H:%M:%S")


def _extract_metric_values(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    return extract_metric_values(snapshot)


def _update_aggregate(
    aggregates: dict[tuple[str, str], dict[str, Any]],
    *,
    snapshot: dict[str, Any],
) -> None:
    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    captured_timestamp = _parse_captured_at(captured_at)
    bucket_time = _build_bucket_time(captured_timestamp)
    metrics = _extract_metric_values(snapshot)

    for metric, value in metrics.items():
        aggregate_key = (f"{symbol}#{bucket_time}", metric)
        current = aggregates.get(aggregate_key)
        if current is None:
            aggregates[aggregate_key] = {
                "pk": aggregate_key[0],
                "sk": metric,
                "symbol": symbol,
                "metric": metric,
                "bucket_time": bucket_time,
                "symbol_metric": f"{symbol}#{metric}",
                "sample_count": 1,
                "mean": value,
                "m2": Decimal("0"),
                "min_value": value,
                "max_value": value,
                "latest_value": value,
                "last_source_captured_at": captured_at,
                "last_source_checksum": str(snapshot.get("snapshot_checksum", "")),
                "stats_scope": "all_time_intraday_bucket",
            }
            continue

        previous_count = int(current["sample_count"])
        previous_mean = current["mean"]
        previous_m2 = current["m2"]
        sample_count = previous_count + 1
        delta = value - previous_mean
        mean = previous_mean + (delta / Decimal(sample_count))
        delta_2 = value - mean
        m2 = previous_m2 + (delta * delta_2)

        current["sample_count"] = sample_count
        current["mean"] = mean
        current["m2"] = m2
        current["min_value"] = min(current["min_value"], value)
        current["max_value"] = max(current["max_value"], value)
        if captured_timestamp >= _parse_captured_at(current["last_source_captured_at"]):
            current["latest_value"] = value
            current["last_source_captured_at"] = captured_at
            current["last_source_checksum"] = str(snapshot.get("snapshot_checksum", ""))


def _scan_all_snapshots() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def handler(_event: dict[str, Any], _context: Any) -> dict[str, Any]:
    raw_snapshots = _scan_all_snapshots()
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}

    for snapshot in raw_snapshots:
        if "symbol" not in snapshot or "captured_at" not in snapshot:
            continue
        _update_aggregate(aggregates, snapshot=snapshot)

    rebuilt_at = datetime.now(BOGOTA_TIMEZONE).isoformat()
    with HISTORIC_STATS_TABLE.batch_writer(overwrite_by_pkeys=["pk", "sk"]) as batch:
        for aggregate in aggregates.values():
            sample_count = int(aggregate["sample_count"])
            if sample_count > 1:
                variance = aggregate["m2"] / Decimal(sample_count - 1)
                stddev = variance.sqrt()
            else:
                stddev = Decimal("0")

            item = dict(aggregate)
            item["stddev"] = stddev
            item["last_updated_at"] = rebuilt_at
            item["stats_version"] = sample_count
            batch.put_item(Item=item)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "snapshots_scanned": len(raw_snapshots),
                "stats_items_written": len(aggregates),
            }
        ),
    }
