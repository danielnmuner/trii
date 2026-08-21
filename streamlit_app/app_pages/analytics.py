from __future__ import annotations
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from analytics_data import (
    load_analytics_catalog,
    load_daily_closing_snapshots,
    load_zscore_opportunities,
    refresh_analytics_core_cache,
    refresh_daily_closing_cache,
    refresh_zscore_cache,
)
from analytics_diagnostics import render_diagnostic_board
from analytics_renderers import render_kpis, render_summary_line
from analytics_styles import ANALYTICS_PAGE_STYLES
from analytics_utils import load_symbol_record_groups, normalize_records_for_table
from backend import BackendConfigurationError
from trii_ingestion.services import ApiGatewayClientError, now_in_bogota

@st.fragment
def _render_overview_fragment(selected_symbols: tuple[str, ...]) -> None:
    if not selected_symbols:
        st.info("Selecciona al menos un simbolo para cargar current snapshots e historic stats.")
        return

    with st.spinner("Consultando current snapshots e historic stats..."):
        symbol_record_groups, summary = load_symbol_record_groups(selected_symbols)

    if not symbol_record_groups:
        st.info("No hay snapshots disponibles para los simbolos elegidos.")
        return

    render_summary_line(summary)
    render_kpis(symbol_record_groups)


@st.fragment
def _render_diagnostic_fragment(selected_symbols: tuple[str, ...]) -> None:
    if not selected_symbols:
        st.info("Selecciona al menos un simbolo para abrir el diagnostico.")
        return

    with st.spinner("Consultando current snapshots e historic stats..."):
        symbol_record_groups, summary = load_symbol_record_groups(selected_symbols)

    if not symbol_record_groups:
        st.info("No hay snapshots disponibles para los simbolos elegidos.")
        return

    render_summary_line(summary)
    tactical_tab, alerts_tab = st.tabs(["Tactico", "Alertas"], on_change="rerun")
    if tactical_tab.open:
        with tactical_tab:
            render_diagnostic_board(
                symbol_record_groups,
                "execution",
                "Lectura tactica para decidir si el mercado ofrece liquidez suficiente, sesgo util en punta y una referencia de precio todavia defendible frente a la sesion.",
            )
    if alerts_tab.open:
        with alerts_tab:
            render_diagnostic_board(
                symbol_record_groups,
                "alerts",
                "Lectura defensiva para separar ruido normal de eventos que merecen revision inmediata antes de tomar una decision de corto plazo.",
            )


@st.fragment
def _render_zscore_fragment(active_symbol: str) -> None:
    control_columns = st.columns([1.2, 0.8], gap="medium")
    with control_columns[0]:
        trading_date = st.date_input(
            "Trading date",
            key="analytics_zscore_date",
        )
    with control_columns[1]:
        st.markdown("*Carga manual*")
        requested = st.button(
            "Actualizar oportunidades",
            key="analytics_zscore_refresh",
            icon=":material/refresh:",
            type="secondary",
            width="stretch",
        )

    requested_signature = {
        "symbol": active_symbol,
        "trading_date": trading_date.isoformat(),
    }
    if requested:
        st.session_state["analytics_zscore_request"] = requested_signature
        refresh_zscore_cache()

    if st.session_state.get("analytics_zscore_request") != requested_signature:
        st.info(
            "Esta vista no consulta automaticamente `trii-prod-zscore-opportunities`. Usa el boton para traer un solo dia por simbolo."
        )
        return

    with st.spinner("Consultando oportunidades z-score..."):
        response = load_zscore_opportunities(
            active_symbol,
            trading_date.isoformat(),
        )

    result = response.get("result", {})
    records = result.get("records", [])
    st.caption(
        f"`trii-prod-zscore-opportunities` | symbol `{active_symbol}` | date `{trading_date.isoformat()}` | {len(records)} registros"
    )
    if not records:
        st.info("No hay oportunidades z-score para los filtros seleccionados.")
        return

    st.dataframe(
        normalize_records_for_table(records),
        hide_index=True,
        width="stretch",
    )


@st.fragment
def _render_daily_closing_fragment(active_symbol: str) -> None:
    st.caption(
        "Consulta manual de `trii-prod-daily-closing-snapshots`. Esta vista trae el historico disponible para el simbolo seleccionado."
    )
    requested = st.button(
        "Actualizar cierres diarios",
        key="analytics_daily_closing_refresh",
        icon=":material/refresh:",
        type="secondary",
        width="stretch",
    )

    requested_signature = {"symbol": active_symbol}
    if requested:
        st.session_state["analytics_daily_closing_request"] = requested_signature
        refresh_daily_closing_cache()

    if st.session_state.get("analytics_daily_closing_request") != requested_signature:
        st.info(
            "Esta vista no consulta automaticamente `trii-prod-daily-closing-snapshots`. Usa el boton para cargar la serie del simbolo."
        )
        return

    with st.spinner("Consultando cierres diarios..."):
        response = load_daily_closing_snapshots(active_symbol)

    result = response.get("result", {})
    records = result.get("records", [])
    st.caption(
        f"`trii-prod-daily-closing-snapshots` | symbol `{active_symbol}` | {len(records)} registros"
    )
    if not records:
        st.info("No hay cierres diarios disponibles para el simbolo seleccionado.")
        return

    st.dataframe(
        normalize_records_for_table(records),
        hide_index=True,
        width="stretch",
    )

st.session_state.setdefault("analytics_last_manual_refresh", None)
st.session_state.setdefault("analytics_session_loaded_at", now_in_bogota())
st.session_state.setdefault("analytics_zscore_date", now_in_bogota().date())
st.session_state.setdefault("analytics_zscore_request", None)
st.session_state.setdefault("analytics_daily_closing_request", None)

st.markdown(
    ANALYTICS_PAGE_STYLES,
    unsafe_allow_html=True,
)

try:
    with st.spinner("Consultando simbolos disponibles..."):
        catalog_response = load_analytics_catalog()

    catalog_result = catalog_response.get("result", {})
    symbols = [
        str(symbol).strip().upper()
        for symbol in catalog_result.get("symbols", [])
        if str(symbol).strip()
    ]

    if not symbols:
        st.info("No se encontraron snapshots disponibles para construir filtros operativos.")
    else:
        filter_columns = st.columns([2.0, 1.1, 0.7], gap="medium")
        with filter_columns[0]:
            st.markdown("*Symbols*")
            selected_symbols = st.multiselect(
                "Symbols",
                options=symbols,
                default=symbols,
                help="Current snapshots e historic stats se consultan por estos simbolos.",
                label_visibility="collapsed",
            )
        active_symbol_default = selected_symbols[0] if selected_symbols else symbols[0]
        with filter_columns[1]:
            st.markdown("*Symbol puntual*")
            active_symbol = st.selectbox(
                "Symbol puntual",
                options=symbols,
                index=symbols.index(active_symbol_default),
                help="Usa este simbolo para consultas manuales de z-score opportunities y daily closing snapshots.",
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
            refresh_analytics_core_cache()
            st.toast("Current snapshots e historic stats fueron actualizados contra API Gateway.")

        overview_tab, diagnostic_tab, zscore_tab, closing_tab = st.tabs(
            [
                "Resumen",
                "Diagnostico",
                "Z-score opportunities",
                "Cierre diario",
            ],
            on_change="rerun",
        )
        selected_symbol_tuple = tuple(selected_symbols)

        if overview_tab.open:
            with overview_tab:
                _render_overview_fragment(selected_symbol_tuple)

        if diagnostic_tab.open:
            with diagnostic_tab:
                _render_diagnostic_fragment(selected_symbol_tuple)

        if zscore_tab.open:
            with zscore_tab:
                _render_zscore_fragment(active_symbol)

        if closing_tab.open:
            with closing_tab:
                _render_daily_closing_fragment(active_symbol)
except (BackendConfigurationError, ApiGatewayClientError) as exc:
    st.error("No fue posible consultar los snapshots recientes.")
    st.caption("Referencia interna: `analytics_recent_snapshots`")
    st.write(
        "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
        "o confirma que el API Gateway y la Lambda esten desplegados."
    )
    with st.expander("Detalle tecnico"):
        st.code(str(exc))
