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

import streamlit as st

from backend import BackendConfigurationError, get_backend_client
from contract_specs import CONTRACT_SPECS
from state import cancel_clear_capture, clear_capture, request_clear_capture, text_state_key
from trii_ingestion.models.types import SectionType
from trii_ingestion.services import (
    ApiGatewayClientError,
    ClipboardParserService,
    SnapshotPayloadService,
)
from trii_ingestion.validation import ValidationReport

LOGGER = logging.getLogger(__name__)
PARSER_SERVICE = ClipboardParserService()
SNAPSHOT_PAYLOAD_SERVICE = SnapshotPayloadService()
PRIMARY_SPEC = CONTRACT_SPECS[0]


def _render_validation_report(title: str, report: ValidationReport) -> None:
    with st.container(border=True):
        st.subheader(title)
        if report.is_valid:
            st.success("Validacion completada sin errores.")
            return

        st.error(f"Se detectaron {len(report.issues)} problema(s) en este contrato.")
        for issue in report.issues:
            st.write(f"**Error:** {issue.message}")
            st.caption(f"Codigo: `{issue.code}`")
            st.write(f"**Como corregirlo:** {issue.hint}")
            st.divider()


def _render_form() -> None:
    st.write(
        "Esta captura ahora procesa unicamente `Indicadores principales`. "
        "Si el bloque pertenece a una sola accion y pasa la validacion, se construira el JSON final del snapshot."
    )

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Limpiar captura actual",
            icon=":material/delete_sweep:",
        ):
            request_clear_capture()
            st.rerun()

    _render_clear_confirmation()

    with st.form("trii_contracts_form", clear_on_submit=False, border=True):
        with st.container(border=True):
            st.subheader(f"1. {PRIMARY_SPEC.title}")
            st.caption(f"*{PRIMARY_SPEC.importance_note}*")
            st.text_area(
                "Entrada del contrato 1: Indicadores principales",
                key=text_state_key(PRIMARY_SPEC.section),
                placeholder=PRIMARY_SPEC.placeholder,
                height=260,
                label_visibility="collapsed",
                persist_state="session",
            )

        validate_column, send_column = st.columns(2, gap="small")
        with validate_column:
            validate_requested = st.form_submit_button(
                "Validar contrato",
                key="validate_contract_submit",
                type="secondary",
                icon=":material/rule:",
                width="stretch",
            )
        with send_column:
            send_requested = st.form_submit_button(
                "Validar y enviar",
                key="validate_and_send_submit",
                type="primary",
                icon=":material/cloud_upload:",
                width="stretch",
            )

    if validate_requested or send_requested:
        _process_form_submission(send_requested=send_requested)


def _render_clear_confirmation() -> None:
    if not st.session_state.get("clear_capture_pending"):
        return

    with st.container(border=True):
        st.warning(
            "Vas a borrar el contrato pegado, los resultados de validacion y el JSON final actual."
        )
        st.caption("Esta accion no se puede deshacer.")
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                "Cancelar limpieza",
                icon=":material/close:",
            ):
                cancel_clear_capture()
                st.rerun()
            if st.button(
                "Confirmar limpieza total",
                type="primary",
                icon=":material/delete_forever:",
            ):
                clear_capture()
                st.rerun()


def _render_processing_error(title: str, *, error_code: str, hint: str, exc: Exception) -> None:
    LOGGER.exception("UI processing error [%s]: %s", error_code, title, exc_info=exc)
    st.error(title)
    st.caption(f"Referencia interna: `{error_code}`")
    st.write(hint)


def _send_snapshot_to_backend() -> None:
    final_document = st.session_state.get("consolidated_document")
    if final_document is None:
        raise ValueError("No existe un snapshot final para enviar.")

    client = get_backend_client()
    response = client.submit_snapshot(final_document.model_dump(mode="json"))
    result = response.get("result", {})
    st.session_state["send_message"] = (
        "Envio completado hacia DynamoDB. "
        f"Simbolo: {result.get('symbol', 'n/a')} | capturado: {result.get('captured_at', 'n/a')}."
    )


def _process_form_submission(*, send_requested: bool) -> None:
    st.session_state["parsed_documents"] = {}
    st.session_state["validation_reports"] = {}
    st.session_state["consolidated_document"] = None
    st.session_state["send_message"] = None

    raw_text = st.session_state.get(text_state_key(SectionType.STOCK_SNAPSHOT), "").strip()
    report = PARSER_SERVICE.validate(raw_text, SectionType.STOCK_SNAPSHOT)
    st.session_state["validation_reports"][SectionType.STOCK_SNAPSHOT.value] = report

    if not report.is_valid:
        st.error(
            "Se detectaron problemas en `Indicadores principales`. Corrige los errores indicados mas abajo y vuelve a validar."
        )
        return

    try:
        parsed_document = PARSER_SERVICE.parse(
            raw_text,
            SectionType.STOCK_SNAPSHOT,
        ).document
        st.session_state["parsed_documents"][SectionType.STOCK_SNAPSHOT.value] = parsed_document
        st.session_state["consolidated_document"] = SNAPSHOT_PAYLOAD_SERVICE.build(parsed_document)
        if send_requested:
            try:
                _send_snapshot_to_backend()
                st.success("JSON final construido y enviado correctamente.")
            except (BackendConfigurationError, ApiGatewayClientError, ValueError) as exc:
                _render_processing_error(
                    "El JSON final es valido, pero no fue posible enviarlo al backend.",
                    error_code="send_snapshot_api",
                    hint=(
                        "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
                        "o confirma que el API Gateway y la Lambda esten desplegados."
                    ),
                    exc=exc,
                )
        else:
            st.success("JSON final construido correctamente. Ahora ya esta listo para envio.")
    except Exception as exc:  # noqa: BLE001
        _render_processing_error(
            "No fue posible procesar `Indicadores principales`.",
            error_code="parse_stock_snapshot",
            hint=(
                "Revisa que el bloque pertenezca a la accion correcta y que incluya precio, profundidad e indicadores completos."
            ),
            exc=exc,
        )


def _render_results() -> None:
    reports: dict[str, ValidationReport] = st.session_state["validation_reports"]
    if reports:
        st.header("Resultados de validacion")
        report = reports.get(SectionType.STOCK_SNAPSHOT.value)
        if report is not None:
            _render_validation_report("1. Indicadores principales", report)

    final_document = st.session_state.get("consolidated_document")
    if final_document is not None:
        st.header("JSON final")
        st.json(final_document.model_dump(mode="json"))

        if st.session_state.get("send_message"):
            st.success(st.session_state["send_message"])


_render_form()
_render_results()
