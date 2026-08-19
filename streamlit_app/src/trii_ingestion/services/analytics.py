from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
TIME_WINDOW_OPTIONS: tuple[tuple[str, str, timedelta], ...] = (
    ("1h", "Ultima hora", timedelta(hours=1)),
    ("3h", "Ultimas 3 horas", timedelta(hours=3)),
    ("6h", "Ultimas 6 horas", timedelta(hours=6)),
    ("1d", "Ultimo dia", timedelta(days=1)),
    ("3d", "Ultimos 3 dias", timedelta(days=3)),
    ("7d", "Ultimos 7 dias", timedelta(days=7)),
)


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
    return value.astimezone(BOGOTA_TIMEZONE).strftime("%d-%m-%Y %H:%M")


def get_time_window_labels() -> list[str]:
    return [label for label, _, _ in TIME_WINDOW_OPTIONS]


def resolve_time_window(label: str) -> timedelta:
    for option_label, _, delta in TIME_WINDOW_OPTIONS:
        if option_label == label:
            return delta
    raise ValueError(f"Unsupported analytics time window: {label}")


def get_time_window_help_text(label: str) -> str:
    for option_label, description, _ in TIME_WINDOW_OPTIONS:
        if option_label == label:
            return description
    raise ValueError(f"Unsupported analytics time window: {label}")


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


def extract_symbols(records: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(record.get("symbol", "")).strip().upper()
            for record in records
            if str(record.get("symbol", "")).strip()
        }
    )


def filter_records(
    records: list[dict[str, Any]],
    *,
    symbol: str,
    window_label: str,
    current_time: datetime | None = None,
) -> list[dict[str, Any]]:
    now_value = current_time or now_in_bogota()
    window_delta = resolve_time_window(window_label)
    from_timestamp = now_value - window_delta
    normalized_symbol = symbol.strip().upper()
    filtered: list[dict[str, Any]] = []

    for record in records:
        if str(record.get("symbol", "")).strip().upper() != normalized_symbol:
            continue

        captured_at = parse_record_timestamp(record)
        if captured_at is None:
            continue
        if captured_at < from_timestamp or captured_at > now_value:
            continue

        filtered.append(record)

    filtered.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)
    return filtered


def build_analytics_summary(
    records: list[dict[str, Any]],
    *,
    window_label: str,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    now_value = current_time or now_in_bogota()
    fallback_from_timestamp = now_value - resolve_time_window(window_label)
    parsed_timestamps = [
        timestamp
        for record in records
        if (timestamp := parse_record_timestamp(record)) is not None
    ]

    if parsed_timestamps:
        from_timestamp = min(parsed_timestamps)
        to_timestamp = max(parsed_timestamps)
    else:
        from_timestamp = fallback_from_timestamp
        to_timestamp = now_value

    return {
        "record_count": len(records),
        "from_timestamp": format_datetime_label(from_timestamp),
        "to_timestamp": format_datetime_label(to_timestamp),
    }


def build_depth_history_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for record in records:
        captured_at = record.get("captured_at")
        for side, levels_key in (("Bid", "bid_levels"), ("Ask", "ask_levels")):
            levels = record.get(levels_key, [])
            if not isinstance(levels, list):
                continue

            for level in levels[:5]:
                if not isinstance(level, dict):
                    continue

                level_number = int(level.get("level", 0) or 0)
                rows.append(
                    {
                        "captured_at": captured_at,
                        "side": side,
                        "level": level_number,
                        "level_label": f"Nivel {level_number}",
                        "price": float(level.get("price", 0) or 0),
                        "quantity": float(level.get("quantity", 0) or 0),
                    }
                )

    return rows
