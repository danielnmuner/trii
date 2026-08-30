import json
import os
import time
from datetime import datetime
from decimal import Decimal
import hashlib
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError
from data_quality import build_data_quality_item, parse_captured_at
from seasonality_profile import (
    SEASONALITY_PROFILE_KEY,
    build_seasonality_profile_item,
)
from snapshot_metrics import extract_metric_values, parse_metric_keys, to_decimal
from stats_engine import build_stat_item
from zoneinfo import ZoneInfo


DYNAMODB_CLIENT = boto3.client("dynamodb")
DYNAMODB_RESOURCE = boto3.resource("dynamodb")
LAMBDA_CLIENT = boto3.client("lambda")
DESERIALIZER = TypeDeserializer()
SERIALIZER = TypeSerializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = os.environ["HISTORIC_STATS_TABLE"]
PROCESSED_STATS_EVENTS_TABLE = os.environ["PROCESSED_STATS_EVENTS_TABLE"]
MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION = os.environ["MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION"]
ENABLED_STATISTICAL_METRICS = parse_metric_keys(os.environ.get("ENABLED_STATISTICAL_METRICS"))
PROCESSED_STATS_EVENT_TTL_SECONDS = 24 * 60 * 60


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in values.items()}


def _extract_metric_values(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    previous_snapshot = _load_previous_snapshot(
        str(snapshot["symbol"]).strip().upper(),
        str(snapshot["captured_at"]).strip(),
    )
    return extract_metric_values(
        snapshot,
        ENABLED_STATISTICAL_METRICS,
        previous_snapshot=previous_snapshot,
    )


def _compute_z_score(stat_item: dict[str, Any]) -> Decimal | None:
    latest_value = to_decimal(stat_item.get("latest_value"))
    mean = to_decimal(stat_item.get("mean"))
    stddev = to_decimal(stat_item.get("stddev"))
    sample_count = int(stat_item.get("sample_count", 0) or 0)
    if latest_value is None or mean is None or stddev is None:
        return None
    if sample_count < 2 or stddev == 0:
        return None
    return (latest_value - mean) / stddev


def _build_trigger_signature(symbol: str, captured_at: str, triggered_rules: list[str]) -> str:
    payload = "|".join([symbol, captured_at, *sorted(triggered_rules)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_ai_trigger_payload(
    snapshot: dict[str, Any],
    stat_items: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    triggered_rules: list[str] = []
    zscore_context: dict[str, Any] = {}

    spread_bps_item = stat_items.get("spread_bps")
    if spread_bps_item is not None:
        spread_bps_latest = to_decimal(spread_bps_item.get("latest_value"))
        if spread_bps_latest is not None and spread_bps_latest >= Decimal("100"):
            triggered_rules.append("placeholder_wide_spread")
        zscore_context["spread_bps"] = {
            "latest_value": spread_bps_latest,
            "mean": to_decimal(spread_bps_item.get("mean")),
            "stddev": to_decimal(spread_bps_item.get("stddev")),
            "sample_count": int(spread_bps_item.get("sample_count", 0) or 0),
            "z_score": _compute_z_score(spread_bps_item),
        }

    for metric_key, rule_name in (
        ("obi_l1", "placeholder_obi_l1_extreme"),
        ("obi_top_5", "placeholder_obi_top_5_extreme"),
    ):
        stat_item = stat_items.get(metric_key)
        if stat_item is None:
            continue
        z_score = _compute_z_score(stat_item)
        if z_score is not None and abs(z_score) >= Decimal("2.0"):
            triggered_rules.append(rule_name)
        zscore_context[metric_key] = {
            "latest_value": to_decimal(stat_item.get("latest_value")),
            "mean": to_decimal(stat_item.get("mean")),
            "stddev": to_decimal(stat_item.get("stddev")),
            "sample_count": int(stat_item.get("sample_count", 0) or 0),
            "z_score": z_score,
        }

    if not triggered_rules:
        return None

    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    return {
        "symbol": symbol,
        "captured_at": captured_at,
        "snapshot_checksum": str(snapshot.get("snapshot_checksum") or "").strip(),
        "triggered_rules": sorted(triggered_rules),
        "trigger_signature": _build_trigger_signature(symbol, captured_at, triggered_rules),
        "zscore_context": {
            key: {
                inner_key: (str(inner_value) if isinstance(inner_value, Decimal) else inner_value)
                for inner_key, inner_value in value.items()
            }
            for key, value in zscore_context.items()
        },
    }


def _invoke_market_ai_recommendation_handler(payload: dict[str, Any]) -> None:
    LAMBDA_CLIENT.invoke(
        FunctionName=MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION,
        InvocationType="Event",
        Payload=json.dumps(payload).encode("utf-8"),
    )


def _load_existing_stat_items(pk: str, metrics: list[str]) -> dict[str, dict[str, Any]]:
    if not metrics:
        return {}

    response = DYNAMODB_CLIENT.batch_get_item(
        RequestItems={
            HISTORIC_STATS_TABLE: {
                "Keys": [
                    _serialize_item({"pk": pk, "sk": metric})
                    for metric in metrics
                ]
            }
        }
    )
    items = response.get("Responses", {}).get(HISTORIC_STATS_TABLE, [])
    return {
        item["sk"]["S"]: _deserialize_item(item)
        for item in items
    }


def _processed_event_exists(snapshot_checksum: str) -> bool:
    response = DYNAMODB_CLIENT.get_item(
        TableName=PROCESSED_STATS_EVENTS_TABLE,
        Key=_serialize_item({"snapshot_checksum": snapshot_checksum}),
        ProjectionExpression="snapshot_checksum",
    )
    return "Item" in response


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


def _load_existing_data_quality_item(symbol: str, trading_date: str) -> dict[str, Any] | None:
    response = DYNAMODB_CLIENT.get_item(
        TableName=HISTORIC_STATS_TABLE,
        Key=_serialize_item({"pk": symbol, "sk": f"data_quality#{trading_date}"}),
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


def _transact_snapshot(snapshot: dict[str, Any], source_event_id: str) -> str:
    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    captured_timestamp = parse_captured_at(captured_at)
    snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
    if not snapshot_checksum:
        raise ValueError("Snapshot checksum is required for idempotent historic stats updates.")

    previous_snapshot = _load_previous_snapshot(symbol, captured_at)
    metrics = extract_metric_values(
        snapshot,
        ENABLED_STATISTICAL_METRICS,
        previous_snapshot=previous_snapshot,
    )
    metric_names = sorted(metrics.keys())
    updated_items: dict[str, dict[str, Any]] = {}
    updated_at = datetime.now(BOGOTA_TIMEZONE)
    previous_timestamp = None
    if previous_snapshot is not None:
        previous_timestamp = parse_captured_at(str(previous_snapshot["captured_at"]))

    for _attempt in range(3):
        previous_items = _load_existing_stat_items(symbol, metric_names)
        previous_data_quality_item = _load_existing_data_quality_item(symbol, captured_at[:10])
        previous_seasonality_item = _load_existing_seasonality_item(symbol)
        data_quality_item = build_data_quality_item(
            previous_data_quality_item,
            symbol=symbol,
            current_timestamp=captured_timestamp,
            previous_timestamp=previous_timestamp,
            updated_at=updated_at,
        )
        seasonality_item = build_seasonality_profile_item(
            previous_seasonality_item,
            snapshot=snapshot,
            previous_snapshot=previous_snapshot,
            updated_at=updated_at,
        )
        processed_units = list(metric_names)
        if seasonality_item is not None:
            processed_units.append(SEASONALITY_PROFILE_KEY)
        if data_quality_item is not None:
            processed_units.append(str(data_quality_item["sk"]))
        if not processed_units:
            return "skipped-no-metrics"
        processed_timestamp = datetime.now(BOGOTA_TIMEZONE)
        transact_items = [
            {
                "Put": {
                    "TableName": PROCESSED_STATS_EVENTS_TABLE,
                    "Item": _serialize_item(
                        {
                            "snapshot_checksum": snapshot_checksum,
                            "captured_date": captured_at[:10],
                            "symbol": symbol,
                            "captured_at": captured_at,
                            "symbol_captured_at": f"{symbol}#{captured_at}",
                            "processed_at": processed_timestamp.isoformat(),
                            "expires_at": int(processed_timestamp.timestamp())
                            + PROCESSED_STATS_EVENT_TTL_SECONDS,
                            "source_event_id": source_event_id,
                            "metrics_processed": processed_units,
                        }
                    ),
                    "ConditionExpression": "attribute_not_exists(snapshot_checksum)",
                }
            }
        ]

        for metric_name in metric_names:
            previous_item = previous_items.get(metric_name)
            updated_item = build_stat_item(
                previous_item,
                symbol=symbol,
                metric=metric_name,
                captured_at=captured_at,
                snapshot_checksum=snapshot_checksum,
                value=metrics[metric_name],
                updated_at=updated_at,
            )
            updated_items[metric_name] = updated_item
            put_request = {
                "TableName": HISTORIC_STATS_TABLE,
                "Item": _serialize_item(updated_item),
            }
            if previous_item is None:
                put_request["ConditionExpression"] = "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            else:
                put_request["ConditionExpression"] = "stats_version = :expected_version"
                put_request["ExpressionAttributeValues"] = _serialize_values(
                    {":expected_version": int(previous_item["stats_version"])}
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

        if data_quality_item is not None:
            data_quality_put_request = {
                "TableName": HISTORIC_STATS_TABLE,
                "Item": _serialize_item(data_quality_item),
            }
            if previous_data_quality_item is None:
                data_quality_put_request["ConditionExpression"] = "attribute_not_exists(pk) AND attribute_not_exists(sk)"
            else:
                data_quality_put_request["ConditionExpression"] = "stats_version = :expected_version"
                data_quality_put_request["ExpressionAttributeValues"] = _serialize_values(
                    {":expected_version": int(previous_data_quality_item["stats_version"])}
                )
            transact_items.append({"Put": data_quality_put_request})

        try:
            DYNAMODB_CLIENT.transact_write_items(TransactItems=transact_items)
            trigger_payload = _build_ai_trigger_payload(snapshot, updated_items)
            if trigger_payload is not None:
                _invoke_market_ai_recommendation_handler(trigger_payload)
            return "processed"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise
            if _processed_event_exists(snapshot_checksum):
                current_items = _load_existing_stat_items(symbol, metric_names)
                trigger_payload = _build_ai_trigger_payload(snapshot, current_items)
                if trigger_payload is not None:
                    _invoke_market_ai_recommendation_handler(trigger_payload)
                return "duplicate"
            time.sleep(0.15)

    raise RuntimeError("Historic stats transaction could not be committed after retries.")


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    processed = 0
    duplicates = 0
    skipped = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            skipped += 1
            continue

        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        result = _transact_snapshot(
            _deserialize_item(new_image),
            str(record.get("eventID", "")),
        )
        if result == "processed":
            processed += 1
        elif result == "duplicate":
            duplicates += 1
        else:
            skipped += 1

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "processed": processed,
                "duplicates": duplicates,
                "skipped": skipped,
            }
        ),
    }
