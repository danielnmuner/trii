from decimal import Decimal
from typing import Any


PASS_THROUGH_METRIC_KEYS = (
    "last_price",
    "daily_change_amount",
    "daily_change_percent",
    "traded_volume",
    "traded_value",
)


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


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator


def sum_level_quantities(levels: Any) -> Decimal | None:
    if not isinstance(levels, list):
        return None

    total = Decimal("0")
    found = False
    for level in levels[:5]:
        if not isinstance(level, dict):
            continue
        quantity = to_decimal(level.get("quantity"))
        if quantity is None:
            continue
        total += quantity
        found = True

    return total if found else None


def derive_metric_values(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    metrics: dict[str, Decimal] = {}

    best_bid_price = to_decimal(snapshot.get("best_bid_price"))
    best_ask_price = to_decimal(snapshot.get("best_ask_price"))
    best_bid_quantity = to_decimal(snapshot.get("best_bid_quantity"))
    best_ask_quantity = to_decimal(snapshot.get("best_ask_quantity"))
    bid_depth_total_5 = sum_level_quantities(snapshot.get("bid_levels"))
    ask_depth_total_5 = sum_level_quantities(snapshot.get("ask_levels"))

    if best_bid_price is not None and best_ask_price is not None:
        spread = best_ask_price - best_bid_price
        mid_price = (best_bid_price + best_ask_price) / Decimal("2")
        metrics["spread"] = spread
        metrics["mid_price"] = mid_price

        spread_bps = safe_divide(spread * Decimal("10000"), mid_price)
        if spread_bps is not None:
            metrics["spread_bps"] = spread_bps

    if (
        best_bid_price is not None
        and best_ask_price is not None
        and best_bid_quantity is not None
        and best_ask_quantity is not None
    ):
        total_l1_quantity = best_bid_quantity + best_ask_quantity
        microprice_numerator = (
            (best_ask_price * best_bid_quantity)
            + (best_bid_price * best_ask_quantity)
        )
        microprice = safe_divide(microprice_numerator, total_l1_quantity)
        obi_l1 = safe_divide(
            best_bid_quantity - best_ask_quantity,
            total_l1_quantity,
        )

        if microprice is not None:
            metrics["microprice"] = microprice
        if obi_l1 is not None:
            metrics["obi_l1"] = obi_l1

    if bid_depth_total_5 is not None:
        metrics["bid_depth_total_5"] = bid_depth_total_5
    if ask_depth_total_5 is not None:
        metrics["ask_depth_total_5"] = ask_depth_total_5

    if bid_depth_total_5 is not None and ask_depth_total_5 is not None:
        total_depth = bid_depth_total_5 + ask_depth_total_5
        obi_top_5 = safe_divide(
            bid_depth_total_5 - ask_depth_total_5,
            total_depth,
        )
        book_pressure_ratio = safe_divide(bid_depth_total_5, ask_depth_total_5)

        if obi_top_5 is not None:
            metrics["obi_top_5"] = obi_top_5
        if book_pressure_ratio is not None:
            metrics["book_pressure_ratio"] = book_pressure_ratio

    if "microprice" in metrics and "mid_price" in metrics:
        metrics["depth_weighted_microprice_deviation"] = (
            metrics["microprice"] - metrics["mid_price"]
        )

    return metrics


def extract_metric_values(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    metrics = derive_metric_values(snapshot)

    for key in PASS_THROUGH_METRIC_KEYS:
        value = to_decimal(snapshot.get(key))
        if value is not None:
            metrics[key] = value

    return metrics
