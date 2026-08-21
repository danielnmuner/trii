from __future__ import annotations

import json
from datetime import datetime

from analytics_data import load_analytics_snapshot
from trii_ingestion.services import build_analytics_summary, now_in_bogota


type SymbolRecordGroup = tuple[str, dict, list[dict]]


def safe_float(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_metric_value(metric_key: str, value: float | None) -> str:
    if value is None:
        return "n/a"

    if metric_key in {"spread", "bid_depth_total_5", "ask_depth_total_5", "traded_volume"}:
        return f"{value:,.0f}"
    if metric_key == "traded_value":
        return f"{value:,.0f}"
    if metric_key == "vwap_cumulative":
        return f"{value:,.2f}"
    if metric_key == "daily_change_amount":
        return f"{value:,.2f}"
    if metric_key == "daily_change_percent":
        return f"{(value / 100):,.2f}%"
    if metric_key in {"mid_price", "microprice"}:
        return f"{value:,.2f}"
    if metric_key == "spread_bps":
        return f"{value:,.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{value:,.2f}"
    if metric_key == "depth_weighted_microprice_deviation":
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def format_cop_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    formatted = f"{round(value):,.0f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {formatted}"


def format_metric_delta(metric_key: str, current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None

    delta = current - previous
    if metric_key == "spread_bps":
        return f"{delta:+.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{delta:+.2f}"
    return f"{delta:+,.2f}"


def compute_cumulative_vwap(record: dict | None) -> float | None:
    if not isinstance(record, dict):
        return None
    traded_value = safe_float(record, "traded_value")
    traded_volume = safe_float(record, "traded_volume")
    if traded_value is None or traded_volume in (None, 0):
        return None
    return traded_value / traded_volume


def format_metric_delta_with_relative(
    metric_key: str,
    current: float | None,
    previous: float | None,
) -> str | None:
    absolute_delta = format_metric_delta(metric_key, current, previous)
    if absolute_delta is None or previous in (None, 0):
        return absolute_delta

    relative_delta = ((current - previous) / previous) * 100
    return f"{absolute_delta} ({relative_delta:+.2f}%)"


def build_market_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "last_price", "label": "Ultimo precio"},
        {"key": "vwap_cumulative", "label": "VWAP acumulado"},
        {"key": "best_prices", "label": "Mejor compra / venta"},
        {"key": "price_range", "label": "Maximo / minimo"},
        {"key": "spread", "label": "Spread"},
        {"key": "traded_volume", "label": "Volumen negociado"},
        {"key": "traded_value", "label": "Valor negociado"},
    ]


def build_symbol_analytics_groups(
    analytics_payloads: list[dict],
    selected_symbols: list[str],
) -> list[SymbolRecordGroup]:
    grouped = {
        str(payload.get("symbol", "")).strip().upper(): payload
        for payload in analytics_payloads
        if str(payload.get("symbol", "")).strip()
    }

    groups: list[SymbolRecordGroup] = []
    for symbol in selected_symbols:
        payload = grouped.get(symbol)
        if not payload:
            continue
        records = [
            record
            for record in [
                payload.get("current_snapshot"),
                payload.get("previous_snapshot"),
            ]
            if isinstance(record, dict) and record
        ]
        if records:
            groups.append((symbol, payload, records))

    return groups


def load_symbol_record_groups(selected_symbols: tuple[str, ...]) -> tuple[list[SymbolRecordGroup], dict]:
    analytics_payloads: list[dict] = []
    for selected_symbol in selected_symbols:
        analytics_response = load_analytics_snapshot(selected_symbol)
        analytics_result = analytics_response.get("result", {})
        if analytics_result.get("current_snapshot"):
            analytics_payloads.append(analytics_result)

    symbol_record_groups = build_symbol_analytics_groups(analytics_payloads, list(selected_symbols))
    filtered_records = [
        record
        for _, _, records in symbol_record_groups
        for record in records
        if isinstance(record, dict)
    ]
    filtered_records.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)

    summary = build_analytics_summary(
        filtered_records,
        current_time=now_in_bogota(),
    )
    return symbol_record_groups, summary


def stringify_record_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def normalize_records_for_table(records: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records:
        normalized_row = {
            str(key): stringify_record_value(value)
            for key, value in record.items()
        }
        rows.append(normalized_row)
    return rows


def signal_tone(label: str) -> str:
    normalized = label.strip().lower()
    if normalized == "anomaly":
        return "green"
    if normalized == "review":
        return "blue"
    return "gray"


def format_signed_cop(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{format_cop_price(abs(value))}"


def sample_count_label(sample_count: int) -> str | None:
    if sample_count <= 0:
        return None
    return f"{sample_count:,}"


def format_signed_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def format_plain_integer(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{round(float(value)):,}"


def format_elapsed_seconds(total_seconds: int) -> str:
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds:02d}s"


def refresh_tone(total_seconds: int) -> str:
    if total_seconds < 60:
        return "green"
    if total_seconds <= 300:
        return "orange"
    return "red"


def feed_age_tone(total_seconds: int) -> str:
    if total_seconds > 600:
        return "red"
    if total_seconds > 300:
        return "orange"
    return "green"


def format_trigger_reason(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("-", " ").replace("_", " ")
    if not normalized:
        return None
    return normalized.title()


def resolve_symbol_sample_count(current_stats: dict) -> int:
    counts = [
        int(stat_item.get("sample_count", 0) or 0)
        for stat_item in current_stats.values()
        if isinstance(stat_item, dict)
    ]
    return max(counts, default=0)


def parse_record_timestamp(raw_value: str | None, reference_time: datetime) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=reference_time.tzinfo)
    return parsed.astimezone(reference_time.tzinfo)


def format_z_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}{chr(963)}"


def format_samples(value: int) -> str:
    return f"{value:,}"
