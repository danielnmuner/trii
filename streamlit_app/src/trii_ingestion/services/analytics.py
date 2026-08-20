from __future__ import annotations

import json
import math
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


MARKET_REGIMES: tuple[tuple[set[int], tuple[int, int], tuple[int, int]], ...] = (
    (set((3, 4, 5, 6, 7, 8, 9, 10)), (8, 30), (15, 0)),
    (set((11, 12, 1, 2)), (9, 30), (16, 0)),
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
            levels = _normalize_depth_levels(record.get(levels_key))
            if not levels:
                continue

            for level in levels[:5]:
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


def compute_latest_z_score(records: list[dict[str, Any]], metric_key: str) -> float | None:
    if not records:
        return None

    latest_value = _safe_float(records[0].get(metric_key))
    if latest_value is None:
        return None

    series = [
        value
        for record in records
        if (value := _safe_float(record.get(metric_key))) is not None
    ]
    if len(series) < 2:
        return None

    mean_value = sum(series) / len(series)
    variance = sum((value - mean_value) ** 2 for value in series) / len(series)
    sigma = math.sqrt(variance)
    if sigma == 0:
        return None

    return (latest_value - mean_value) / sigma


def build_z_score_context(
    records: list[dict[str, Any]],
    metric_key: str,
    *,
    current_time: datetime | None = None,
) -> dict[str, str | float | int | None]:
    z_score = compute_latest_z_score(records, metric_key)
    sample_size, expected_points = _build_intraday_sample_stats(records, current_time=current_time)
    coverage_ratio = 0.0 if expected_points == 0 else min(sample_size / expected_points, 1.0)

    if coverage_ratio >= 0.8:
        sample_label = "Representative"
    elif coverage_ratio >= 0.45:
        sample_label = "Partial"
    else:
        sample_label = "Thin"

    anomaly_label = None
    if z_score is not None:
        absolute_z = abs(z_score)
        if absolute_z >= 3.0:
            anomaly_label = "Anomaly"
        elif absolute_z >= 2.0:
            anomaly_label = "Review"
        else:
            anomaly_label = "Normal"

    return {
        "z_score": z_score,
        "sample_label": sample_label,
        "sample_size": sample_size,
        "anomaly_label": anomaly_label,
        "coverage_ratio": coverage_ratio,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_intraday_coverage_ratio(
    records: list[dict[str, Any]],
    *,
    current_time: datetime | None = None,
) -> float:
    actual_points, expected_points = _build_intraday_sample_stats(records, current_time=current_time)
    if expected_points == 0:
        return 0.0
    return min(actual_points / expected_points, 1.0)


def _build_intraday_sample_stats(
    records: list[dict[str, Any]],
    *,
    current_time: datetime | None = None,
) -> tuple[int, int]:
    timestamps = _parse_intraday_timestamps(records)
    if not timestamps:
        return 0, 0

    evaluation_time = current_time or max(timestamps)
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=BOGOTA_TIMEZONE)
    evaluation_time = evaluation_time.astimezone(BOGOTA_TIMEZONE)

    market_open, market_close = _resolve_market_session_bounds(evaluation_time)
    if evaluation_time < market_open:
        return 0, 0

    session_limit = min(evaluation_time, market_close)
    if session_limit <= market_open:
        return 0, 0

    window_start = min(timestamps)
    effective_start = max(window_start, market_open)
    if effective_start > session_limit:
        return 0, 0

    expected_points = max(int((session_limit - effective_start).total_seconds() // 60) + 1, 1)
    actual_points = len(
        {
            timestamp.replace(second=0, microsecond=0)
            for timestamp in timestamps
            if effective_start <= timestamp <= session_limit
        }
    )
    return actual_points, expected_points

def _parse_intraday_timestamps(records: list[dict[str, Any]]) -> list[datetime]:
    return [
        timestamp
        for record in records
        if (timestamp := parse_record_timestamp(record)) is not None
    ]


def _resolve_market_session_bounds(value: datetime) -> tuple[datetime, datetime]:
    month = value.month
    for months, open_hm, close_hm in MARKET_REGIMES:
        if month in months:
            open_hour, open_minute = open_hm
            close_hour, close_minute = close_hm
            market_open = value.replace(
                hour=open_hour,
                minute=open_minute,
                second=0,
                microsecond=0,
            )
            market_close = value.replace(
                hour=close_hour,
                minute=close_minute,
                second=0,
                microsecond=0,
            )
            return market_open, market_close

    fallback_open = value.replace(hour=8, minute=30, second=0, microsecond=0)
    fallback_close = value.replace(hour=15, minute=0, second=0, microsecond=0)
    return fallback_open, fallback_close


def _normalize_depth_levels(raw_levels: Any) -> list[dict[str, Any]]:
    if isinstance(raw_levels, str):
        try:
            raw_levels = json.loads(raw_levels)
        except json.JSONDecodeError:
            return []

    if isinstance(raw_levels, dict) and "L" in raw_levels:
        raw_levels = raw_levels.get("L", [])

    if not isinstance(raw_levels, list):
        return []

    normalized_levels: list[dict[str, Any]] = []
    for level in raw_levels:
        normalized_level = _normalize_single_level(level)
        if normalized_level is not None:
            normalized_levels.append(normalized_level)

    return normalized_levels


def _normalize_single_level(raw_level: Any) -> dict[str, Any] | None:
    if isinstance(raw_level, dict) and "M" in raw_level:
        raw_level = raw_level.get("M", {})

    if not isinstance(raw_level, dict):
        return None

    normalized = {
        "level": _unwrap_dynamo_value(raw_level.get("level")),
        "price": _unwrap_dynamo_value(raw_level.get("price")),
        "quantity": _unwrap_dynamo_value(raw_level.get("quantity")),
    }

    if normalized["level"] is None:
        return None
    return normalized


def _unwrap_dynamo_value(value: Any) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        return value

    if "N" in value:
        raw_number = value["N"]
        try:
            numeric_value = float(raw_number)
        except (TypeError, ValueError):
            return raw_number
        return int(numeric_value) if numeric_value.is_integer() else numeric_value

    if "S" in value:
        return value["S"]

    if "M" in value:
        return {
            key: _unwrap_dynamo_value(item)
            for key, item in value["M"].items()
        }

    if "L" in value:
        return [_unwrap_dynamo_value(item) for item in value["L"]]

    return value
