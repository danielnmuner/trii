from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from analytics_utils import (
    SymbolRecordGroup,
    build_market_kpi_definitions,
    compute_cumulative_vwap,
    feed_age_tone,
    format_cop_price,
    format_elapsed_seconds,
    format_metric_delta,
    format_metric_delta_with_relative,
    format_metric_value,
    format_trigger_reason,
    refresh_tone,
    resolve_symbol_sample_count,
    safe_float,
    sample_count_label,
    signal_tone,
)
from trii_ingestion.services import build_historic_z_score_context, now_in_bogota


def render_microstructure_tape(symbol: str, payload: dict, records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    current_stats = payload.get("current_stats", {})
    symbol_sample_count = resolve_symbol_sample_count(current_stats)
    symbol_sample_count_markup = (
        ""
        if symbol_sample_count <= 0
        else f"<div class='analytics-light-tape-sub'>{escape(sample_count_label(symbol_sample_count) or '')}</div>"
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
        current_value = safe_float(latest_record, key)
        previous_value = safe_float(previous_record, key) if previous_record else None
        delta = format_metric_delta_with_relative(key, current_value, previous_value) or "No prior point"
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
                        else f"<span class='analytics-light-tape-zmeta-line analytics-light-tape-zmeta-line-{signal_tone(str(signal_label))}'>"
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
                        f"<div class='analytics-light-tape-main'>{escape(format_metric_value(key, current_value))}</div>"
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


def render_market_tape(records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    items: list[str] = []

    for metric in build_market_kpi_definitions():
        metric_key = metric["key"]
        current_value = (
            compute_cumulative_vwap(latest_record)
            if metric_key == "vwap_cumulative"
            else safe_float(latest_record, metric_key)
        )
        tone = "neutral"

        if metric_key == "last_price":
            previous_value = safe_float(latest_record, "previous_close")
            delta = format_metric_delta(metric_key, current_value, previous_value)
            if current_value is not None and previous_value is not None:
                tone = "positive" if current_value >= previous_value else "negative"

            daily_change_percent = safe_float(latest_record, "daily_change_percent")
            percent_markup = ""
            if daily_change_percent is not None:
                percent_value = daily_change_percent / 100
                percent_tone = "positive" if percent_value >= 0 else "negative"
                percent_markup = (
                    f"<span class='analytics-market-tape-inline-percent analytics-market-tape-inline-percent-{percent_tone}'>"
                    f"({escape(format_metric_value('daily_change_percent', daily_change_percent))})</span>"
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
                        f"<div class='analytics-market-tape-main'>{escape(format_metric_value(metric_key, current_value))}</div>",
                        f"<div class='analytics-market-tape-sub analytics-market-tape-sub-inline'>{delta_markup}</div>",
                        "</div>",
                    ]
                )
            )
            continue

        if metric_key in {"traded_volume", "traded_value"}:
            previous_value = safe_float(previous_record, metric_key) if previous_record else None
            delta = format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "vwap_cumulative":
            previous_value = compute_cumulative_vwap(previous_record)
            delta = format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "spread":
            previous_value = safe_float(previous_record, metric_key) if previous_record else None
            delta = format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "best_prices":
            best_bid_price = safe_float(latest_record, "best_bid_price")
            best_ask_price = safe_float(latest_record, "best_ask_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor compra</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(format_cop_price(best_bid_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor venta</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(format_cop_price(best_ask_price))}</div>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
            continue
        elif metric_key == "price_range":
            high_price = safe_float(latest_record, "high_price")
            low_price = safe_float(latest_record, "low_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio maximo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(format_cop_price(high_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio minimo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(format_cop_price(low_price))}</div>",
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
                    f"<div class='analytics-market-tape-main'>{escape(format_metric_value(metric['key'], current_value))}</div>",
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


def render_kpis(symbol_record_groups: list[SymbolRecordGroup]) -> None:
    for symbol, payload, records in symbol_record_groups:
        render_microstructure_tape(symbol, payload, records)
        render_market_tape(records)
        st.markdown("<div class='analytics-kpi-row-spacer'></div>", unsafe_allow_html=True)


def render_summary_line(summary: dict[str, str]) -> None:
    current_time = now_in_bogota()
    refresh_reference = (
        st.session_state.get("analytics_last_manual_refresh")
        or st.session_state.get("analytics_session_loaded_at")
        or current_time
    )
    refresh_age_seconds = max(int((current_time - refresh_reference).total_seconds()), 0)
    current_refresh_tone = refresh_tone(refresh_age_seconds)
    trigger_reason = format_trigger_reason(summary.get("trigger_reason"))
    latest_captured_at = str(summary.get("latest_captured_at") or "").strip()
    sample_age_seconds = None
    if latest_captured_at:
        try:
            latest_timestamp = datetime.fromisoformat(latest_captured_at)
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=current_time.tzinfo)
            latest_timestamp = latest_timestamp.astimezone(current_time.tzinfo)
            sample_age_seconds = max(int((current_time - latest_timestamp).total_seconds()), 0)
        except ValueError:
            sample_age_seconds = None
    summary_parts = [
        f":green[:material/event_available: **Desde**] **{summary['from_timestamp']}**",
        f":green[:material/flag: **Hasta**] **{summary['to_timestamp']}**",
        f":green[:material/timer: **TW**] **{summary['tw_seconds']:,}s**",
    ]
    if trigger_reason is not None:
        summary_parts.append(f":green[:material/rss_feed: **Feed**] **{trigger_reason}**")
    if sample_age_seconds is not None:
        sample_tone = feed_age_tone(sample_age_seconds)
        summary_parts.append(
            f":{sample_tone}[:material/av_timer: **Lag**] **{format_elapsed_seconds(sample_age_seconds)}**"
        )
    summary_parts.append(
        f":{current_refresh_tone}[:material/history: **Last Refresh**] **{format_elapsed_seconds(refresh_age_seconds)}**"
    )
    st.markdown(
        "  |  ".join(summary_parts),
        text_alignment="right",
    )
