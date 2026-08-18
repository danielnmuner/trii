from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st

from backend import BackendConfigurationError, get_backend_client
from trii_ingestion.services import ApiGatewayClientError


@st.cache_data(ttl=60, show_spinner=False)
def _load_recent_snapshots(days: int) -> dict:
    client = get_backend_client()
    return client.get_recent_snapshots(days=days)


st.write(
    "Esta vista consulta los snapshots persistidos en DynamoDB para mostrar la actividad reciente del mercado en los últimos 7 días, "
    "tomando como referencia la hora actual de America/Bogota."
)
st.caption(
    "*La tabla se ordena del registro más reciente al más antiguo y conserva los bloques técnicos anidados para que la consulta operativa "
    "siga siendo fiel al JSON consolidado almacenado.*"
)

days = 7

try:
    with st.spinner("Consultando snapshots recientes..."):
        response = _load_recent_snapshots(days)
    result = response.get("result", {})
    records = result.get("records", [])

    summary_columns = st.columns(3, gap="small")
    summary_columns[0].metric("Registros", result.get("record_count", 0))
    summary_columns[1].metric("Desde", result.get("from_date", "n/a"))
    summary_columns[2].metric("Hasta", result.get("to_timestamp", "n/a"))

    if not records:
        st.info("No se encontraron snapshots en los últimos 7 días.")
    else:
        dataframe = pd.DataFrame(records)
        st.dataframe(
            dataframe,
            hide_index=True,
            width="stretch",
            column_config={
                "stock_snapshot": st.column_config.JsonColumn("Stock snapshot"),
                "technical_oscillators": st.column_config.JsonColumn("Osciladores"),
                "technical_moving_averages": st.column_config.JsonColumn("Medias móviles"),
                "support_and_resistance": st.column_config.JsonColumn("Soportes y resistencias"),
            },
        )
except (BackendConfigurationError, ApiGatewayClientError) as exc:
    st.error("No fue posible consultar los snapshots recientes.")
    st.caption("Referencia interna: `analytics_recent_snapshots`")
    st.write(
        "Revisa la configuración de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
        "o confirma que el API Gateway y la Lambda estén desplegados."
    )
