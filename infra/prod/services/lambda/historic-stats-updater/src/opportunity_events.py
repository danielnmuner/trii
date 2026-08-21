from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any

from snapshot_metrics import to_decimal


Z_SCORE_THRESHOLD = Decimal("1.5")
TRIGGER_METRIC_KEYS = (
    "spread_bps",
    "obi_l1",
    "obi_top_5",
    "traded_volume",
    "traded_value",
    "volume_rate",
    "value_rate",
)


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


def build_triggered_z_scores(
    stat_items: dict[str, dict[str, Any]],
    *,
    threshold: Decimal = Z_SCORE_THRESHOLD,
) -> dict[str, dict[str, Decimal]]:
    triggered: dict[str, dict[str, Decimal]] = {}
    for metric_key in TRIGGER_METRIC_KEYS:
        stat_item = stat_items.get(metric_key)
        if stat_item is None:
            continue
        z_score = compute_z_score(stat_item)
        if z_score is None or abs(z_score) < threshold:
            continue
        sample_value = to_decimal(stat_item.get("latest_value"))
        if sample_value is None:
            continue
        triggered[metric_key] = {
            "sample_value": sample_value,
            "z_score": z_score,
        }
    return triggered


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
            (
                lot["remaining_quantity"] * lot["price_per_share"]
                for lot in fifo_lots
            ),
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
    triggered_z_scores: dict[str, dict[str, Decimal]],
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
        "triggered_z_scores": triggered_z_scores,
        "last_price": to_decimal(snapshot.get("last_price")),
        "daily_change_amount": to_decimal(snapshot.get("daily_change_amount")),
        "daily_change_percent": to_decimal(snapshot.get("daily_change_percent")),
        "previous_close": to_decimal(snapshot.get("previous_close")),
        "high_price": to_decimal(snapshot.get("high_price")),
        "low_price": to_decimal(snapshot.get("low_price")),
        "bid_levels": snapshot.get("bid_levels", []),
        "ask_levels": snapshot.get("ask_levels", []),
        "approved_position_summary": position_summary,
    }
