from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
ANALYTICS_CATALOG_TABLE = DYNAMODB_RESOURCE.Table(os.environ["ANALYTICS_CATALOG_TABLE"])
CATALOG_PK = "analytics_catalog"


def _parse_iso_date(raw_value: str) -> date:
    return date.fromisoformat(str(raw_value).strip())


def _find_latest_trading_date(*, lookback_days: int = 14) -> str | None:
    for offset in range(lookback_days + 1):
        candidate = (datetime.now(BOGOTA_TIMEZONE).date() - timedelta(days=offset)).isoformat()
        response = CURRENT_SNAPSHOTS_TABLE.query(
            IndexName="captured-date-index",
            KeyConditionExpression=Key("captured_date").eq(candidate),
            Limit=1,
        )
        if response.get("Items"):
            return candidate
    return None


def _load_snapshots_for_trading_date(trading_date: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": "captured-date-index",
        "KeyConditionExpression": Key("captured_date").eq(trading_date),
    }
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _select_latest_two_snapshots_per_symbol(
    snapshots: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    latest_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        symbol = str(snapshot.get("symbol") or "").strip().upper()
        captured_at = str(snapshot.get("captured_at") or "").strip()
        if not symbol or not captured_at:
            continue
        entries = latest_by_symbol.setdefault(symbol, [])
        entries.append(snapshot)
        entries.sort(key=lambda item: str(item.get("captured_at") or ""), reverse=True)
        del entries[2:]
    return latest_by_symbol


def _build_catalog_item(
    *,
    trading_date: str,
    snapshots: list[dict[str, Any]],
    previous_item: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_by_symbol = _select_latest_two_snapshots_per_symbol(snapshots)
    sorted_symbols = sorted(latest_by_symbol)

    records = [
        {
            "symbol": symbol,
            "current_snapshot_key": {
                "symbol": symbol,
                "captured_at": str(latest_by_symbol[symbol][0]["captured_at"]),
            },
            "previous_snapshot_key": None
            if len(latest_by_symbol[symbol]) < 2
            else {
                "symbol": symbol,
                "captured_at": str(latest_by_symbol[symbol][1]["captured_at"]),
            },
        }
        for symbol in sorted_symbols
    ]
    to_timestamp = max(
        (record["current_snapshot_key"]["captured_at"] for record in records),
        default=None,
    )
    previous_version = 0 if previous_item is None else int(previous_item.get("catalog_version", 0) or 0)
    return {
        "pk": CATALOG_PK,
        "record_type": "analytics_catalog",
        "trading_date": trading_date,
        "to_timestamp": to_timestamp,
        "symbols": sorted_symbols,
        "symbol_count": len(sorted_symbols),
        "record_count": len(records),
        "records": records,
        "catalog_version": previous_version + 1,
        "updated_at": datetime.now(BOGOTA_TIMEZONE).isoformat(),
    }


def _persist_catalog(item: dict[str, Any]) -> None:
    ANALYTICS_CATALOG_TABLE.put_item(Item=item)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    apply_changes = bool(event.get("apply", False))
    requested_trading_date = event.get("trading_date")

    trading_date = (
        _parse_iso_date(requested_trading_date).isoformat()
        if requested_trading_date
        else _find_latest_trading_date()
    )

    if trading_date is None:
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "apply": apply_changes,
                    "trading_date": None,
                    "snapshots_read": 0,
                    "catalog_symbol_count": 0,
                    "catalog_record_count": 0,
                    "to_timestamp": None,
                    "records": [],
                    "updated": False,
                }
            ),
        }

    snapshots = _load_snapshots_for_trading_date(trading_date)
    previous_item = ANALYTICS_CATALOG_TABLE.get_item(Key={"pk": CATALOG_PK}).get("Item")
    catalog_item = _build_catalog_item(
        trading_date=trading_date,
        snapshots=snapshots,
        previous_item=previous_item,
    )

    if apply_changes and catalog_item["record_count"] > 0:
        _persist_catalog(catalog_item)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "apply": apply_changes,
                "trading_date": trading_date,
                "snapshots_read": len(snapshots),
                "catalog_symbol_count": catalog_item["symbol_count"],
                "catalog_record_count": catalog_item["record_count"],
                "to_timestamp": catalog_item["to_timestamp"],
                "records": catalog_item["records"],
                "updated": apply_changes and catalog_item["record_count"] > 0,
            }
        ),
    }
