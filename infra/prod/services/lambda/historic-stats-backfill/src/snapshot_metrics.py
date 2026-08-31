from decimal import Decimal
from datetime import datetime
from typing import Any


SUPPORTED_STATISTICAL_METRIC_KEYS = (
    "spread_bps",
    "obi_l1",
    "obi_top_5",
    "book_pressure_ratio",
    "depth_weighted_microprice_deviation",
    "traded_volume",
    "traded_value",
    "vwap",
    "volume_rate",
    "value_rate",
    "seasonality_profile",
)


def normalize_metric_keys(metric_keys: Any) -> tuple[str, ...]:
    if metric_keys is None:
        return SUPPORTED_STATISTICAL_METRIC_KEYS

    normalized: list[str] = []
    for raw_key in metric_keys:
        key = str(raw_key).strip()
        if not key:
            continue
        if key not in SUPPORTED_STATISTICAL_METRIC_KEYS:
            raise ValueError(f"Unsupported metric key: {key}")
        if key not in normalized:
            normalized.append(key)

    return tuple(normalized or SUPPORTED_STATISTICAL_METRIC_KEYS)


def parse_metric_keys(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None or not raw_value.strip():
        return SUPPORTED_STATISTICAL_METRIC_KEYS
    return normalize_metric_keys(raw_value.split(","))


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


def _parse_timestamp(raw_value: str) -> datetime | None:
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


def _get_trading_date(snapshot: dict[str, Any]) -> str | None:
    captured_date = str(snapshot.get("captured_date") or "").strip()
    if captured_date:
        return captured_date
    captured_at = str(snapshot.get("captured_at") or "").strip()
    if captured_at:
        return captured_at[:10]
    return None


def derive_metric_values(
    snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None = None,
) -> dict[str, Decimal]:
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

    traded_volume = to_decimal(snapshot.get("traded_volume"))
    if traded_volume is not None:
        metrics["traded_volume"] = traded_volume

    traded_value = to_decimal(snapshot.get("traded_value"))
    if traded_value is not None:
        metrics["traded_value"] = traded_value

    if traded_volume is not None and traded_value is not None and traded_volume > 0:
        vwap = safe_divide(traded_value, traded_volume)
        if vwap is not None:
            metrics["vwap"] = vwap

    if previous_snapshot is not None:
        current_trading_date = _get_trading_date(snapshot)
        previous_trading_date = _get_trading_date(previous_snapshot)
        current_timestamp = _parse_timestamp(snapshot.get("captured_at"))
        previous_timestamp = _parse_timestamp(previous_snapshot.get("captured_at"))
        previous_traded_volume = to_decimal(previous_snapshot.get("traded_volume"))
        previous_traded_value = to_decimal(previous_snapshot.get("traded_value"))

        if (
            current_trading_date
            and previous_trading_date
            and current_trading_date == previous_trading_date
            and current_timestamp is not None
            and previous_timestamp is not None
            and previous_traded_volume is not None
            and previous_traded_value is not None
        ):
            delta_seconds = Decimal(str((current_timestamp - previous_timestamp).total_seconds()))
            delta_volume = traded_volume - previous_traded_volume if traded_volume is not None else None
            delta_value = traded_value - previous_traded_value if traded_value is not None else None
            if (
                delta_seconds > 0
                and delta_volume is not None
                and delta_value is not None
                and delta_volume > 0
                and delta_value > 0
            ):
                metrics["volume_rate"] = delta_volume / delta_seconds
                metrics["value_rate"] = delta_value / delta_seconds

    return metrics


def extract_metric_values(
    snapshot: dict[str, Any],
    enabled_metric_keys: Any = None,
    *,
    previous_snapshot: dict[str, Any] | None = None,
) -> dict[str, Decimal]:
    derived_metrics = derive_metric_values(snapshot, previous_snapshot=previous_snapshot)
    selected_metric_keys = set(normalize_metric_keys(enabled_metric_keys))
    return {
        key: value
        for key, value in derived_metrics.items()
        if key in selected_metric_keys
    }
