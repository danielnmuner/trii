import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
BEDROCK_CLIENT = boto3.client("bedrock-runtime")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["HISTORIC_STATS_TABLE"])
MARKET_AI_RECOMMENDATIONS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["MARKET_AI_RECOMMENDATIONS_TABLE"])
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    return value


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def _compute_z_score(stat_item: dict[str, Any]) -> float | None:
    latest_value = _safe_decimal(stat_item.get("latest_value"))
    mean = _safe_decimal(stat_item.get("mean"))
    stddev = _safe_decimal(stat_item.get("stddev"))
    sample_count = int(stat_item.get("sample_count", 0) or 0)
    if latest_value is None or mean is None or stddev is None:
        return None
    if sample_count < 2 or stddev == 0:
        return None
    return float((latest_value - mean) / stddev)


def _get_current_snapshot(symbol: str, captured_at: str) -> dict[str, Any]:
    response = CURRENT_SNAPSHOTS_TABLE.get_item(
        Key={
            "symbol": symbol,
            "captured_at": captured_at,
        }
    )
    item = response.get("Item")
    if not item:
        raise ValueError("Triggering snapshot was not found in current snapshots.")
    return item


def _get_previous_snapshot(symbol: str, captured_at: str) -> dict[str, Any] | None:
    response = CURRENT_SNAPSHOTS_TABLE.query(
        KeyConditionExpression=Key("symbol").eq(symbol) & Key("captured_at").lte(captured_at),
        ScanIndexForward=False,
        Limit=2,
    )
    items = response.get("Items", [])
    if len(items) < 2:
        return None
    return items[1]


def _load_stats(symbol: str) -> dict[str, Any]:
    response = HISTORIC_STATS_TABLE.query(
        KeyConditionExpression=Key("pk").eq(symbol),
    )
    items = response.get("Items", [])
    return {
        str(item["metric"]): item
        for item in items
        if "metric" in item
    }


def _build_zscore_context(stats_items: dict[str, Any], metric_keys: tuple[str, ...]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for metric_key in metric_keys:
        stat_item = stats_items.get(metric_key)
        if not stat_item:
            continue
        context[metric_key] = {
            "latest_value": _json_ready(stat_item.get("latest_value")),
            "mean": _json_ready(stat_item.get("mean")),
            "stddev": _json_ready(stat_item.get("stddev")),
            "sample_count": _json_ready(stat_item.get("sample_count")),
            "z_score": _compute_z_score(stat_item),
        }
    return context


def _extract_model_text(response: dict[str, Any]) -> str | None:
    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])
    for item in content:
        if "text" in item:
            return item["text"]
    return None


def _invoke_bedrock(prompt: str) -> dict[str, Any]:
    response = BEDROCK_CLIENT.converse(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
    )
    return {
        "model_id": os.environ["BEDROCK_MODEL_ID"],
        "text": _extract_model_text(response),
    }


def _build_placeholder_summary(symbol: str, triggered_rules: list[str]) -> str:
    joined_rules = ", ".join(triggered_rules)
    return (
        f"Placeholder market recommendation for {symbol}. "
        f"The automatic trigger bundle fired because these rules were matched: {joined_rules}."
    )


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    symbol = str(event.get("symbol") or "").strip().upper()
    captured_at = str(event.get("captured_at") or "").strip()
    trigger_signature = str(event.get("trigger_signature") or "").strip()
    triggered_rules = [
        str(rule).strip()
        for rule in event.get("triggered_rules", [])
        if str(rule).strip()
    ]
    snapshot_checksum = str(event.get("snapshot_checksum") or "").strip()

    if not symbol or not captured_at or not trigger_signature:
        raise ValueError("symbol, captured_at, and trigger_signature are required.")

    current_snapshot = _get_current_snapshot(symbol, captured_at)
    previous_snapshot = _get_previous_snapshot(symbol, captured_at)
    current_stats = _load_stats(symbol)

    zscore_context = _build_zscore_context(current_stats, ("obi_l1", "obi_top_5", "spread_bps"))
    created_at = datetime.now(BOGOTA_TIMEZONE).isoformat()
    invoke_model = os.environ.get("INVOKE_BEDROCK_MODEL", "false").lower() == "true"

    recommendation_summary = _build_placeholder_summary(symbol, triggered_rules)
    recommendation_status = "placeholder"
    model_result = {
        "skipped": True,
        "reason": "Bedrock invocation is disabled until prompt and production rules are finalized.",
        "model_id": os.environ["BEDROCK_MODEL_ID"],
    }

    if invoke_model:
        prompt = json.dumps(
            {
                "symbol": symbol,
                "captured_at": captured_at,
                "triggered_rules": triggered_rules,
                "zscore_context": zscore_context,
                "current_snapshot": _json_ready(current_snapshot),
                "previous_snapshot": _json_ready(previous_snapshot),
            },
            ensure_ascii=False,
        )
        model_result = _invoke_bedrock(prompt)
        recommendation_summary = model_result.get("text") or recommendation_summary
        recommendation_status = "generated"

    item = {
        "trigger_signature": trigger_signature,
        "symbol": symbol,
        "captured_at": captured_at,
        "snapshot_checksum": snapshot_checksum,
        "current_snapshot_key": {
            "symbol": symbol,
            "captured_at": captured_at,
        },
        "previous_snapshot_key": None
        if previous_snapshot is None
        else {
            "symbol": symbol,
            "captured_at": str(previous_snapshot["captured_at"]),
        },
        "current_stats_pk": symbol,
        "triggered_rules": triggered_rules,
        "zscore_context": zscore_context,
        "recommendation_status": recommendation_status,
        "recommendation_summary": recommendation_summary,
        "recommendation_details": {
            "model_result": model_result,
            "current_snapshot": _json_ready(current_snapshot),
            "previous_snapshot": _json_ready(previous_snapshot),
            "current_stats": _json_ready(current_stats),
        },
        "model_id": os.environ["BEDROCK_MODEL_ID"],
        "model_invoked": invoke_model,
        "created_at": created_at,
    }

    try:
        MARKET_AI_RECOMMENDATIONS_TABLE.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(trigger_signature)",
        )
        status = "stored"
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        status = "duplicate"

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "status": status,
                "trigger_signature": trigger_signature,
                "symbol": symbol,
                "captured_at": captured_at,
                "triggered_rules": triggered_rules,
            }
        ),
    }
