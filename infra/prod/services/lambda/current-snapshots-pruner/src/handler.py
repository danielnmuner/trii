from __future__ import annotations

import json
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
DESERIALIZER = TypeDeserializer()
MAX_SNAPSHOTS_PER_SYMBOL = 2
FULL_SCAN_MODE = "full-scan"


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _load_stale_keys(symbol: str) -> list[dict[str, str]]:
    stale_keys: list[dict[str, str]] = []
    retained_count = 0
    query_kwargs: dict[str, Any] = {
        "ConsistentRead": True,
        "KeyConditionExpression": Key("symbol").eq(symbol),
        "ProjectionExpression": "symbol, captured_at",
        "ScanIndexForward": False,
    }

    while True:
        response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
        for item in response.get("Items", []):
            if retained_count < MAX_SNAPSHOTS_PER_SYMBOL:
                retained_count += 1
                continue
            stale_keys.append(
                {
                    "symbol": str(item["symbol"]),
                    "captured_at": str(item["captured_at"]),
                }
            )

        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key

    return stale_keys


def _prune_symbol(symbol: str) -> int:
    stale_keys = _load_stale_keys(symbol)
    if not stale_keys:
        return 0

    with CURRENT_SNAPSHOTS_TABLE.batch_writer() as batch:
        for key in stale_keys:
            batch.delete_item(Key=key)
    return len(stale_keys)


def _scan_symbols() -> set[str]:
    symbols: set[str] = set()
    scan_kwargs: dict[str, Any] = {
        "ProjectionExpression": "#symbol",
        "ExpressionAttributeNames": {
            "#symbol": "symbol",
        },
    }

    while True:
        response = CURRENT_SNAPSHOTS_TABLE.scan(**scan_kwargs)
        for item in response.get("Items", []):
            symbol = str(item.get("symbol") or "").strip().upper()
            if symbol:
                symbols.add(symbol)

        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

    return symbols


def _manual_full_scan() -> dict[str, int | str]:
    symbols = _scan_symbols()
    deleted_items = 0
    for symbol in sorted(symbols):
        deleted_items += _prune_symbol(symbol)

    return {
        "mode": FULL_SCAN_MODE,
        "processed_symbols": len(symbols),
        "deleted_items": deleted_items,
        "ignored_records": 0,
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if str(event.get("mode") or "").strip().lower() == FULL_SCAN_MODE:
        return {
            "statusCode": 200,
            "body": json.dumps(_manual_full_scan()),
        }

    symbols: set[str] = set()
    ignored_records = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            ignored_records += 1
            continue
        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            ignored_records += 1
            continue
        item = _deserialize_item(new_image)
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            ignored_records += 1
            continue
        symbols.add(symbol)

    deleted_items = 0
    for symbol in sorted(symbols):
        deleted_items += _prune_symbol(symbol)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "mode": "stream",
                "processed_symbols": len(symbols),
                "deleted_items": deleted_items,
                "ignored_records": ignored_records,
            }
        ),
    }
