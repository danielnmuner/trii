import json
import os
import time
from datetime import datetime
from decimal import Decimal
import hashlib
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError
from snapshot_metrics import extract_metric_values, to_decimal
from zoneinfo import ZoneInfo


DYNAMODB_CLIENT = boto3.client("dynamodb")
LAMBDA_CLIENT = boto3.client("lambda")
DESERIALIZER = TypeDeserializer()
SERIALIZER = TypeSerializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
HISTORIC_STATS_TABLE = os.environ["HISTORIC_STATS_TABLE"]
PROCESSED_STATS_EVENTS_TABLE = os.environ["PROCESSED_STATS_EVENTS_TABLE"]
MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION = os.environ["MARKET_AI_RECOMMENDATION_HANDLER_FUNCTION"]


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def _serialize_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in values.items()}


def _parse_captured_at(raw_value: str) -> datetime:
    timestamp = datetime.fromisoformat(raw_value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def _build_bucket_time(captured_at: datetime) -> str:
    return captured_at.strftime("%H:%M:%S")


def _extract_metric_values(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    return extract_metric_values(snapshot)


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
    bucket_time = _build_bucket_time(_parse_captured_at(captured_at))

    return {
        "symbol": symbol,
        "captured_at": captured_at,
        "bucket_time": bucket_time,
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


def _load_current_stat_items(pk: str, metrics: list[str]) -> dict[str, dict[str, Any]]:
    return _load_existing_stat_items(pk, metrics)


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


def _build_stat_item(
    previous_item: dict[str, Any] | None,
    *,
    symbol: str,
    metric: str,
    bucket_time: str,
    captured_at: str,
    snapshot_checksum: str,
    value: Decimal,
) -> dict[str, Any]:
    previous_count = int(previous_item["sample_count"]) if previous_item else 0
    previous_mean = _to_decimal(previous_item["mean"]) if previous_item else Decimal("0")
    previous_m2 = _to_decimal(previous_item["m2"]) if previous_item else Decimal("0")
    previous_min = _to_decimal(previous_item["min_value"]) if previous_item else value
    previous_max = _to_decimal(previous_item["max_value"]) if previous_item else value

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
        "pk": f"{symbol}#{bucket_time}",
        "sk": metric,
        "symbol": symbol,
        "metric": metric,
        "bucket_time": bucket_time,
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
        "last_updated_at": datetime.now(BOGOTA_TIMEZONE).isoformat(),
        "stats_scope": "all_time_intraday_bucket",
        "stats_version": stats_version,
    }


def _transact_snapshot(snapshot: dict[str, Any], source_event_id: str) -> str:
    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    captured_timestamp = _parse_captured_at(captured_at)
    bucket_time = _build_bucket_time(captured_timestamp)
    snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
    if not snapshot_checksum:
        raise ValueError("Snapshot checksum is required for idempotent historic stats updates.")

    metrics = _extract_metric_values(snapshot)
    if not metrics:
        return "skipped-no-metrics"

    metric_names = sorted(metrics.keys())
    updated_items: dict[str, dict[str, Any]] = {}

    for _attempt in range(3):
        previous_items = _load_existing_stat_items(f"{symbol}#{bucket_time}", metric_names)
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
                            "bucket_time": bucket_time,
                            "processed_at": datetime.now(BOGOTA_TIMEZONE).isoformat(),
                            "source_event_id": source_event_id,
                            "metrics_processed": metric_names,
                        }
                    ),
                    "ConditionExpression": "attribute_not_exists(snapshot_checksum)",
                }
            }
        ]

        for metric_name in metric_names:
            previous_item = previous_items.get(metric_name)
            updated_item = _build_stat_item(
                previous_item,
                symbol=symbol,
                metric=metric_name,
                bucket_time=bucket_time,
                captured_at=captured_at,
                snapshot_checksum=snapshot_checksum,
                value=metrics[metric_name],
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
                current_items = _load_current_stat_items(f"{symbol}#{bucket_time}", metric_names)
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
