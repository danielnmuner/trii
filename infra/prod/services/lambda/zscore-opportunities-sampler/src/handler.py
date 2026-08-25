from __future__ import annotations

import json
import os
from collections import deque
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from zoneinfo import ZoneInfo


TRIGGER_METRIC_KEYS = (
    "spread_bps",
    "obi_l1",
    "obi_top_5",
    "traded_volume",
    "traded_value",
    "volume_rate",
    "value_rate",
)

DYNAMODB_CLIENT = boto3.client("dynamodb")
DYNAMODB_RESOURCE = boto3.resource("dynamodb")
DESERIALIZER = TypeDeserializer()
SERIALIZER = TypeSerializer()
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
HISTORIC_STATS_TABLE = os.environ["HISTORIC_STATS_TABLE"]
STOCK_ORDERS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["STOCK_ORDERS_TABLE"])
ZSCORE_OPPORTUNITIES_TABLE = DYNAMODB_RESOURCE.Table(os.environ["ZSCORE_OPPORTUNITIES_TABLE"])


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _parse_iso_date(raw_value: Any) -> str:
    return date.fromisoformat(str(raw_value).strip()).isoformat()


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


def _select_latest_snapshot_per_symbol(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        symbol = str(snapshot.get("symbol") or "").strip().upper()
        captured_at = str(snapshot.get("captured_at") or "").strip()
        if not symbol or not captured_at:
            continue
        current = latest_by_symbol.get(symbol)
        if current is None or captured_at > str(current.get("captured_at") or ""):
            latest_by_symbol[symbol] = snapshot
    return latest_by_symbol


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def compute_z_score(stat_item: dict[str, Any]) -> Decimal | None:
    latest_value = to_decimal(stat_item.get("latest_value"))
    mean = to_decimal(stat_item.get("mean"))
    stddev = to_decimal(stat_item.get("stddev"))
    sample_count = int(stat_item.get("sample_count", 0) or 0)
    if latest_value is None or mean is None or stddev is None:
        return None
    if sample_count < 2 or stddev == 0:
        return None
    return (latest_value - mean) / stddev


def build_monitored_z_scores(
    stat_items: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Decimal]]:
    monitored: dict[str, dict[str, Decimal]] = {}
    for metric_key in TRIGGER_METRIC_KEYS:
        stat_item = stat_items.get(metric_key)
        if stat_item is None:
            continue
        z_score = compute_z_score(stat_item)
        if z_score is None:
            continue
        sample_value = to_decimal(stat_item.get("latest_value"))
        if sample_value is None:
            continue
        monitored[metric_key] = {
            "sample_value": sample_value,
            "z_score": z_score,
        }
    return monitored


def summarize_approved_position(orders: list[dict[str, Any]], symbol: str) -> dict[str, Any]:
    fifo_lots: deque[dict[str, Decimal]] = deque()
    approved_buy_quantity = Decimal("0")
    approved_sell_quantity = Decimal("0")

    sorted_orders = sorted(
        orders,
        key=lambda item: (
            str(item.get("created_at") or ""),
            int(item.get("source_line_number", 0) or 0),
            str(item.get("record_checksum") or ""),
        ),
    )
    for order in sorted_orders:
        if str(order.get("normalized_status") or "").strip().lower() != "approved":
            continue

        filled_quantity = to_decimal(order.get("filled_quantity"))
        price_per_share = to_decimal(order.get("price_per_share"))
        order_side = str(order.get("order_side") or "").strip().lower()
        if (
            filled_quantity is None
            or price_per_share is None
            or filled_quantity <= 0
            or order_side not in {"buy", "sell"}
        ):
            continue

        if order_side == "buy":
            approved_buy_quantity += filled_quantity
            fifo_lots.append(
                {
                    "remaining_quantity": filled_quantity,
                    "price_per_share": price_per_share,
                }
            )
            continue

        approved_sell_quantity += filled_quantity
        quantity_to_consume = filled_quantity
        while quantity_to_consume > 0 and fifo_lots:
            oldest_lot = fifo_lots[0]
            lot_quantity = oldest_lot["remaining_quantity"]
            consumed_quantity = min(lot_quantity, quantity_to_consume)
            oldest_lot["remaining_quantity"] = lot_quantity - consumed_quantity
            quantity_to_consume -= consumed_quantity
            if oldest_lot["remaining_quantity"] <= 0:
                fifo_lots.popleft()

    available_quantity = sum((lot["remaining_quantity"] for lot in fifo_lots), Decimal("0"))
    weighted_average_price = None
    if available_quantity > 0:
        remaining_notional = sum(
            (lot["remaining_quantity"] * lot["price_per_share"] for lot in fifo_lots),
            Decimal("0"),
        )
        weighted_average_price = remaining_notional / available_quantity

    return {
        "symbol": symbol,
        "approved_buy_quantity": approved_buy_quantity,
        "approved_sell_quantity": approved_sell_quantity,
        "available_quantity": available_quantity,
        "weighted_average_price": weighted_average_price,
    }


def build_zscore_opportunity_item(
    snapshot: dict[str, Any],
    monitored_z_scores: dict[str, dict[str, Decimal]],
    position_summary: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    symbol = str(snapshot["symbol"]).strip().upper()
    captured_at = str(snapshot["captured_at"]).strip()
    trading_date = str(snapshot.get("captured_date") or captured_at[:10]).strip()

    return {
        "snapshot_checksum": str(snapshot.get("snapshot_checksum") or "").strip(),
        "symbol": symbol,
        "captured_at": captured_at,
        "trading_date": trading_date,
        "symbol_captured_at": f"{symbol}#{captured_at}",
        "created_at": created_at.isoformat(),
        "triggered_z_scores": monitored_z_scores,
        "last_price": to_decimal(snapshot.get("last_price")),
        "daily_change_amount": to_decimal(snapshot.get("daily_change_amount")),
        "daily_change_percent": (
            None
            if to_decimal(snapshot.get("daily_change_percent")) is None
            else to_decimal(snapshot.get("daily_change_percent")) / Decimal("100")
        ),
        "previous_close": to_decimal(snapshot.get("previous_close")),
        "high_price": to_decimal(snapshot.get("high_price")),
        "low_price": to_decimal(snapshot.get("low_price")),
        "bid_levels": snapshot.get("bid_levels", []),
        "ask_levels": snapshot.get("ask_levels", []),
        "approved_position_summary": position_summary,
    }


def _load_stat_items(symbol: str) -> dict[str, dict[str, Any]]:
    response = DYNAMODB_CLIENT.batch_get_item(
        RequestItems={
            HISTORIC_STATS_TABLE: {
                "Keys": [
                    _serialize_item({"pk": symbol, "sk": metric_key})
                    for metric_key in TRIGGER_METRIC_KEYS
                ]
            }
        }
    )
    items = response.get("Responses", {}).get(HISTORIC_STATS_TABLE, [])
    return {
        item["sk"]["S"]: _deserialize_item(item)
        for item in items
    }


def _load_approved_orders_for_symbol(symbol: str, captured_at: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": "symbol-created-at-index",
        "KeyConditionExpression": Key("symbol").eq(symbol) & Key("created_at").lte(captured_at),
        "ScanIndexForward": True,
    }
    while True:
        response = STOCK_ORDERS_TABLE.query(**query_kwargs)
        for item in response.get("Items", []):
            if str(item.get("normalized_status") or "").strip().lower() == "approved":
                items.append(item)
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _build_sample_item(snapshot: dict[str, Any], sampled_at: datetime) -> dict[str, Any] | None:
    symbol = str(snapshot.get("symbol") or "").strip().upper()
    captured_at = str(snapshot.get("captured_at") or "").strip()
    snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
    if not symbol or not captured_at or not snapshot_checksum:
        return None

    stat_items = _load_stat_items(symbol)
    monitored_z_scores = build_monitored_z_scores(stat_items)
    if not monitored_z_scores:
        return None

    position_summary = summarize_approved_position(
        _load_approved_orders_for_symbol(symbol, captured_at),
        symbol,
    )
    return build_zscore_opportunity_item(
        snapshot,
        monitored_z_scores,
        position_summary,
        sampled_at,
    )


def _persist_samples(samples: list[dict[str, Any]]) -> None:
    for item in samples:
        ZSCORE_OPPORTUNITIES_TABLE.put_item(Item=item)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    apply_changes = bool(event.get("apply", True))
    requested_trading_date = event.get("trading_date")
    invocation_mode = "schedule" if event.get("source") == "aws.events" else "manual"

    trading_date = (
        _parse_iso_date(requested_trading_date)
        if requested_trading_date
        else _find_latest_trading_date()
    )
    if trading_date is None:
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "apply": apply_changes,
                    "invocation_mode": invocation_mode,
                    "trading_date": None,
                    "snapshots_read": 0,
                    "symbols_sampled": 0,
                    "records_written": 0,
                    "records": [],
                    "skipped_symbols": [],
                }
            ),
        }

    snapshots = _load_snapshots_for_trading_date(trading_date)
    latest_by_symbol = _select_latest_snapshot_per_symbol(snapshots)
    sampled_at = datetime.now(BOGOTA_TIMEZONE)

    samples: list[dict[str, Any]] = []
    skipped_symbols: list[str] = []
    for symbol in sorted(latest_by_symbol):
        sample_item = _build_sample_item(latest_by_symbol[symbol], sampled_at)
        if sample_item is None:
            skipped_symbols.append(symbol)
            continue
        samples.append(sample_item)

    if apply_changes and samples:
        _persist_samples(samples)

    records = [
        {
            "symbol": str(item["symbol"]),
            "captured_at": str(item["captured_at"]),
            "snapshot_checksum": str(item["snapshot_checksum"]),
            "zscore_metric_count": len(item.get("triggered_z_scores", {})),
        }
        for item in samples
    ]
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "apply": apply_changes,
                "invocation_mode": invocation_mode,
                "trading_date": trading_date,
                "snapshots_read": len(snapshots),
                "symbols_sampled": len(samples),
                "records_written": len(samples) if apply_changes else 0,
                "records": records,
                "skipped_symbols": skipped_symbols,
            }
        ),
    }
