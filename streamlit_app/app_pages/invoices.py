from __future__ import annotations

import logging
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
from trii_ingestion.services import ApiGatewayClientError, InvoiceArchivesService

LOGGER = logging.getLogger(__name__)
INVOICE_ARCHIVES_SERVICE = InvoiceArchivesService()


def _render_processing_error(title: str, *, error_code: str, hint: str, exc: Exception) -> None:
    LOGGER.exception("Invoice upload processing error [%s]: %s", error_code, title, exc_info=exc)
    st.error(title)
    st.caption(f"Referencia interna: `{error_code}`")
    st.write(hint)


def _process_invoice_submission(*, uploaded_files, send_requested: bool) -> None:
    st.session_state["invoice_archives_upload_result"] = None
    st.session_state["invoice_archives_send_message"] = None

    normalized_uploaded_files = uploaded_files or []
    if not normalized_uploaded_files:
        st.error("Debes cargar al menos un archivo ZIP de factura antes de continuar.")
        return

    try:
        archives = [(uploaded_file.name, uploaded_file.getvalue()) for uploaded_file in normalized_uploaded_files]
        prepared_archives = INVOICE_ARCHIVES_SERVICE.prepare_archives(archives=archives)
        st.session_state["invoice_archives_upload_result"] = prepared_archives.upload_result
        if send_requested:
            client = get_backend_client()
            response = client.submit_invoice_archives(documents=list(prepared_archives.documents))
            persisted_result = response.get("result", {})
            st.session_state["invoice_archives_send_message"] = (
                "Envio completado hacia S3. "
                f"Archivos cargados: {persisted_result.get('uploaded_files', 0)}."
            )
            st.success("Lote validado y enviado correctamente.")
        else:
            st.success("Lote validado correctamente. Ahora ya esta listo para envio.")
    except (BackendConfigurationError, ApiGatewayClientError) as exc:
        _render_processing_error(
            "El lote es valido, pero no fue posible enviarlo al backend.",
            error_code="send_invoice_archives_api",
            hint=(
                "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
                "o confirma que el API Gateway y la Lambda esten desplegados."
            ),
            exc=exc,
        )
    except Exception as exc:  # noqa: BLE001
        _render_processing_error(
            "No fue posible procesar el lote de facturas.",
            error_code="inspect_invoice_archives",
            hint=(
                "Verifica que cada archivo sea un ZIP valido y que dentro contenga exactamente un XML y un PDF por factura."
            ),
            exc=exc,
        )


st.write(
    "Carga los archivos fuente de facturas para conservar respaldo documental antes del procesamiento contable y de reconciliacion. "
    "En esta etapa el objetivo es validar el lote, descomprimir cada ZIP en memoria y dejar el XML y el PDF listos para envio hacia S3."
)
st.caption(
    "*Estas facturas son la evidencia documental de las operaciones. La app extrae el XML y el PDF antes del envio para que S3 conserve los archivos fuente finales "
    "que luego alimentaran el parseo y la reconciliacion financiera, sin depender del ZIP original como formato de almacenamiento.*"
)

with st.form("invoice_archives_upload_form", clear_on_submit=False, border=True):
    st.subheader("Facturas fuente")
    st.caption(
        "*Se esperan archivos ZIP de factura como los de la carpeta `invoices`. Cada ZIP debe contener exactamente un XML y un PDF, y ambos archivos seran enviados por separado a S3.*"
    )
    uploaded_files = st.file_uploader(
        "Archivos ZIP de facturas",
        type="zip",
        accept_multiple_files=True,
        key="invoice_archives_uploaded_files",
        help="Carga uno o varios archivos ZIP de factura exportados por la entidad emisora.",
        width="stretch",
    )

    validate_column, send_column = st.columns(2, gap="small")
    with validate_column:
        validate_requested = st.form_submit_button(
            "Validar lote",
            key="validate_invoice_archives_submit",
            type="secondary",
            icon=":material/task_alt:",
            width="stretch",
        )
    with send_column:
        send_requested = st.form_submit_button(
            "Validar y enviar",
            key="validate_and_send_invoice_archives_submit",
            type="primary",
            icon=":material/cloud_upload:",
            width="stretch",
        )

if validate_requested or send_requested:
    _process_invoice_submission(uploaded_files=uploaded_files, send_requested=send_requested)

upload_result = st.session_state.get("invoice_archives_upload_result")
if upload_result is not None:
    st.header("Resultado de validacion")
    metrics_columns = st.columns(3, gap="small")
    metrics_columns[0].metric("ZIP validos", upload_result.archive_count)
    metrics_columns[1].metric("XML detectados", upload_result.xml_count)
    metrics_columns[2].metric("PDF detectados", upload_result.pdf_count)

    with st.container(border=True):
        st.write(f"**Timestamp de carga:** `{upload_result.captured_at}`")
        st.write(f"**Zona horaria:** `{upload_result.timezone}`")
        st.write("**Destino esperado:** `S3 / invoices/YYYY/MM/DD/<invoice_id>/archivo.xml|archivo.pdf`")

    st.subheader("Vista previa del lote")
    st.dataframe(
        pd.DataFrame(upload_result.preview_rows),
        hide_index=True,
        width="stretch",
    )

if st.session_state.get("invoice_archives_send_message"):
    st.success(st.session_state["invoice_archives_send_message"])
