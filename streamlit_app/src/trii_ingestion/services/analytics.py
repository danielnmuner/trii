from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
def now_in_bogota() -> datetime:
    return datetime.now(BOGOTA_TIMEZONE)


def format_timestamp_label(raw_value: str | None, *, fallback_time: str = "00:00:00") -> str:
    if not raw_value:
        return "n/a"

    normalized = raw_value.strip()
    if not normalized:
        return "n/a"

    if "T" not in normalized:
        normalized = f"{normalized}T{fallback_time}"

    timestamp = datetime.fromisoformat(normalized)
    return timestamp.strftime("%d-%m-%Y %H:%M")


def format_datetime_label(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(BOGOTA_TIMEZONE).strftime("%d-%m-%Y %H:%M:%S")


def parse_record_timestamp(record: dict[str, Any]) -> datetime | None:
    raw_value = record.get("captured_at")
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None

    try:
        timestamp = datetime.fromisoformat(raw_value.strip())
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def build_analytics_summary(
    records: list[dict[str, Any]],
    *,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    now_value = current_time or now_in_bogota()
    parsed_timestamps = [
        timestamp
        for record in records
        if (timestamp := parse_record_timestamp(record)) is not None
    ]

    if parsed_timestamps:
        from_timestamp = min(parsed_timestamps)
        to_timestamp = max(parsed_timestamps)
    else:
        from_timestamp = now_value
        to_timestamp = now_value

    tw_seconds = max(int((to_timestamp - from_timestamp).total_seconds()), 0)

    return {
        "record_count": len(records),
        "from_timestamp": format_datetime_label(from_timestamp),
        "to_timestamp": format_datetime_label(to_timestamp),
        "tw_seconds": tw_seconds,
    }


def build_depth_history_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for record in records:
        captured_at = record.get("captured_at")
        for side, levels_key in (("Bid", "bid_levels"), ("Ask", "ask_levels")):
            levels = record.get(levels_key)
            if not isinstance(levels, list):
                continue
            if not levels:
                continue

            for level in levels[:5]:
                normalized_level = _normalize_depth_level(level)
                if normalized_level is None:
                    continue

                level_number = int(normalized_level["level"])
                rows.append(
                    {
                        "captured_at": captured_at,
                        "side": side,
                        "level": level_number,
                        "level_label": f"Nivel {level_number}",
                        "price": float(normalized_level["price"]),
                        "quantity": float(normalized_level["quantity"]),
                    }
                )

    return rows

def build_historic_z_score_context(stat_item: dict[str, Any] | None) -> dict[str, str | float | int | None]:
    if not stat_item:
        return {
            "z_score": None,
            "sample_count": 0,
            "signal_label": None,
        }

    latest_value = _safe_float(stat_item.get("latest_value"))
    mean_value = _safe_float(stat_item.get("mean"))
    stddev_value = _safe_float(stat_item.get("stddev"))
    sample_count = int(stat_item.get("sample_count", 0) or 0)

    z_score = None
    if (
        latest_value is not None
        and mean_value is not None
        and stddev_value not in (None, 0.0)
        and sample_count >= 2
    ):
        z_score = (latest_value - mean_value) / stddev_value

    signal_label = None
    if z_score is not None:
        absolute_z = abs(z_score)
        if absolute_z >= 3.0:
            signal_label = "Anomaly"
        elif absolute_z >= 2.0:
            signal_label = "Review"
        else:
            signal_label = "Normal"

    return {
        "z_score": z_score,
        "sample_count": sample_count,
        "signal_label": signal_label,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _normalize_depth_level(raw_level: Any) -> dict[str, float | int] | None:
    if not isinstance(raw_level, dict):
        return None

    level = raw_level.get("level")
    price = raw_level.get("price")
    quantity = raw_level.get("quantity")
    if level is None or price is None or quantity is None:
        return None

    normalized_level = _safe_float(level)
    normalized_price = _safe_float(price)
    normalized_quantity = _safe_float(quantity)
    if normalized_level is None or normalized_price is None or normalized_quantity is None:
        return None

    return {
        "level": int(normalized_level),
        "price": normalized_price,
        "quantity": normalized_quantity,
    }
