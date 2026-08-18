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
    ReconciliationService,
)
from trii_ingestion.validation import ValidationReport

LOGGER = logging.getLogger(__name__)
PARSER_SERVICE = ClipboardParserService()
RECONCILIATION_SERVICE = ReconciliationService()


def _render_validation_report(title: str, report: ValidationReport) -> None:
    with st.container(border=True):
        st.subheader(title)
        if report.is_valid:
            st.success("Validación completada sin errores.")
            return

        st.error(f"Se detectaron {len(report.issues)} problema(s) en este contrato.")
        for issue in report.issues:
            st.write(f"**Error:** {issue.message}")
            st.caption(f"Código: `{issue.code}`")
            st.write(f"**Cómo corregirlo:** {issue.hint}")
            st.divider()


def _render_form() -> None:
    st.write(
        "Completa los cuatro contratos en el orden obligatorio 1, 2, 3 y 4. "
        "Solo cuando los cuatro bloques pertenezcan al mismo snapshot y pasen la validación se construirá el JSON consolidado."
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
        for index, spec in enumerate(CONTRACT_SPECS, start=1):
            with st.container(border=True):
                st.subheader(f"{index}. {spec.title}")
                st.caption(f"*{spec.importance_note}*")
                st.text_area(
                    f"Entrada del contrato {index}: {spec.title}",
                    key=text_state_key(spec.section),
                    placeholder=spec.placeholder,
                    height=220,
                    label_visibility="collapsed",
                    persist_state="session",
                )

        validate_column, send_column = st.columns(2, gap="small")
        with validate_column:
            validate_requested = st.form_submit_button(
                "Validar contratos",
                key="validate_contracts_submit",
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
            "Vas a borrar los cuatro contratos pegados, los resultados de validación y el JSON consolidado actual."
        )
        st.caption("Esta acción no se puede deshacer.")
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
    consolidated_document = st.session_state.get("consolidated_document")
    if consolidated_document is None:
        raise ValueError("No existe un snapshot consolidado para enviar.")

    client = get_backend_client()
    response = client.submit_snapshot(consolidated_document.model_dump(mode="json"))
    result = response.get("result", {})
    st.session_state["send_message"] = (
        "Envío completado hacia DynamoDB. "
        f"Símbolo: {result.get('symbol', 'n/a')} | capturado: {result.get('captured_at', 'n/a')}."
    )


def _process_form_submission(*, send_requested: bool) -> None:
    st.session_state["parsed_documents"] = {}
    st.session_state["validation_reports"] = {}
    st.session_state["consolidated_document"] = None
    st.session_state["send_message"] = None

    text_by_section = {
        spec.section: st.session_state.get(text_state_key(spec.section), "").strip()
        for spec in CONTRACT_SPECS
    }

    for spec in CONTRACT_SPECS:
        report = PARSER_SERVICE.validate(text_by_section[spec.section], spec.section)
        st.session_state["validation_reports"][spec.section.value] = report

    invalid_specs = [
        spec
        for spec in CONTRACT_SPECS
        if not st.session_state["validation_reports"][spec.section.value].is_valid
    ]
    if invalid_specs:
        st.error(
            "Se detectaron problemas en "
            f"{len(invalid_specs)} contrato(s): "
            + ", ".join(spec.title for spec in invalid_specs)
            + ". Corrige los errores indicados más abajo y vuelve a validar."
        )
        return

    stock_text = text_by_section[SectionType.STOCK_SNAPSHOT]
    try:
        stock_document = PARSER_SERVICE.parse(
            stock_text,
            SectionType.STOCK_SNAPSHOT,
        ).document
        st.session_state["parsed_documents"][SectionType.STOCK_SNAPSHOT.value] = stock_document
        asset_context = PARSER_SERVICE.asset_context_from_documents(
            st.session_state["parsed_documents"]
        )
    except Exception as exc:  # noqa: BLE001
        _render_processing_error(
            "No fue posible procesar `Resumen de la acción`.",
            error_code="parse_stock_snapshot",
            hint=(
                "Revisa que el bloque pertenezca a la misma acción y que incluya "
                "profundidad de mercado e indicadores completos."
            ),
            exc=exc,
        )
        return

    parse_failures: list[str] = []
    for spec in CONTRACT_SPECS:
        if spec.section == SectionType.STOCK_SNAPSHOT:
            continue

        raw_text = text_by_section[spec.section]
        try:
            parsed = PARSER_SERVICE.parse(
                raw_text,
                spec.section,
                asset_context=asset_context,
            )
            st.session_state["parsed_documents"][spec.section.value] = parsed.document
        except Exception as exc:  # noqa: BLE001
            parse_failures.append(spec.title)
            _render_processing_error(
                f"No fue posible procesar `{spec.title}`.",
                error_code=f"parse_{spec.section.value}",
                hint=(
                    "El contrato superó la validación básica, pero el contenido no "
                    "se pudo interpretar de forma consistente. Revisa que el bloque "
                    "copiado esté completo y no pertenezca a otra acción."
                ),
                exc=exc,
            )

    if parse_failures or len(st.session_state["parsed_documents"]) != len(CONTRACT_SPECS):
        st.warning(
            "No se construyó el JSON consolidado porque uno o más contratos siguen teniendo problemas de procesamiento."
        )
        return

    try:
        consolidated = RECONCILIATION_SERVICE.reconcile(st.session_state["parsed_documents"])
        st.session_state["consolidated_document"] = consolidated.document
        if send_requested:
            try:
                _send_snapshot_to_backend()
                st.success("JSON consolidado construido y enviado correctamente.")
            except (BackendConfigurationError, ApiGatewayClientError, ValueError) as exc:
                _render_processing_error(
                    "El JSON consolidado es válido, pero no fue posible enviarlo al backend.",
                    error_code="send_snapshot_api",
                    hint=(
                        "Revisa la configuración de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
                        "o confirma que el API Gateway y la Lambda estén desplegados."
                    ),
                    exc=exc,
                )
        else:
            st.success("JSON consolidado construido correctamente. Ahora ya está listo para envío.")
    except Exception as exc:  # noqa: BLE001
        _render_processing_error(
            "Los cuatro contratos fueron parseados, pero no pasaron la validación cruzada.",
            error_code="reconcile_snapshot_payload",
            hint=(
                "Esto suele pasar cuando uno de los bloques pertenece a otra acción "
                "o a otro momento de mercado. Limpia la captura y vuelve a pegar los cuatro contratos del mismo snapshot."
            ),
            exc=exc,
        )


def _render_results() -> None:
    reports: dict[str, ValidationReport] = st.session_state["validation_reports"]
    if reports:
        st.header("Resultados de validación")
        for index, spec in enumerate(CONTRACT_SPECS, start=1):
            report = reports.get(spec.section.value)
            if report is not None:
                _render_validation_report(f"{index}. {spec.title}", report)

    consolidated_document = st.session_state.get("consolidated_document")
    if consolidated_document is not None:
        st.header("JSON consolidado final")
        st.json(consolidated_document.model_dump(mode="json"))

        if st.session_state.get("send_message"):
            st.success(st.session_state["send_message"])


_render_form()
_render_results()
