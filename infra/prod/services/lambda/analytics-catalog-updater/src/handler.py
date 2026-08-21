from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
DESERIALIZER = TypeDeserializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
ANALYTICS_CATALOG_TABLE = DYNAMODB_RESOURCE.Table(os.environ["ANALYTICS_CATALOG_TABLE"])
CATALOG_PK = "analytics_catalog"


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _load_catalog() -> dict[str, Any] | None:
    response = ANALYTICS_CATALOG_TABLE.get_item(Key={"pk": CATALOG_PK})
    return response.get("Item")


def _build_catalog_item(
    current_item: dict[str, Any] | None,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    working = current_item
    for snapshot in snapshots:
        symbol = str(snapshot.get("symbol") or "").strip().upper()
        captured_at = str(snapshot.get("captured_at") or "").strip()
        trading_date = str(snapshot.get("captured_date") or captured_at[:10]).strip()
        if not symbol or not captured_at or not trading_date:
            continue

        if working is None or trading_date > str(working.get("trading_date") or ""):
            working = {
                "pk": CATALOG_PK,
                "record_type": "analytics_catalog",
                "trading_date": trading_date,
                "to_timestamp": captured_at,
                "symbols": [],
                "records": [],
                "catalog_version": 0,
            }
        elif trading_date < str(working.get("trading_date") or ""):
            continue

        record_by_symbol = {
            str(record.get("symbol") or "").strip().upper(): dict(record)
            for record in working.get("records", [])
            if str(record.get("symbol") or "").strip()
        }
        existing_record = record_by_symbol.get(symbol)
        existing_current_key = {}
        existing_previous_key = None
        if existing_record is not None:
            existing_current_key = dict(existing_record.get("current_snapshot_key") or {})
            raw_previous_key = existing_record.get("previous_snapshot_key")
            existing_previous_key = None if raw_previous_key is None else dict(raw_previous_key)

        if existing_record is None:
            record_by_symbol[symbol] = {
                "symbol": symbol,
                "current_snapshot_key": {
                    "symbol": symbol,
                    "captured_at": captured_at,
                },
                "previous_snapshot_key": None,
            }
        elif captured_at >= str(existing_current_key.get("captured_at") or ""):
            new_previous_key = existing_current_key or None
            record_by_symbol[symbol] = {
                "symbol": symbol,
                "current_snapshot_key": {
                    "symbol": symbol,
                    "captured_at": captured_at,
                },
                "previous_snapshot_key": new_previous_key,
            }
        elif existing_previous_key is None or captured_at > str(existing_previous_key.get("captured_at") or ""):
            record_by_symbol[symbol] = {
                "symbol": symbol,
                "current_snapshot_key": existing_current_key,
                "previous_snapshot_key": {
                    "symbol": symbol,
                    "captured_at": captured_at,
                },
            }

        records = [record_by_symbol[key] for key in sorted(record_by_symbol)]
        working["records"] = records
        working["symbols"] = [record["symbol"] for record in records]
        working["symbol_count"] = len(records)
        working["record_count"] = len(records)
        if captured_at > str(working.get("to_timestamp") or ""):
            working["to_timestamp"] = captured_at

    if working is None:
        return None

    updated_item = dict(working)
    updated_item["updated_at"] = datetime.now(BOGOTA_TIMEZONE).isoformat()
    return updated_item


def _persist_catalog(item: dict[str, Any], previous_item: dict[str, Any] | None) -> bool:
    try:
        if previous_item is None:
            item["catalog_version"] = 1
            ANALYTICS_CATALOG_TABLE.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
        else:
            expected_version = int(previous_item.get("catalog_version", 0) or 0)
            item["catalog_version"] = expected_version + 1
            ANALYTICS_CATALOG_TABLE.put_item(
                Item=item,
                ConditionExpression="catalog_version = :expected_version",
                ExpressionAttributeValues={":expected_version": expected_version},
            )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        return False


def _apply_snapshots(snapshots: list[dict[str, Any]]) -> bool:
    filtered_snapshots = [
        snapshot
        for snapshot in snapshots
        if str(snapshot.get("symbol") or "").strip()
        and str(snapshot.get("captured_at") or "").strip()
    ]
    filtered_snapshots.sort(
        key=lambda snapshot: (
            str(snapshot.get("captured_date") or str(snapshot.get("captured_at") or "")[:10]),
            str(snapshot.get("captured_at") or ""),
            str(snapshot.get("symbol") or ""),
        )
    )
    if not filtered_snapshots:
        return False

    for _attempt in range(5):
        current_item = _load_catalog()
        updated_item = _build_catalog_item(current_item, filtered_snapshots)
        if updated_item is None:
            return False
        if _persist_catalog(updated_item, current_item):
            return True
    raise RuntimeError("Analytics catalog could not be updated after retries.")


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    snapshots = []
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            continue
        snapshots.append(_deserialize_item(new_image))

    updated = _apply_snapshots(snapshots)
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "updated": updated,
                "processed_records": len(snapshots),
            }
        ),
    }
