from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "streamlit_app"
SRC_DIR = ROOT_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from contract_specs import CONTRACT_SPECS
from state import clear_capture, text_state_key
from trii_ingestion.models.types import SectionType
from trii_ingestion.services import ClipboardParserService, ReconciliationService
from trii_ingestion.validation import ValidationReport

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
        "Completa los cuatro contratos en esta misma página. "
        "Solo cuando todos sean válidos se construirá el JSON consolidado."
    )

    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button(
            "Limpiar captura actual",
            icon=":material/delete_sweep:",
        ):
            clear_capture()
            st.rerun()

    with st.form("trii_contracts_form", clear_on_submit=False, border=True):
        for spec in CONTRACT_SPECS:
            with st.container(border=True):
                st.subheader(spec.title)
                st.write(spec.summary)
                st.caption(
                    f"Qué copiar: {spec.what_to_copy} "
                    f"• Dónde: {spec.where_to_find_it}"
                )
                st.text_area(
                    "Texto copiado",
                    key=text_state_key(spec.section),
                    placeholder=spec.placeholder,
                    height=220,
                    label_visibility="visible",
                    persist_state="session",
                )

        submitted = st.form_submit_button(
            "Validar y construir JSON",
            type="primary",
            icon=":material/schema:",
        )

    if submitted:
        _process_form_submission()


def _process_form_submission() -> None:
    st.session_state["parsed_documents"] = {}
    st.session_state["validation_reports"] = {}
    st.session_state["consolidated_document"] = None
    st.session_state["send_message"] = None

    text_by_section = {
        spec.section: st.session_state.get(text_state_key(spec.section), "").strip()
        for spec in CONTRACT_SPECS
    }

    empty_sections = [spec.title for spec in CONTRACT_SPECS if not text_by_section[spec.section]]
    if empty_sections:
        st.error(
            "Faltan contratos obligatorios por diligenciar: " + ", ".join(empty_sections)
        )
        return

    stock_text = text_by_section[SectionType.STOCK_SNAPSHOT]
    stock_report = PARSER_SERVICE.validate(stock_text, SectionType.STOCK_SNAPSHOT)
    st.session_state["validation_reports"][SectionType.STOCK_SNAPSHOT.value] = stock_report
    if not stock_report.is_valid:
        return

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
        st.error("No fue posible procesar `Resumen de la acción`.")
        with st.expander("Detalle técnico"):
            st.code(str(exc))
        return

    for spec in CONTRACT_SPECS:
        if spec.section == SectionType.STOCK_SNAPSHOT:
            continue

        raw_text = text_by_section[spec.section]
        report = PARSER_SERVICE.validate(raw_text, spec.section)
        st.session_state["validation_reports"][spec.section.value] = report
        if not report.is_valid:
            continue

        try:
            parsed = PARSER_SERVICE.parse(
                raw_text,
                spec.section,
                asset_context=asset_context,
            )
            st.session_state["parsed_documents"][spec.section.value] = parsed.document
        except Exception as exc:  # noqa: BLE001
            st.error(f"No fue posible procesar `{spec.title}`.")
            with st.expander(f"Detalle técnico de {spec.title}"):
                st.code(str(exc))

    if len(st.session_state["parsed_documents"]) != len(CONTRACT_SPECS):
        st.warning(
            "No se construyó el JSON consolidado porque uno o más contratos siguen teniendo problemas."
        )
        return

    try:
        consolidated = RECONCILIATION_SERVICE.reconcile(st.session_state["parsed_documents"])
        st.session_state["consolidated_document"] = consolidated.document
        st.success("JSON consolidado construido correctamente.")
    except Exception as exc:  # noqa: BLE001
        st.error("Los cuatro contratos fueron parseados, pero no pasaron la validación cruzada.")
        with st.expander("Detalle técnico"):
            st.code(str(exc))


def _render_results() -> None:
    reports: dict[str, ValidationReport] = st.session_state["validation_reports"]
    if reports:
        st.header("Resultados de validación")
        for spec in CONTRACT_SPECS:
            report = reports.get(spec.section.value)
            if report is not None:
                _render_validation_report(spec.title, report)

    consolidated_document = st.session_state.get("consolidated_document")
    if consolidated_document is not None:
        st.header("JSON consolidado final")
        st.json(consolidated_document.model_dump(mode="json"))

        if st.button(
            "Enviar a DynamoDB (simulado)",
            type="primary",
            icon=":material/cloud_upload:",
            width="stretch",
        ):
            st.session_state["send_message"] = (
                "Envío simulado correctamente. El payload consolidado quedó listo para persistencia."
            )

        if st.session_state.get("send_message"):
            st.success(st.session_state["send_message"])


_render_form()
_render_results()
