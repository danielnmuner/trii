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
    extract_symbols,
    filter_records,
    get_time_window_help_text,
    get_time_window_labels,
    now_in_bogota,
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_recent_snapshots(days: int) -> dict:
    client = get_backend_client()
    return client.get_recent_snapshots(days=days)


def _refresh_recent_snapshots_cache() -> None:
    _load_recent_snapshots.clear()
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
        return f"{value:,.2f}%"
    if metric_key in {"mid_price", "microprice"}:
        return f"{value:,.2f}"
    if metric_key == "spread_bps":
        return f"{value:,.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{value:,.2f}"
    if metric_key == "depth_weighted_microprice_deviation":
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def _format_metric_delta(metric_key: str, current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None

    delta = current - previous
    if metric_key == "spread_bps":
        return f"{delta:+.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{delta:+.2f}"
    return f"{delta:+,.2f}"


def _build_sidebar_market_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "last_price", "label": "Ultimo precio"},
        {"key": "daily_change_amount", "label": "Cambio COP"},
        {"key": "daily_change_percent", "label": "Cambio %"},
        {"key": "traded_volume", "label": "Volumen negociado"},
        {"key": "traded_value", "label": "Valor negociado"},
    ]


def _build_microstructure_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "spread", "label": "Spread"},
        {"key": "spread_bps", "label": "Spread bps"},
        {"key": "mid_price", "label": "Mid price"},
        {"key": "microprice", "label": "Microprice"},
        {"key": "obi_l1", "label": "OBI L1"},
        {"key": "obi_top_5", "label": "OBI top 5"},
    ]


def _render_kpi_card(
    *,
    label: str,
    value: str,
    delta: str | None,
    tone: str = "green",
    size: str = "default",
) -> None:
    delta_text = delta if delta is not None else "No prior point"
    delta_class = "analytics-kpi-delta analytics-kpi-delta-empty" if delta is None else "analytics-kpi-delta"
    tone_class = f"analytics-kpi-card analytics-kpi-card-{tone} analytics-kpi-card-{size}"
    st.markdown(
        f"""
        <div class="{tone_class}">
            <div class="analytics-kpi-header">
                <span class="analytics-kpi-accent"></span>
                <div class="analytics-kpi-label">{label}</div>
            </div>
            <div class="analytics-kpi-value">{value}</div>
            <div class="{delta_class}">
                <span class="analytics-kpi-delta-prefix">vs prev</span>
                <span class="analytics-kpi-delta-value">{delta_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_symbol_record_groups(records: list[dict], selected_symbols: list[str]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = {symbol: [] for symbol in selected_symbols}
    for record in records:
        symbol = str(record.get("symbol", "")).strip().upper()
        if symbol in grouped:
            grouped[symbol].append(record)

    return [(symbol, grouped[symbol]) for symbol in selected_symbols if grouped[symbol]]


def _render_symbol_chip(symbol: str) -> None:
    st.markdown(f"<div class='analytics-symbol-chip'>{symbol}</div>", unsafe_allow_html=True)


def _render_market_tape(records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    items: list[str] = []

    for metric in _build_sidebar_market_kpi_definitions():
        current_value = _safe_float(latest_record, metric["key"])
        tone = "neutral"
        if metric["key"] == "last_price":
            previous_value = _safe_float(latest_record, "previous_close")
            delta = _format_metric_delta(metric["key"], current_value, previous_value)
            if current_value is not None and previous_value is not None:
                tone = "positive" if current_value >= previous_value else "negative"
        elif metric["key"] == "daily_change_percent":
            daily_change_amount = _safe_float(latest_record, "daily_change_amount")
            delta = None if current_value is None else f"{daily_change_amount or 0:+,.2f} COP"
            if current_value is not None:
                tone = "positive" if current_value >= 0 else "negative"
        elif metric["key"] == "daily_change_amount":
            delta = str(latest_record.get("daily_change_direction", "")).strip().lower()
            if delta == "up":
                delta = "sesgo alcista"
                tone = "positive"
            elif delta == "down":
                delta = "sesgo bajista"
                tone = "negative"
            else:
                delta = "sesgo neutral"
                tone = "neutral"
        else:
            previous_value = _safe_float(previous_record, metric["key"]) if previous_record else None
            delta = _format_metric_delta(metric["key"], current_value, previous_value)
            tone = "market"

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


def _render_kpis(symbol_record_groups: list[tuple[str, list[dict]]]) -> None:
    microstructure_kpis = _build_microstructure_kpi_definitions()

    ordered_microstructure = [
        "obi_l1",
        "obi_top_5",
        "spread",
        "spread_bps",
        "mid_price",
        "microprice",
    ]
    definitions_by_key = {metric["key"]: metric for metric in microstructure_kpis}
    display_metrics = [definitions_by_key[key] for key in ordered_microstructure]

    for symbol, records in symbol_record_groups:
        latest_record = records[0]
        previous_record = records[1] if len(records) > 1 else None
        columns = st.columns([0.78, 1, 1, 1, 1, 1, 1], gap="small")
        with columns[0]:
            _render_symbol_chip(symbol)
        for column, metric in zip(columns[1:], display_metrics, strict=False):
            current_value = _safe_float(latest_record, metric["key"])
            previous_value = _safe_float(previous_record, metric["key"]) if previous_record else None
            with column:
                _render_kpi_card(
                    label=metric["label"],
                    value=_format_metric_value(metric["key"], current_value),
                    delta=_format_metric_delta(metric["key"], current_value, previous_value),
                )

        tape_columns = st.columns([0.78, 6], gap="small")
        with tape_columns[0]:
            st.markdown("<div class='analytics-symbol-spacer'></div>", unsafe_allow_html=True)
        with tape_columns[1]:
            _render_market_tape(records)
        st.markdown("<div class='analytics-kpi-row-spacer'></div>", unsafe_allow_html=True)


def _render_summary_line(summary: dict[str, str]) -> None:
    st.markdown(
        (
            f":green[:material/database: **Registros**] **{summary['record_count']}**"
            f"  |  :green[:material/event_available: **Desde**] **{summary['from_timestamp']}**"
            f"  |  :green[:material/flag: **Hasta**] **{summary['to_timestamp']}**"
        ),
        text_alignment="right",
    )


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


def _build_activity_table(records: list[dict]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for record in records:
        rows.append(
            {
                "Hora": str(record.get("captured_at", "")),
                "Simbolo": str(record.get("symbol", "")),
                "OBI L1": _safe_float(record, "obi_l1"),
                "OBI Top 5": _safe_float(record, "obi_top_5"),
                "Spread": _safe_float(record, "spread"),
            }
        )

    return pd.DataFrame(rows)


def _render_activity_table(records: list[dict]) -> None:
    frame = _build_activity_table(records)
    if frame.empty:
        st.info("No hay registros disponibles para construir la tabla operativa.")
        return

    display_frame = frame.copy()
    display_frame["Hora"] = pd.to_datetime(display_frame["Hora"], errors="coerce").dt.strftime("%d-%m-%Y %H:%M")
    display_frame["Hora"] = display_frame["Hora"].fillna("n/a")

    styled = (
        display_frame.style.format(
            {
                "OBI L1": "{:,.2f}",
                "OBI Top 5": "{:,.2f}",
                "Spread": "{:,.0f}",
            },
            na_rep="n/a",
        )
    )

    st.dataframe(styled, width="stretch", hide_index=True)
st.session_state.setdefault("analytics_last_manual_refresh", None)

st.markdown(
    """
    <style>
    .analytics-kpi-card {
        background: #ffffff;
        border: 1px solid rgba(8, 33, 20, 0.08);
        border-radius: 14px;
        padding: 0.42rem 0.5rem 0.38rem 0.5rem;
        min-height: 58px;
        box-shadow: 0 1px 2px rgba(8, 33, 20, 0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .analytics-kpi-card-blue {
        border-color: rgba(26, 115, 232, 0.14);
        box-shadow: 0 1px 2px rgba(26, 115, 232, 0.08);
    }
    .analytics-kpi-header {
        display: flex;
        align-items: center;
        gap: 0.28rem;
        margin-bottom: 0.12rem;
    }
    .analytics-kpi-accent {
        width: 0.34rem;
        height: 0.34rem;
        border-radius: 999px;
        background: #02fb7e;
        box-shadow: 0 0 0 3px rgba(2, 251, 126, 0.14);
        flex-shrink: 0;
    }
    .analytics-kpi-card-blue .analytics-kpi-accent {
        background: #1a73e8;
        box-shadow: 0 0 0 4px rgba(26, 115, 232, 0.14);
    }
    .analytics-kpi-label {
        color: #082114;
        font-size: 0.58rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        line-height: 1.0;
    }
    .analytics-kpi-value {
        color: #000000;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 0.95;
        letter-spacing: -0.02em;
        margin-bottom: 0.12rem;
        word-break: break-word;
    }
    .analytics-kpi-delta {
        color: #082114;
        display: flex;
        align-items: baseline;
        gap: 0.16rem;
        font-size: 0.56rem;
        font-weight: 300;
        line-height: 0.98;
        letter-spacing: -0.01em;
        opacity: 0.88;
    }
    .analytics-kpi-delta-prefix {
        color: rgba(8, 33, 20, 0.48);
        font-weight: 400;
    }
    .analytics-kpi-delta-value {
        color: #082114;
        font-weight: 300;
    }
    .analytics-kpi-delta-empty {
        color: rgba(8, 33, 20, 0.52);
    }
    .analytics-kpi-row-spacer {
        height: 0.24rem;
    }
    .analytics-symbol-chip {
        min-height: 58px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 14px;
        border: 1px solid rgba(8, 33, 20, 0.08);
        background: #ffffff;
        color: #082114;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .analytics-symbol-spacer {
        min-height: 48px;
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
    .analytics-market-tape-sub {
        color: rgba(255, 255, 255, 0.58);
        font-size: 0.46rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
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
    [data-testid="column"] .analytics-kpi-card {
        height: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

days = 7

try:
    with st.spinner("Consultando snapshots recientes..."):
        response = _load_recent_snapshots(days)

    result = response.get("result", {})
    all_records = result.get("records", [])
    symbols = extract_symbols(all_records)

    if not symbols:
        st.info("No se encontraron snapshots disponibles para construir filtros operativos.")
    else:
        time_window_options = get_time_window_labels()
        current_time = now_in_bogota()

        filter_columns = st.columns([1.05, 1.55, 0.7], gap="medium")
        with filter_columns[0]:
            st.markdown("*Time window*")
            selected_window = st.selectbox(
                "Time window",
                options=time_window_options,
                index=time_window_options.index("6h"),
                help=get_time_window_help_text("6h"),
                label_visibility="collapsed",
            )
        with filter_columns[1]:
            st.markdown("*Symbols*")
            selected_symbols = st.multiselect(
                "Symbols",
                options=symbols,
                default=symbols,
                help="Select one or more symbols for the analytics view.",
                label_visibility="collapsed",
            )
        with filter_columns[2]:
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

        filtered_records: list[dict] = []
        for selected_symbol in selected_symbols:
            filtered_records.extend(
                filter_records(
                    all_records,
                    symbol=selected_symbol,
                    window_label=selected_window,
                    current_time=current_time,
                )
            )
        filtered_records.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)
        summary = build_analytics_summary(
            filtered_records,
            window_label=selected_window,
            current_time=current_time,
        )

        last_manual_refresh = st.session_state.get("analytics_last_manual_refresh")
        if last_manual_refresh is not None:
            st.caption(
                f"*Ultima recarga manual: {last_manual_refresh.strftime('%d-%m-%Y %H:%M')} (America/Bogota).*"
            )

        _render_summary_line(summary)

        if not selected_symbols:
            st.info("Selecciona al menos un simbolo para cargar la vista analitica.")
        elif not filtered_records:
            st.info("No hay snapshots para los simbolos elegidos dentro de la ventana seleccionada.")
        else:
            symbol_record_groups = _build_symbol_record_groups(filtered_records, selected_symbols)
            _render_kpis(symbol_record_groups)
            table_tab, chart_tab = st.tabs(["Actividad reciente", "Bid / Ask volume"])

            with table_tab:
                _render_activity_table(filtered_records)

            with chart_tab:
                if len(selected_symbols) != 1:
                    st.info("Selecciona un solo simbolo para inspeccionar las curvas de Bid / Ask volume.")
                else:
                    depth_history = pd.DataFrame(build_depth_history_rows(filtered_records))
                    if not depth_history.empty:
                        depth_history["captured_at"] = pd.to_datetime(depth_history["captured_at"], errors="coerce")
                        depth_history = depth_history.dropna(subset=["captured_at"])

                        if not depth_history.empty:
                            bid_chart_slot = st.container()
                            ask_chart_slot = st.container()
                            with bid_chart_slot:
                                st.altair_chart(_build_depth_chart(depth_history, "Bid", "quantity"), width="stretch")
                            with ask_chart_slot:
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
