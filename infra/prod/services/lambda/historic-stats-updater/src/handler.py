import json
import os
import time
from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError
from seasonality_profile import (
    SEASONALITY_PROFILE_KEY,
    build_seasonality_profile_item,
)
from snapshot_metrics import extract_metric_values, parse_metric_keys
from stats_engine import STATS_SUMMARY_KEY, build_stats_summary_item
from zoneinfo import ZoneInfo


DYNAMODB_CLIENT = boto3.client("dynamodb")
DYNAMODB_RESOURCE = boto3.resource("dynamodb")
DESERIALIZER = TypeDeserializer()
SERIALIZER = TypeSerializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = os.environ["HISTORIC_STATS_TABLE"]
ENABLED_STATISTICAL_METRICS = parse_metric_keys(os.environ.get("ENABLED_STATISTICAL_METRICS"))


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in values.items()}


def _load_previous_snapshot(symbol: str, captured_at: str) -> dict[str, Any] | None:
    response = CURRENT_SNAPSHOTS_TABLE.query(
        KeyConditionExpression=Key("symbol").eq(symbol) & Key("captured_at").lte(captured_at),
        ScanIndexForward=False,
        Limit=2,
    )
    items = response.get("Items", [])
    if len(items) < 2:
        return None
    return items[1]


def _load_existing_stats_summary_item(symbol: str) -> dict[str, Any] | None:
    response = DYNAMODB_CLIENT.get_item(
        TableName=HISTORIC_STATS_TABLE,
        Key=_serialize_item({"pk": symbol, "sk": STATS_SUMMARY_KEY}),
    )
    item = response.get("Item")
    return None if item is None else _deserialize_item(item)


def _load_existing_seasonality_item(symbol: str) -> dict[str, Any] | None:
    response = DYNAMODB_CLIENT.get_item(
        TableName=HISTORIC_STATS_TABLE,
        Key=_serialize_item({"pk": symbol, "sk": SEASONALITY_PROFILE_KEY}),
    )
    item = response.get("Item")
    return None if item is None else _deserialize_item(item)


def _transact_snapshot(snapshot: dict[str, Any]) -> str:
    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
    if not snapshot_checksum:
        raise ValueError("Snapshot checksum is required for historic stats updates.")

    previous_snapshot = _load_previous_snapshot(symbol, captured_at)
    metrics = extract_metric_values(
        snapshot,
        ENABLED_STATISTICAL_METRICS,
        previous_snapshot=previous_snapshot,
    )
    updated_at = datetime.now(BOGOTA_TIMEZONE)

    for _attempt in range(3):
        previous_summary_item = _load_existing_stats_summary_item(symbol)
        previous_seasonality_item = _load_existing_seasonality_item(symbol)
        seasonality_item = build_seasonality_profile_item(
            previous_seasonality_item,
            snapshot=snapshot,
            previous_snapshot=previous_snapshot,
            updated_at=updated_at,
        )
        processed_units = []
        if metrics:
            processed_units.append(STATS_SUMMARY_KEY)
        if seasonality_item is not None:
            processed_units.append(SEASONALITY_PROFILE_KEY)
        if not processed_units:
            return "skipped-no-metrics"
        transact_items = []

        if metrics:
            updated_summary_item = build_stats_summary_item(
                previous_summary_item,
                symbol=symbol,
                captured_at=captured_at,
                snapshot_checksum=snapshot_checksum,
                metric_values=metrics,
                updated_at=updated_at,
            )
            put_request = {
                "TableName": HISTORIC_STATS_TABLE,
                "Item": _serialize_item(updated_summary_item),
            }
            if previous_summary_item is None:
                put_request["ConditionExpression"] = "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            else:
                put_request["ConditionExpression"] = "stats_version = :expected_version"
                put_request["ExpressionAttributeValues"] = _serialize_values(
                    {":expected_version": int(previous_summary_item["stats_version"])}
                )
            transact_items.append({"Put": put_request})

        if seasonality_item is not None:
            seasonality_put_request = {
                "TableName": HISTORIC_STATS_TABLE,
                "Item": _serialize_item(seasonality_item),
            }
            if previous_seasonality_item is None:
                seasonality_put_request["ConditionExpression"] = "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            else:
                seasonality_put_request["ConditionExpression"] = "stats_version = :expected_version"
                seasonality_put_request["ExpressionAttributeValues"] = _serialize_values(
                    {":expected_version": int(previous_seasonality_item["stats_version"])}
                )
            transact_items.append({"Put": seasonality_put_request})

        try:
            DYNAMODB_CLIENT.transact_write_items(TransactItems=transact_items)
            return "processed"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
            time.sleep(0.15)

    raise RuntimeError("Historic stats transaction could not be committed after retries.")


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    processed = 0
    skipped = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        result = _transact_snapshot(_deserialize_item(new_image))
        if result == "processed":
            processed += 1
        else:
            skipped += 1

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "processed": processed,
                "skipped": skipped,
            }
        ),
    }
