from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
HISTORIC_STATS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["HISTORIC_STATS_TABLE"])
DESERIALIZER = TypeDeserializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
STATS_SUMMARY_KEY = "stats_summary"
TARGET_METRICS = (
    "vwap",
    "spread_bps",
    "obi_l1",
    "obi_top_5",
    "traded_volume",
    "traded_value",
)
SUMMARY_FIELDS_BY_METRIC = {
    "vwap": (
        "metric",
        "stddev",
        "sample_count",
    ),
    "spread_bps": (
        "metric",
        "latest_value",
        "mean",
        "stddev",
        "sample_count",
        "min_value",
        "max_value",
    ),
    "obi_l1": (
        "metric",
        "latest_value",
        "mean",
        "stddev",
        "sample_count",
        "min_value",
        "max_value",
    ),
    "obi_top_5": (
        "metric",
        "latest_value",
        "mean",
        "stddev",
        "sample_count",
        "min_value",
        "max_value",
    ),
    "traded_volume": (
        "metric",
        "latest_value",
        "mean",
        "stddev",
        "sample_count",
        "min_value",
        "max_value",
    ),
    "traded_value": (
        "metric",
        "latest_value",
        "mean",
        "stddev",
        "sample_count",
        "min_value",
        "max_value",
    ),
}


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _summary_checksum(metrics_payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(_json_ready(metrics_payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _scan_symbols() -> list[str]:
    symbols: set[str] = set()
    scan_kwargs: dict[str, Any] = {
        "ProjectionExpression": "#pk, #sk",
        "ExpressionAttributeNames": {
            "#pk": "pk",
            "#sk": "sk",
        },
    }

    while True:
        response = HISTORIC_STATS_TABLE.scan(**scan_kwargs)
        for item in response.get("Items", []):
            symbol = str(item.get("pk") or "").strip().upper()
            metric = str(item.get("sk") or "").strip()
            if symbol and metric in TARGET_METRICS:
                symbols.add(symbol)

        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

    return sorted(symbols)


def _load_symbol_items(symbol: str) -> dict[str, dict[str, Any]]:
    response = HISTORIC_STATS_TABLE.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(symbol),
    )
    return {
        str(item.get("sk") or "").strip(): item
        for item in response.get("Items", [])
    }


def _project_metric_item(item: dict[str, Any], metric: str) -> tuple[dict[str, Any] | None, list[str]]:
    required_fields = SUMMARY_FIELDS_BY_METRIC[metric]
    validation_errors: list[str] = []
    projected: dict[str, Any] = {"metric": metric}

    if str(item.get("pk") or "").strip().upper() == "":
        validation_errors.append("missing pk")
    if str(item.get("sk") or "").strip() != metric:
        validation_errors.append(f"sk mismatch for {metric}")
    if str(item.get("metric") or "").strip() != metric:
        validation_errors.append(f"metric field mismatch for {metric}")

    for field_name in required_fields:
        if field_name not in item:
            validation_errors.append(f"{metric} missing field {field_name}")
            continue
        projected[field_name] = item[field_name]

    if validation_errors:
        return None, validation_errors

    return projected, []


def _build_summary_item(
    symbol: str,
    items_by_sk: dict[str, dict[str, Any]],
    existing_summary: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    metrics_payload: dict[str, Any] = {}
    missing_metrics: list[str] = []
    validation_errors: list[str] = []
    source_metric_versions: dict[str, int] = {}
    latest_source_captured_at: str | None = None

    for metric in TARGET_METRICS:
        item = items_by_sk.get(metric)
        if item is None:
            missing_metrics.append(metric)
            continue

        projected_item, errors = _project_metric_item(item, metric)
        if errors:
            validation_errors.extend(errors)
            continue

        metrics_payload[metric] = projected_item
        source_metric_versions[metric] = int(item.get("stats_version") or 0)
        captured_at = str(item.get("last_source_captured_at") or "").strip()
        if captured_at and (latest_source_captured_at is None or captured_at > latest_source_captured_at):
            latest_source_captured_at = captured_at

    status = "complete" if not missing_metrics and not validation_errors else "partial"
    source_checksum = _summary_checksum(metrics_payload)
    previous_stats_version = int(existing_summary.get("stats_version") or 0) if existing_summary else 0
    previous_checksum = str(existing_summary.get("source_checksum") or "").strip() if existing_summary else ""
    summary_item = {
        "pk": symbol,
        "sk": STATS_SUMMARY_KEY,
        "symbol": symbol,
        "record_type": STATS_SUMMARY_KEY,
        "metric_count": len(metrics_payload),
        "metrics": metrics_payload,
        "missing_metrics": missing_metrics,
        "migration_status": status,
        "source_metric_versions": source_metric_versions,
        "source_checksum": source_checksum,
        "last_source_captured_at": latest_source_captured_at,
        "last_updated_at": datetime.now(BOGOTA_TIMEZONE).isoformat(),
        "stats_version": previous_stats_version + 1 if previous_checksum != source_checksum else previous_stats_version,
    }

    return (
        None if validation_errors else summary_item,
        {
            "symbol": symbol,
            "metric_count": len(metrics_payload),
            "missing_metrics": missing_metrics,
            "validation_errors": validation_errors,
            "source_checksum": source_checksum,
            "existing_checksum": previous_checksum,
            "changed": previous_checksum != source_checksum,
        },
    )


def _summary_matches_source(summary_item: dict[str, Any], expected_summary: dict[str, Any]) -> bool:
    return (
        str(summary_item.get("source_checksum") or "").strip()
        == str(expected_summary.get("source_checksum") or "").strip()
        and _json_ready(summary_item.get("metrics") or {}) == _json_ready(expected_summary.get("metrics") or {})
        and sorted(summary_item.get("missing_metrics") or []) == sorted(expected_summary.get("missing_metrics") or [])
    )


def _cleanup_legacy_items(symbol: str, items_by_sk: dict[str, dict[str, Any]]) -> int:
    deleted_items = 0
    with HISTORIC_STATS_TABLE.batch_writer() as batch:
        for metric in TARGET_METRICS:
            if metric not in items_by_sk:
                continue
            batch.delete_item(Key={"pk": symbol, "sk": metric})
            deleted_items += 1
    return deleted_items


def _run(mode: str, symbol: str | None, confirm_delete_legacy: bool) -> dict[str, Any]:
    symbols = [symbol] if symbol else _scan_symbols()
    migrated = 0
    skipped = 0
    invalid = 0
    cleaned_up = 0
    results: list[dict[str, Any]] = []

    for current_symbol in symbols:
        items_by_sk = _load_symbol_items(current_symbol)
        existing_summary = items_by_sk.get(STATS_SUMMARY_KEY)
        summary_item, validation = _build_summary_item(current_symbol, items_by_sk, existing_summary)
        validation["has_existing_summary"] = existing_summary is not None

        if summary_item is None:
            invalid += 1
            results.append(validation)
            continue

        if mode == "validate":
            validation["valid"] = existing_summary is not None and _summary_matches_source(existing_summary, summary_item)
            if validation["valid"]:
                skipped += 1
            else:
                migrated += 1
            results.append(validation)
            continue

        if mode == "cleanup":
            if not confirm_delete_legacy:
                raise ValueError("cleanup mode requires `confirm_delete_legacy=true`.")
            if existing_summary is None or not _summary_matches_source(existing_summary, summary_item):
                validation["valid"] = False
                invalid += 1
                results.append(validation)
                continue
            cleaned_up += _cleanup_legacy_items(current_symbol, items_by_sk)
            validation["valid"] = True
            results.append(validation)
            continue

        if existing_summary is not None and not validation["changed"]:
            skipped += 1
            results.append(validation)
            continue

        HISTORIC_STATS_TABLE.put_item(Item=summary_item)
        migrated += 1
        results.append(validation)

    return {
        "mode": mode,
        "processed_symbols": len(symbols),
        "migrated_symbols": migrated,
        "skipped_symbols": skipped,
        "invalid_symbols": invalid,
        "deleted_legacy_items": cleaned_up,
        "results": results,
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    mode = str(event.get("mode") or "migrate").strip().lower()
    if mode not in {"migrate", "validate", "cleanup"}:
        raise ValueError("`mode` must be migrate, validate, or cleanup.")

    symbol = str(event.get("symbol") or "").strip().upper() or None
    confirm_delete_legacy = bool(event.get("confirm_delete_legacy"))

    return {
        "statusCode": 200,
        "body": json.dumps(_run(mode, symbol, confirm_delete_legacy)),
    }
