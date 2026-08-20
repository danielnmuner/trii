from __future__ import annotations
from html import escape
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import altair as alt
import pandas as pd
import streamlit as st

from backend import BackendConfigurationError, get_backend_client
from trii_ingestion.services import (
    ApiGatewayClientError,
    build_analytics_summary,
    build_depth_history_rows,
    build_historic_z_score_context,
    now_in_bogota,
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_analytics_catalog(days: int) -> dict:
    client = get_backend_client()
    return client.get_analytics_catalog(days=days)


@st.cache_data(ttl=60, show_spinner=False)
def _load_analytics_snapshot(symbol: str) -> dict:
    client = get_backend_client()
    return client.get_analytics_snapshot(symbol=symbol)


def _refresh_recent_snapshots_cache() -> None:
    _load_analytics_catalog.clear()
    _load_analytics_snapshot.clear()
    st.session_state["analytics_last_manual_refresh"] = now_in_bogota()


def _safe_float(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_metric_value(metric_key: str, value: float | None) -> str:
    if value is None:
        return "n/a"

    if metric_key in {"spread", "bid_depth_total_5", "ask_depth_total_5", "traded_volume"}:
        return f"{value:,.0f}"
    if metric_key == "traded_value":
        return f"{value:,.0f}"
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


def _format_cop_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {formatted}"


def _format_metric_delta(metric_key: str, current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None

    delta = current - previous
    if metric_key == "spread_bps":
        return f"{delta:+.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{delta:+.2f}"
    return f"{delta:+,.2f}"


def _format_metric_delta_with_relative(metric_key: str, current: float | None, previous: float | None) -> str | None:
    absolute_delta = _format_metric_delta(metric_key, current, previous)
    if absolute_delta is None or previous in (None, 0):
        return absolute_delta

    relative_delta = ((current - previous) / previous) * 100
    return f"{absolute_delta} ({relative_delta:+.2f}%)"


def _build_market_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "last_price", "label": "Ultimo precio"},
        {"key": "best_prices", "label": "Mejor compra / venta"},
        {"key": "price_range", "label": "Maximo / minimo"},
        {"key": "spread", "label": "Spread"},
        {"key": "traded_volume", "label": "Volumen negociado"},
        {"key": "traded_value", "label": "Valor negociado"},
    ]


def _build_symbol_analytics_groups(
    analytics_payloads: list[dict],
    selected_symbols: list[str],
) -> list[tuple[str, dict, list[dict]]]:
    grouped = {
        str(payload.get("symbol", "")).strip().upper(): payload
        for payload in analytics_payloads
        if str(payload.get("symbol", "")).strip()
    }

    groups: list[tuple[str, dict, list[dict]]] = []
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


def _signal_tone(label: str) -> str:
    normalized = label.strip().lower()
    if normalized == "anomaly":
        return "green"
    if normalized == "review":
        return "blue"
    return "gray"


def _sample_count_label(sample_count: int) -> str | None:
    if sample_count <= 0:
        return None
    return f"{sample_count:,}"


def _format_elapsed_seconds(total_seconds: int) -> str:
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds:02d}s"


def _refresh_tone(total_seconds: int) -> str:
    if total_seconds < 60:
        return "green"
    if total_seconds <= 300:
        return "orange"
    return "red"


def _feed_age_tone(total_seconds: int) -> str:
    if total_seconds > 600:
        return "red"
    if total_seconds > 300:
        return "orange"
    return "green"


def _format_trigger_reason(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("-", " ").replace("_", " ")
    if not normalized:
        return None
    return normalized.title()


def _resolve_symbol_sample_count(current_stats: dict) -> int:
    counts = [
        int(stat_item.get("sample_count", 0) or 0)
        for stat_item in current_stats.values()
        if isinstance(stat_item, dict)
    ]
    return max(counts, default=0)


def _render_microstructure_tape(symbol: str, payload: dict, records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    current_stats = payload.get("current_stats", {})
    symbol_sample_count = _resolve_symbol_sample_count(current_stats)
    symbol_sample_count_markup = (
        ""
        if symbol_sample_count <= 0
        else f"<div class='analytics-light-tape-sub'>{escape(_sample_count_label(symbol_sample_count) or '')}</div>"
    )
    items: list[str] = [
        (
            "<div class='analytics-light-tape-item analytics-light-tape-symbol'>"
            f"<div class='analytics-light-tape-main'>{escape(symbol)}</div>"
            f"{symbol_sample_count_markup}"
            "</div>"
        )
    ]

    for key, label in (
        ("obi_l1", "OBI L1"),
        ("obi_top_5", "OBI TOP 5"),
        ("spread_bps", "SPREAD BPS"),
        ("mid_price", "MID PRICE"),
        ("microprice", "MICROPRICE"),
    ):
        current_value = _safe_float(latest_record, key)
        previous_value = _safe_float(previous_record, key) if previous_record else None
        delta = _format_metric_delta_with_relative(key, current_value, previous_value) or "No prior point"
        z_score_markup = ""

        if key in {"obi_l1", "obi_top_5", "spread_bps"}:
            z_score_context = build_historic_z_score_context(current_stats.get(key))
            z_score_value = z_score_context["z_score"]
            z_score_label = None if z_score_value is None else f"{z_score_value:+.1f}"
            signal_label = z_score_context["signal_label"]
            z_score_markup = "".join(
                [
                    "<div class='analytics-light-tape-zscore-stack'>",
                    (
                        ""
                        if z_score_label is None
                        else f"<span class='analytics-light-tape-zscore'>{escape(z_score_label)}&sigma;</span>"
                    ),
                    "<div class='analytics-light-tape-zmeta'>",
                    (
                        ""
                        if signal_label is None
                        else f"<span class='analytics-light-tape-zmeta-line analytics-light-tape-zmeta-line-{_signal_tone(str(signal_label))}'>"
                        f"{escape(str(signal_label))}</span>"
                    ),
                    "</div>",
                    "</div>",
                ]
            )

        items.append(
            "".join(
                [
                    "<div class='analytics-light-tape-item'>",
                    "<div class='analytics-light-tape-eyebrow'>",
                    "<span class='analytics-light-tape-dot'></span>",
                    f"<span class='analytics-light-tape-label'>{escape(label)}</span>",
                    "</div>",
                    (
                        "<div class='analytics-light-tape-main-row'>"
                        f"<div class='analytics-light-tape-main'>{escape(_format_metric_value(key, current_value))}</div>"
                        f"{z_score_markup}"
                        "</div>"
                    ),
                    f"<div class='analytics-light-tape-sub'>{escape(delta)}</div>",
                    "</div>",
                ]
            )
        )

    st.markdown(
        "<div class='analytics-light-tape'>"
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_market_tape(records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    items: list[str] = []

    for metric in _build_market_kpi_definitions():
        metric_key = metric["key"]
        current_value = _safe_float(latest_record, metric_key)
        tone = "neutral"

        if metric_key == "last_price":
            previous_value = _safe_float(latest_record, "previous_close")
            delta = _format_metric_delta(metric_key, current_value, previous_value)
            if current_value is not None and previous_value is not None:
                tone = "positive" if current_value >= previous_value else "negative"

            daily_change_percent = _safe_float(latest_record, "daily_change_percent")
            percent_markup = ""
            if daily_change_percent is not None:
                percent_value = daily_change_percent / 100
                percent_tone = "positive" if percent_value >= 0 else "negative"
                percent_markup = (
                    f"<span class='analytics-market-tape-inline-percent analytics-market-tape-inline-percent-{percent_tone}'>"
                    f"({escape(_format_metric_value('daily_change_percent', daily_change_percent))})</span>"
                )

            delta_markup = "".join(
                [
                    f"<span>{escape(delta or 'No prior point')}</span>",
                    percent_markup,
                ]
            )

            items.append(
                "".join(
                    [
                        f"<div class='analytics-market-tape-item analytics-market-tape-item-{tone}'>",
                        "<div class='analytics-market-tape-eyebrow'>",
                        f"<span class='analytics-market-tape-label'>{escape(metric['label'])}</span>",
                        "</div>",
                        f"<div class='analytics-market-tape-main'>{escape(_format_metric_value(metric_key, current_value))}</div>",
                        f"<div class='analytics-market-tape-sub analytics-market-tape-sub-inline'>{delta_markup}</div>",
                        "</div>",
                    ]
                )
            )
            continue

        if metric_key in {"traded_volume", "traded_value"}:
            previous_value = _safe_float(previous_record, metric_key) if previous_record else None
            delta = _format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "spread":
            previous_value = _safe_float(previous_record, metric_key) if previous_record else None
            delta = _format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "best_prices":
            best_bid_price = _safe_float(latest_record, "best_bid_price")
            best_ask_price = _safe_float(latest_record, "best_ask_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor compra</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(best_bid_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor venta</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(best_ask_price))}</div>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
            continue
        elif metric_key == "price_range":
            high_price = _safe_float(latest_record, "high_price")
            low_price = _safe_float(latest_record, "low_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio maximo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(high_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio minimo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(low_price))}</div>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
            continue
        else:
            delta = None

        items.append(
            "".join(
                [
                    f"<div class='analytics-market-tape-item analytics-market-tape-item-{tone}'>",
                    "<div class='analytics-market-tape-eyebrow'>",
                    f"<span class='analytics-market-tape-label'>{escape(metric['label'])}</span>",
                    "</div>",
                    f"<div class='analytics-market-tape-main'>{escape(_format_metric_value(metric['key'], current_value))}</div>",
                    f"<div class='analytics-market-tape-sub'>{escape(delta or 'No prior point')}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(
        "<div class='analytics-market-tape'>"
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_market_ai_recommendation(payload: dict) -> None:
    recommendation = payload.get("market_ai_recommendation")
    if not isinstance(recommendation, dict) or not recommendation:
        return

    summary = str(recommendation.get("recommendation_summary") or "").strip()
    if not summary:
        return

    status = str(recommendation.get("recommendation_status") or "placeholder").strip().lower()
    triggered_rules = [
        str(rule).strip()
        for rule in recommendation.get("triggered_rules", [])
        if str(rule).strip()
    ]
    status_label = {
        "generated": "AI generated",
        "failed": "AI failed",
        "placeholder": "AI placeholder",
    }.get(status, "AI signal")
    rules_label = ", ".join(triggered_rules) if triggered_rules else "No rules"

    st.markdown(
        (
            "<div class='analytics-recommendation-strip'>"
            "<div class='analytics-recommendation-strip-header'>"
            f"<span class='analytics-recommendation-strip-badge'>{escape(status_label)}</span>"
            f"<span class='analytics-recommendation-strip-rules'>{escape(rules_label)}</span>"
            "</div>"
            f"<div class='analytics-recommendation-strip-body'>{escape(summary)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_kpis(symbol_record_groups: list[tuple[str, dict, list[dict]]]) -> None:
    for symbol, payload, records in symbol_record_groups:
        _render_microstructure_tape(symbol, payload, records)
        _render_market_tape(records)
        _render_market_ai_recommendation(payload)
        st.markdown("<div class='analytics-kpi-row-spacer'></div>", unsafe_allow_html=True)


def _render_summary_line(summary: dict[str, str]) -> None:
    current_time = now_in_bogota()
    refresh_reference = (
        st.session_state.get("analytics_last_manual_refresh")
        or st.session_state.get("analytics_session_loaded_at")
        or current_time
    )
    refresh_age_seconds = max(int((current_time - refresh_reference).total_seconds()), 0)
    refresh_tone = _refresh_tone(refresh_age_seconds)
    trigger_reason = _format_trigger_reason(summary.get("trigger_reason"))
    latest_captured_at = str(summary.get("latest_captured_at") or "").strip()
    sample_age_seconds = None
    if latest_captured_at:
        latest_timestamp = datetime.fromisoformat(latest_captured_at)
        if latest_timestamp.tzinfo is None:
            latest_timestamp = latest_timestamp.replace(tzinfo=BOGOTA_TIMEZONE)
        latest_timestamp = latest_timestamp.astimezone(BOGOTA_TIMEZONE)
        sample_age_seconds = max(int((current_time - latest_timestamp).total_seconds()), 0)
    summary_parts = [
        f":green[:material/event_available: **Desde**] **{summary['from_timestamp']}**",
        f":green[:material/flag: **Hasta**] **{summary['to_timestamp']}**",
        f":green[:material/timer: **TW**] **{summary['tw_seconds']:,}s**",
    ]
    if trigger_reason is not None:
        summary_parts.append(f":green[:material/rss_feed: **Feed**] **{trigger_reason}**")
    if sample_age_seconds is not None:
        sample_tone = _feed_age_tone(sample_age_seconds)
        summary_parts.append(
            f":{sample_tone}[:material/av_timer: **Lag**] **{_format_elapsed_seconds(sample_age_seconds)}**"
        )
    summary_parts.append(
        f":{refresh_tone}[:material/history: **Last Refresh**] **{_format_elapsed_seconds(refresh_age_seconds)}**"
    )
    st.markdown(
        "  |  ".join(summary_parts),
        text_alignment="right",
    )


@st.fragment(run_every=1)
def _render_summary_line_fragment() -> None:
    summary = st.session_state.get("analytics_summary")
    if not isinstance(summary, dict) or not summary:
        return
    current_time = now_in_bogota()
    refresh_reference = (
        st.session_state.get("analytics_last_manual_refresh")
        or st.session_state.get("analytics_session_loaded_at")
        or current_time
    )
    refresh_age_seconds = max(int((current_time - refresh_reference).total_seconds()), 0)
    if refresh_age_seconds >= 300:
        _refresh_recent_snapshots_cache()
        st.rerun()
    _render_summary_line(summary)


def _build_depth_chart(depth_history: pd.DataFrame, side: str, metric: str) -> alt.Chart:
    side_frame = depth_history[depth_history["side"] == side].copy()
    legend = alt.Legend(orient="bottom", direction="horizontal", title=None, columns=5)
    color_encoding = alt.Color(
        "level_label:N",
        sort=[f"Nivel {level}" for level in range(1, 6)],
        legend=legend,
    )
    metric_config = {
        "quantity": {
            "title": f"{side} Volume",
            "subtitle": f"Visible size across the top 5 {side.lower()} levels.",
            "y_field": "quantity:Q",
            "y_title": "Volume",
        },
    }[metric]
    tooltip = [
        alt.Tooltip("captured_at:T", title="Timestamp", format="%d-%m-%Y %H:%M"),
        alt.Tooltip("level_label:N", title="Level"),
        alt.Tooltip("price:Q", title="Price", format=",.2f"),
        alt.Tooltip("quantity:Q", title="Volume", format=",.0f"),
    ]

    return (
        alt.Chart(side_frame)
        .mark_line(point=True)
        .encode(
            x=alt.X("captured_at:T", title="Time"),
            y=alt.Y(metric_config["y_field"], title=metric_config["y_title"], scale=alt.Scale(zero=False)),
            color=color_encoding,
            tooltip=tooltip,
        )
        .properties(
            height=410,
            title=alt.TitleParams(
                text=metric_config["title"],
                subtitle=metric_config["subtitle"],
                anchor="start",
            ),
        )
    )


st.session_state.setdefault("analytics_last_manual_refresh", None)
st.session_state.setdefault("analytics_session_loaded_at", now_in_bogota())
st.session_state.setdefault("analytics_summary", {})

st.markdown(
    """
    <style>
    .analytics-kpi-row-spacer {
        height: 0.24rem;
    }
    .analytics-light-tape {
        min-height: 42px;
        border-radius: 10px;
        background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 100%);
        border: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        align-items: stretch;
        overflow: hidden;
        margin-bottom: 6px;
    }
    .analytics-light-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.3rem 0.46rem 0.26rem 0.46rem;
        border-right: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-light-tape-item:last-child {
        border-right: none;
    }
    .analytics-light-tape-symbol {
        max-width: 120px;
        align-items: center;
        justify-content: center;
    }
    .analytics-light-tape-eyebrow {
        display: flex;
        align-items: center;
        gap: 0.22rem;
        margin-bottom: 0.06rem;
    }
    .analytics-light-tape-dot {
        width: 0.28rem;
        height: 0.28rem;
        border-radius: 999px;
        background: #02fb7e;
        flex-shrink: 0;
    }
    .analytics-light-tape-label {
        color: #082114;
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-light-tape-main {
        color: #000000;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 0.94;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.04rem;
    }
    .analytics-light-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.28rem;
        min-width: 0;
    }
    .analytics-light-tape-zscore {
        color: rgba(8, 33, 20, 0.68);
        font-size: 0.52rem;
        font-weight: 600;
        line-height: 1.0;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-light-tape-zscore-stack {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.04rem;
        min-width: 0;
        flex-shrink: 0;
    }
    .analytics-light-tape-zmeta {
        display: flex;
        flex-direction: column;
        gap: 0.01rem;
        min-width: 0;
    }
    .analytics-light-tape-zmeta-line {
        color: rgba(8, 33, 20, 0.54);
        font-size: 0.4rem;
        font-weight: 400;
        line-height: 1.05;
        letter-spacing: 0.01em;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        width: fit-content;
        padding: 0.06rem 0.28rem;
        border-radius: 999px;
        background: rgba(8, 33, 20, 0.06);
    }
    .analytics-light-tape-zmeta-line-green {
        color: #0b6b35;
        background: rgba(2, 251, 126, 0.18);
    }
    .analytics-light-tape-zmeta-line-red {
        color: #b42318;
        background: rgba(255, 95, 87, 0.18);
    }
    .analytics-light-tape-zmeta-line-blue {
        color: #155eef;
        background: rgba(21, 94, 239, 0.14);
    }
    .analytics-light-tape-zmeta-line-gray {
        color: #667085;
        background: rgba(102, 112, 133, 0.12);
    }
    .analytics-light-tape-sub {
        color: rgba(8, 33, 20, 0.62);
        font-size: 0.5rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape {
        min-height: 42px;
        margin-top: 6px;
        border-radius: 10px;
        background: linear-gradient(180deg, #0d1117 0%, #11161d 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        display: flex;
        align-items: stretch;
        overflow: hidden;
    }
    .analytics-market-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.32rem 0.48rem 0.28rem 0.48rem;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-market-tape-item:last-child {
        border-right: none;
    }
    .analytics-market-tape-eyebrow {
        display: flex;
        align-items: center;
        margin-bottom: 0.06rem;
    }
    .analytics-market-tape-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.34rem;
        min-width: 0;
    }
    .analytics-market-tape-main {
        color: #f8fafc;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 0.92;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.05rem;
    }
    .analytics-market-tape-inline-percent {
        font-size: 0.54rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-market-tape-inline-percent-positive {
        color: #02fb7e;
    }
    .analytics-market-tape-inline-percent-negative {
        color: #ff5f57;
    }
    .analytics-market-tape-sub {
        color: rgba(255, 255, 255, 0.58);
        font-size: 0.46rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape-sub-inline {
        display: inline-flex;
        align-items: baseline;
        gap: 0.28rem;
        white-space: nowrap;
    }
    .analytics-market-tape-item-positive .analytics-market-tape-main,
    .analytics-market-tape-item-positive .analytics-market-tape-sub {
        color: #02fb7e;
    }
    .analytics-market-tape-item-negative .analytics-market-tape-main,
    .analytics-market-tape-item-negative .analytics-market-tape-sub {
        color: #ff5f57;
    }
    .analytics-market-tape-item-market .analytics-market-tape-main {
        color: #8ab4f8;
    }
    .analytics-market-tape-item-paired {
        gap: 0.18rem;
    }
    .analytics-market-tape-pair {
        display: flex;
        flex-direction: column;
        gap: 0.02rem;
    }
    .analytics-market-tape-pair-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.45rem;
        font-weight: 600;
        line-height: 1;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-pair-value {
        color: #8ab4f8;
        font-size: 0.66rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-recommendation-strip {
        margin-top: 6px;
        padding: 0.55rem 0.75rem;
        border-radius: 10px;
        border: 1px solid rgba(8, 33, 20, 0.08);
        background: linear-gradient(180deg, #fbfffd 0%, #f4fbf7 100%);
    }
    .analytics-recommendation-strip-header {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin-bottom: 0.14rem;
        flex-wrap: wrap;
    }
    .analytics-recommendation-strip-badge {
        font-size: 0.48rem;
        line-height: 1;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #0b6b35;
        background: rgba(2, 251, 126, 0.14);
        border-radius: 999px;
        padding: 0.18rem 0.42rem;
    }
    .analytics-recommendation-strip-rules {
        font-size: 0.52rem;
        color: rgba(8, 33, 20, 0.62);
        font-weight: 500;
    }
    .analytics-recommendation-strip-body {
        font-size: 0.7rem;
        line-height: 1.4;
        color: #082114;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

days = 7

try:
    with st.spinner("Consultando simbolos disponibles..."):
        catalog_response = _load_analytics_catalog(days)

    catalog_result = catalog_response.get("result", {})
    symbols = [
        str(symbol).strip().upper()
        for symbol in catalog_result.get("symbols", [])
        if str(symbol).strip()
    ]

    if not symbols:
        st.info("No se encontraron snapshots disponibles para construir filtros operativos.")
    else:
        filter_columns = st.columns([2.2, 0.7], gap="medium")
        with filter_columns[0]:
            st.markdown("*Symbols*")
            selected_symbols = st.multiselect(
                "Symbols",
                options=symbols,
                default=symbols,
                help="Select one or more symbols for the analytics view.",
                label_visibility="collapsed",
            )
        with filter_columns[1]:
            st.markdown("*Refresh*")
            refresh_requested = st.button(
                "Refresh query",
                icon=":material/refresh:",
                type="secondary",
                width="stretch",
            )

        if refresh_requested:
            _refresh_recent_snapshots_cache()
            st.toast("Consulta actualizada contra API Gateway.")

        analytics_payloads: list[dict] = []
        for selected_symbol in selected_symbols:
            analytics_response = _load_analytics_snapshot(selected_symbol)
            analytics_result = analytics_response.get("result", {})
            if analytics_result.get("current_snapshot"):
                analytics_payloads.append(analytics_result)

        filtered_records: list[dict] = []
        for payload in analytics_payloads:
            for record in payload.get("snapshots", []):
                if isinstance(record, dict):
                    filtered_records.append(record)

        filtered_records.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)
        summary = build_analytics_summary(
            filtered_records,
            current_time=now_in_bogota(),
        )

        st.session_state["analytics_summary"] = summary
        _render_summary_line_fragment()

        if not selected_symbols:
            st.info("Selecciona al menos un simbolo para cargar la vista analitica.")
        elif not analytics_payloads:
            st.info("No hay snapshots disponibles para los simbolos elegidos.")
        else:
            symbol_record_groups = _build_symbol_analytics_groups(analytics_payloads, selected_symbols)
            _render_kpis(symbol_record_groups)
            if len(selected_symbols) != 1:
                st.info("Selecciona un solo simbolo para inspeccionar las curvas de Bid / Ask volume.")
            else:
                depth_history = pd.DataFrame(build_depth_history_rows(filtered_records))
                if not depth_history.empty:
                    depth_history["captured_at"] = pd.to_datetime(depth_history["captured_at"], errors="coerce")
                    depth_history = depth_history.dropna(subset=["captured_at"])

                    if not depth_history.empty:
                        st.altair_chart(_build_depth_chart(depth_history, "Bid", "quantity"), width="stretch")
                        st.altair_chart(_build_depth_chart(depth_history, "Ask", "quantity"), width="stretch")
                    else:
                        st.info(
                            "Los snapshots consultados no trajeron timestamps validos para construir las series de profundidad."
                        )
                else:
                    st.info(
                        "Los snapshots consultados no trajeron `bid_levels` y `ask_levels` en un formato graficable."
                    )
except (BackendConfigurationError, ApiGatewayClientError) as exc:
    st.error("No fue posible consultar los snapshots recientes.")
    st.caption("Referencia interna: `analytics_recent_snapshots`")
    st.write(
        "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
        "o confirma que el API Gateway y la Lambda esten desplegados."
    )
    with st.expander("Detalle tecnico"):
        st.code(str(exc))
