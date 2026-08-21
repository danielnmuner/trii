from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from snapshot_metrics import (
    SUPPORTED_STATISTICAL_METRIC_KEYS,
    extract_metric_values,
    normalize_metric_keys,
    parse_metric_keys,
)
from seasonality_profile import (
    SEASONALITY_PROFILE_KEY,
    build_seasonality_profile_items_from_snapshots,
)
from stats_engine import build_stat_item
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["HISTORIC_STATS_TABLE"])
LIVE_ENABLED_STATISTICAL_METRICS = parse_metric_keys(os.environ.get("ENABLED_STATISTICAL_METRICS"))


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def _normalize_symbols(raw_symbols: Any) -> list[str] | None:
    if raw_symbols is None:
        return None

    if not isinstance(raw_symbols, list):
        raise ValueError("symbols must be a list of uppercase stock symbols.")

    symbols: list[str] = []
    for raw_symbol in raw_symbols:
        symbol = str(raw_symbol).strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols or None


def _normalize_requested_metrics(raw_metric_names: Any) -> tuple[str, ...]:
    if raw_metric_names is None:
        raise ValueError(
            "metric_names is required so the backfill only touches the new metrics you want to rebuild."
        )
    if not isinstance(raw_metric_names, list):
        raise ValueError("metric_names must be a list of supported metric keys.")
    return normalize_metric_keys(raw_metric_names)


def _snapshot_matches_range(
    snapshot: dict[str, Any],
    captured_at_from: datetime | None,
    captured_at_to: datetime | None,
) -> bool:
    snapshot_timestamp = _parse_timestamp(str(snapshot["captured_at"]))
    if captured_at_from is not None and snapshot_timestamp < captured_at_from:
        return False
    if captured_at_to is not None and snapshot_timestamp > captured_at_to:
        return False
    return True


def _query_snapshots_for_symbol(
    symbol: str,
    captured_at_from: str | None,
    captured_at_to: str | None,
) -> list[dict[str, Any]]:
    key_condition = Key("symbol").eq(symbol)
    if captured_at_from and captured_at_to:
        key_condition = key_condition & Key("captured_at").between(captured_at_from, captured_at_to)
    elif captured_at_from:
        key_condition = key_condition & Key("captured_at").gte(captured_at_from)
    elif captured_at_to:
        key_condition = key_condition & Key("captured_at").lte(captured_at_to)

    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": key_condition,
        "ScanIndexForward": True,
    }
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _scan_all_snapshots() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _load_snapshots(
    *,
    symbols: list[str] | None,
    captured_at_from: datetime | None,
    captured_at_to: datetime | None,
    captured_at_from_raw: str | None,
    captured_at_to_raw: str | None,
) -> list[dict[str, Any]]:
    if symbols:
        snapshots: list[dict[str, Any]] = []
        for symbol in symbols:
            snapshots.extend(
                _query_snapshots_for_symbol(symbol, captured_at_from_raw, captured_at_to_raw)
            )
    else:
        snapshots = _scan_all_snapshots()

    filtered_snapshots = [
        snapshot
        for snapshot in snapshots
        if _snapshot_matches_range(snapshot, captured_at_from, captured_at_to)
    ]
    filtered_snapshots.sort(key=lambda item: (str(item["symbol"]), str(item["captured_at"])))
    return filtered_snapshots


def rebuild_stat_items_from_snapshots(
    snapshots: list[dict[str, Any]],
    metric_names: tuple[str, ...],
    updated_at: datetime,
) -> dict[tuple[str, str], dict[str, Any]]:
    rebuilt_items: dict[tuple[str, str], dict[str, Any]] = {}
    standard_metric_names = tuple(
        metric_name
        for metric_name in metric_names
        if metric_name != SEASONALITY_PROFILE_KEY
    )

    if standard_metric_names:
        for snapshot in snapshots:
            symbol = str(snapshot["symbol"]).strip().upper()
            captured_at = str(snapshot["captured_at"]).strip()
            snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
            if not symbol or not captured_at or not snapshot_checksum:
                continue

            metric_values = extract_metric_values(snapshot, standard_metric_names)
            for metric_name in standard_metric_names:
                metric_value = metric_values.get(metric_name)
                if metric_value is None:
                    continue
                item_key = (symbol, metric_name)
                rebuilt_items[item_key] = build_stat_item(
                    rebuilt_items.get(item_key),
                    symbol=symbol,
                    metric=metric_name,
                    captured_at=captured_at,
                    snapshot_checksum=snapshot_checksum,
                    value=metric_value,
                    updated_at=updated_at,
                )

    if SEASONALITY_PROFILE_KEY in metric_names:
        rebuilt_items.update(
            build_seasonality_profile_items_from_snapshots(
                snapshots,
                updated_at,
            )
        )

    return rebuilt_items


def _persist_items(items: dict[tuple[str, str], dict[str, Any]]) -> None:
    for item in items.values():
        HISTORIC_STATS_TABLE.put_item(Item=item)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    apply_changes = bool(event.get("apply", False))
    symbols = _normalize_symbols(event.get("symbols"))
    metric_names = _normalize_requested_metrics(event.get("metric_names"))
    captured_at_from_raw = event.get("captured_at_from")
    captured_at_to_raw = event.get("captured_at_to")
    captured_at_from = _parse_timestamp(captured_at_from_raw) if captured_at_from_raw else None
    captured_at_to = _parse_timestamp(captured_at_to_raw) if captured_at_to_raw else None

    snapshots = _load_snapshots(
        symbols=symbols,
        captured_at_from=captured_at_from,
        captured_at_to=captured_at_to,
        captured_at_from_raw=captured_at_from_raw,
        captured_at_to_raw=captured_at_to_raw,
    )
    updated_at = datetime.now(BOGOTA_TIMEZONE)
    rebuilt_items = rebuild_stat_items_from_snapshots(snapshots, metric_names, updated_at)

    if apply_changes:
        _persist_items(rebuilt_items)

    summary = {
        "apply": apply_changes,
        "requested_metrics": list(metric_names),
        "live_enabled_metrics": list(LIVE_ENABLED_STATISTICAL_METRICS),
        "supported_metrics": list(SUPPORTED_STATISTICAL_METRIC_KEYS),
        "symbols": symbols or "ALL",
        "captured_at_from": captured_at_from_raw,
        "captured_at_to": captured_at_to_raw,
        "snapshots_read": len(snapshots),
        "stat_items_rebuilt": len(rebuilt_items),
        "rebuilt_keys": [
            {"symbol": symbol, "metric": metric}
            for symbol, metric in sorted(rebuilt_items.keys())
        ],
    }

    return {
        "statusCode": 200,
        "body": json.dumps(summary),
    }
