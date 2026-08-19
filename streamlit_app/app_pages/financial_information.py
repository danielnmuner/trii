from __future__ import annotations

import logging
import sys
from io import BytesIO
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
from trii_ingestion.services import ApiGatewayClientError, StockOrdersCsvService

LOGGER = logging.getLogger(__name__)
STOCK_ORDERS_SERVICE = StockOrdersCsvService()


def _render_processing_error(title: str, *, error_code: str, hint: str, exc: Exception) -> None:
    LOGGER.exception("Financial information processing error [%s]: %s", error_code, title, exc_info=exc)
    st.error(title)
    st.caption(f"Referencia interna: `{error_code}`")
    st.write(hint)


def _process_stock_orders_submission(*, uploaded_file, send_requested: bool) -> None:
    st.session_state["stock_orders_upload_result"] = None
    st.session_state["stock_orders_send_message"] = None

    if uploaded_file is None:
        st.error("Debes cargar un archivo CSV de ordenes antes de continuar.")
        return

    try:
        result = STOCK_ORDERS_SERVICE.parse(raw_bytes=uploaded_file.getvalue())
        st.session_state["stock_orders_upload_result"] = result
        if send_requested:
            client = get_backend_client()
            response = client.submit_stock_orders(
                file_name=uploaded_file.name,
                raw_bytes=uploaded_file.getvalue(),
            )
            persisted_result = response.get("result", {})
            st.session_state["stock_orders_send_message"] = (
                "Envio completado hacia DynamoDB. "
                f"Registros importados: {persisted_result.get('imported_records', 0)}."
            )
            st.success("Archivo validado y enviado correctamente.")
        else:
            st.success("Archivo validado correctamente. Ahora ya esta listo para envio.")
    except (BackendConfigurationError, ApiGatewayClientError) as exc:
        _render_processing_error(
            "El archivo es valido, pero no fue posible enviarlo al backend.",
            error_code="send_stock_orders_api",
            hint=(
                "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
                "o confirma que el API Gateway y la Lambda esten desplegados."
            ),
            exc=exc,
        )
    except Exception as exc:  # noqa: BLE001
        _render_processing_error(
            "No fue posible procesar el CSV de ordenes.",
            error_code="parse_stock_orders_csv",
            hint=(
                "Verifica que el archivo provenga del export de Trii y que conserve exactamente las columnas del ejemplo `orders-trii.csv`."
            ),
            exc=exc,
        )


def _render_uploaded_file_preview(uploaded_file) -> None:
    if uploaded_file is None:
        return

    try:
        preview_frame = pd.read_csv(BytesIO(uploaded_file.getvalue()), nrows=5)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("No fue posible construir la vista previa del CSV de movimientos: %s", exc)
        st.warning(
            "Se cargo un archivo, pero no fue posible mostrar la vista previa inicial. "
            "Puedes continuar con la validacion para obtener el detalle tecnico."
        )
        return

    st.subheader("Vista previa inicial")
    st.caption(
        "*Estas son las primeras 5 filas detectadas en el archivo cargado. Esta revision rapida ayuda a confirmar "
        "que el lote corresponde a movimientos de acciones antes de validar o enviar.*"
    )
    st.dataframe(preview_frame, hide_index=True, width="stretch")


st.write(
    "Carga el historico operativo de movimientos de acciones para conservar el contexto transaccional real de compras y ventas. "
    "Este archivo es clave para reconciliar ejecucion, volumen, comisiones y trazabilidad antes de persistir datos financieros."
)
st.caption(
    "*La carga de movimientos de acciones complementa los snapshots tecnicos con evidencia operativa real. Permite medir ejecucion, "
    "detectar duplicados, reconstruir decisiones historicas y preparar persistencia consistente hacia DynamoDB.*"
)

with st.form("stock_orders_upload_form", clear_on_submit=False, border=True):
    st.subheader("Movimientos de acciones")
    st.caption(
        "*Se espera un CSV exportado desde Trii con la estructura del ejemplo `orders-trii.csv`. "
        "Internamente el archivo se renombra con el patron `stock-order-timestamp-america-bogota-trii.csv`.*"
    )
    uploaded_file = st.file_uploader(
        "Archivo CSV de ordenes",
        type="csv",
        key="stock_orders_uploaded_file",
        help="Carga un unico archivo CSV con el historico de ordenes de Trii.",
        width="stretch",
    )

    validate_column, send_column = st.columns(2, gap="small")
    with validate_column:
        validate_requested = st.form_submit_button(
            "Validar archivo",
            key="validate_stock_orders_submit",
            type="secondary",
            icon=":material/fact_check:",
            width="stretch",
        )
    with send_column:
        send_requested = st.form_submit_button(
            "Validar y enviar",
            key="validate_and_send_stock_orders_submit",
            type="primary",
            icon=":material/cloud_upload:",
            width="stretch",
        )

if validate_requested or send_requested:
    _process_stock_orders_submission(uploaded_file=uploaded_file, send_requested=send_requested)

_render_uploaded_file_preview(uploaded_file)

upload_result = st.session_state.get("stock_orders_upload_result")
if upload_result is not None:
    st.header("Resultado de validacion")
    metrics_columns = st.columns(3, gap="small")
    metrics_columns[0].metric("Ordenes validas", upload_result.record_count)
    metrics_columns[1].metric("Simbolos detectados", len(upload_result.symbols))
    metrics_columns[2].metric("Zona horaria", upload_result.timezone)

    with st.container(border=True):
        st.write(f"**Nombre interno:** `{upload_result.storage_name}`")
        st.write(f"**Timestamp de carga:** `{upload_result.captured_at}`")
        st.write("**Simbolos detectados:** " + ", ".join(upload_result.symbols))

    st.subheader("Vista previa del lote")
    st.dataframe(
        pd.DataFrame(upload_result.preview_rows),
        hide_index=True,
        width="stretch",
    )

if st.session_state.get("stock_orders_send_message"):
    st.success(st.session_state["stock_orders_send_message"])
