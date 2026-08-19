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


def _build_depth_chart(depth_history: pd.DataFrame, side: str) -> alt.Chart:
    side_frame = depth_history[depth_history["side"] == side].copy()
    color_encoding = alt.Color(
        "level_label:N",
        title="Linea de profundidad",
        sort=[f"Nivel {level}" for level in range(1, 6)],
    )
    tooltip = [
        alt.Tooltip("captured_at:T", title="Timestamp", format="%d-%m-%Y %H:%M"),
        alt.Tooltip("level_label:N", title="Linea"),
        alt.Tooltip("price:Q", title="Precio", format=",.2f"),
        alt.Tooltip("quantity:Q", title="Cantidad", format=",.0f"),
    ]
    base = alt.Chart(side_frame).encode(
        x=alt.X("captured_at:T", title="Tiempo"),
        color=color_encoding,
        tooltip=tooltip,
    )

    price_chart = base.mark_line(point=True).encode(
        y=alt.Y("price:Q", title="Precio", scale=alt.Scale(zero=False))
    )
    quantity_chart = base.mark_line(point=True, strokeDash=[6, 2]).encode(
        y=alt.Y("quantity:Q", title="Cantidad")
    )

    return alt.vconcat(
        price_chart.properties(title=f"{side} - precio por nivel", height=220),
        quantity_chart.properties(title=f"{side} - cantidad por nivel", height=220),
    ).resolve_scale(color="shared")


st.write(
    "Esta vista consulta los snapshots persistidos en DynamoDB para mostrar la actividad reciente del mercado "
    "en los ultimos 7 dias, tomando como referencia la hora actual de America/Bogota."
)
st.caption(
    "*Los filtros se aplican al grafico y a la tabla al mismo tiempo para mantener una sola lectura operativa por especie "
    "y por ventana de tiempo.*"
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

        filter_column_time, filter_column_symbol = st.columns(2, gap="large")
        with filter_column_time:
            selected_window = st.selectbox(
                "Ventana de tiempo",
                options=time_window_options,
                index=time_window_options.index("6h"),
                help=get_time_window_help_text("6h"),
            )
        with filter_column_symbol:
            selected_symbol = st.selectbox(
                "Simbolo",
                options=symbols,
                index=0,
                help="La vista analitica solo puede consultar una especie a la vez.",
            )

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

        if not filtered_records:
            st.info("No hay snapshots para ese simbolo dentro de la ventana seleccionada.")
        else:
            depth_history = pd.DataFrame(build_depth_history_rows(filtered_records))
            if not depth_history.empty:
                depth_history["captured_at"] = pd.to_datetime(depth_history["captured_at"], errors="coerce")
                depth_history = depth_history.dropna(subset=["captured_at"])

                if not depth_history.empty:
                    st.subheader("Profundidad reciente")
                    st.caption(
                        "*Se separan precio y cantidad por lado del libro para evitar que una sola escala distorsione "
                        "la lectura operativa de las cinco lineas visibles.*"
                    )
                    bid_column, ask_column = st.columns(2, gap="large")
                    with bid_column:
                        st.altair_chart(_build_depth_chart(depth_history, "Bid"), width="stretch")
                    with ask_column:
                        st.altair_chart(_build_depth_chart(depth_history, "Ask"), width="stretch")

            dataframe = pd.DataFrame(filtered_records)
            if "captured_at" in dataframe.columns:
                dataframe["captured_at"] = pd.to_datetime(dataframe["captured_at"], errors="coerce")

            st.dataframe(
                dataframe,
                hide_index=True,
                width="stretch",
                column_config={
                    "captured_at": st.column_config.DatetimeColumn("Capturado", format="DD-MM-YYYY HH:mm"),
                    "captured_date": None,
                    "snapshot_checksum": None,
                    "symbol_captured_at": None,
                    "bid_levels": st.column_config.JsonColumn("Bid levels"),
                    "ask_levels": st.column_config.JsonColumn("Ask levels"),
                },
            )

        with st.container(horizontal=True):
            st.metric("Registros", summary["record_count"], border=True)
            st.metric("Desde", summary["from_timestamp"], border=True)
            st.metric("Hasta", summary["to_timestamp"], border=True)
except (BackendConfigurationError, ApiGatewayClientError) as exc:
    st.error("No fue posible consultar los snapshots recientes.")
    st.caption("Referencia interna: `analytics_recent_snapshots`")
    st.write(
        "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
        "o confirma que el API Gateway y la Lambda esten desplegados."
    )
    with st.expander("Detalle tecnico"):
        st.code(str(exc))
