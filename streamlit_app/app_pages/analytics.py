from __future__ import annotations

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

    if metric_key in {"spread", "bid_depth_total_5", "ask_depth_total_5"}:
        return f"{value:,.0f}"
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


def _build_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "spread", "label": "Spread"},
        {"key": "spread_bps", "label": "Spread bps"},
        {"key": "mid_price", "label": "Mid price"},
        {"key": "microprice", "label": "Microprice"},
        {"key": "obi_l1", "label": "OBI L1"},
        {"key": "obi_top_5", "label": "OBI top 5"},
        {"key": "bid_depth_total_5", "label": "Bid depth 5"},
        {"key": "ask_depth_total_5", "label": "Ask depth 5"},
        {"key": "book_pressure_ratio", "label": "Pressure ratio"},
        {
            "key": "depth_weighted_microprice_deviation",
            "label": "Microprice dev",
        },
    ]


def _render_kpi_card(*, label: str, value: str, delta: str | None) -> None:
    delta_text = delta if delta is not None else "No prior point"
    delta_class = "analytics-kpi-delta analytics-kpi-delta-empty" if delta is None else "analytics-kpi-delta"
    st.markdown(
        f"""
        <div class="analytics-kpi-card">
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


def _render_kpis(records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    kpi_definitions = _build_kpi_definitions()

    for row_start in range(0, len(kpi_definitions), 5):
        columns = st.columns(5, gap="medium")
        for column, metric in zip(columns, kpi_definitions[row_start : row_start + 5], strict=False):
            current_value = _safe_float(latest_record, metric["key"])
            previous_value = _safe_float(previous_record, metric["key"]) if previous_record else None
            with column:
                _render_kpi_card(
                    label=metric["label"],
                    value=_format_metric_value(metric["key"], current_value),
                    delta=_format_metric_delta(metric["key"], current_value, previous_value),
                )
        if row_start + 5 < len(kpi_definitions):
            st.markdown("<div class='analytics-kpi-row-spacer'></div>", unsafe_allow_html=True)


@st.fragment(run_every="1s")
def _render_live_status() -> None:
    current_time = now_in_bogota()
    st.markdown(
        f":green[:material/schedule: **Hora actual**] **{current_time.strftime('%d-%m-%Y %H:%M:%S')}**",
        text_alignment="right",
    )


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
        "price": {
            "title": f"{side} Price Levels",
            "subtitle": f"Shows visible {side.lower()} prices across the top 5 levels.",
            "y_field": "price:Q",
            "y_title": "Price",
        },
        "quantity": {
            "title": f"{side} Size Levels",
            "subtitle": f"Tracks visible {side.lower()} size across the top 5 levels.",
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
            height=340,
            title=alt.TitleParams(
                text=metric_config["title"],
                subtitle=metric_config["subtitle"],
                anchor="start",
            ),
        )
    )

st.session_state.setdefault("analytics_last_manual_refresh", None)

st.markdown(
    """
    <style>
    .analytics-kpi-card {
        background: #ffffff;
        border: 1px solid rgba(8, 33, 20, 0.08);
        border-radius: 18px;
        padding: 0.78rem 0.9rem 0.72rem 0.9rem;
        min-height: 92px;
        box-shadow: 0 1px 2px rgba(8, 33, 20, 0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .analytics-kpi-header {
        display: flex;
        align-items: center;
        gap: 0.42rem;
        margin-bottom: 0.34rem;
    }
    .analytics-kpi-accent {
        width: 0.46rem;
        height: 0.46rem;
        border-radius: 999px;
        background: #02fb7e;
        box-shadow: 0 0 0 4px rgba(2, 251, 126, 0.14);
        flex-shrink: 0;
    }
    .analytics-kpi-label {
        color: #082114;
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        line-height: 1.15;
    }
    .analytics-kpi-value {
        color: #000000;
        font-size: 1.52rem;
        font-weight: 700;
        line-height: 0.96;
        letter-spacing: -0.02em;
        margin-bottom: 0.34rem;
        word-break: break-word;
    }
    .analytics-kpi-delta {
        color: #082114;
        display: flex;
        align-items: baseline;
        gap: 0.28rem;
        font-size: 0.82rem;
        font-weight: 300;
        line-height: 1.15;
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
        height: 0.5rem;
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

        with st.sidebar:
            with st.container(border=True):
                st.subheader("Filtros")
                st.caption("*Estos controles actualizan toda la vista analitica.*")
                selected_window = st.selectbox(
                    "Ventana de tiempo",
                    options=time_window_options,
                    index=time_window_options.index("6h"),
                    help=get_time_window_help_text("6h"),
                )
                selected_symbol = st.selectbox(
                    "Simbolo",
                    options=symbols,
                    index=0,
                    help="La vista analitica solo puede consultar una especie a la vez.",
                )
                refresh_requested = st.button(
                    "Refrescar consulta",
                    icon=":material/refresh:",
                    type="secondary",
                    width="stretch",
                )

        if refresh_requested:
            _refresh_recent_snapshots_cache()
            st.toast("Consulta actualizada contra API Gateway.")

        filtered_records = filter_records(
            all_records,
            symbol=selected_symbol,
            window_label=selected_window,
            current_time=current_time,
        )
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
        _render_live_status()

        if not filtered_records:
            st.info("No hay snapshots para ese simbolo dentro de la ventana seleccionada.")
        else:
            _render_kpis(filtered_records)

            depth_history = pd.DataFrame(build_depth_history_rows(filtered_records))
            if not depth_history.empty:
                depth_history["captured_at"] = pd.to_datetime(depth_history["captured_at"], errors="coerce")
                depth_history = depth_history.dropna(subset=["captured_at"])

                if not depth_history.empty:
                    st.subheader("Depth charts")
                    st.caption(
                        "*These charts separate price and visible size so the operator can read structure first and execution pressure second without mixing scales.*"
                    )
                    top_row = st.columns(2, gap="large")
                    bottom_row = st.columns(2, gap="large")
                    with top_row[0]:
                        st.altair_chart(_build_depth_chart(depth_history, "Bid", "price"), width="stretch")
                    with top_row[1]:
                        st.altair_chart(_build_depth_chart(depth_history, "Ask", "price"), width="stretch")
                    with bottom_row[0]:
                        st.altair_chart(_build_depth_chart(depth_history, "Bid", "quantity"), width="stretch")
                    with bottom_row[1]:
                        st.altair_chart(_build_depth_chart(depth_history, "Ask", "quantity"), width="stretch")
                else:
                    st.info("Los snapshots consultados no trajeron timestamps validos para construir las series de profundidad.")
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
