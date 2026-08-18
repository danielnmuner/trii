from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from contract_specs import CONTRACT_SPECS
from trii_ingestion.models.types import SectionType


def text_state_key(section: SectionType) -> str:
    return f"text_{section.value}"


def init_state() -> None:
    st.session_state.setdefault("parsed_documents", {})
    st.session_state.setdefault("validation_reports", {})
    st.session_state.setdefault("consolidated_document", None)
    st.session_state.setdefault("send_message", None)
    st.session_state.setdefault("clear_capture_pending", False)
    st.session_state.setdefault("stock_orders_upload_result", None)
    st.session_state.setdefault("stock_orders_send_message", None)
    st.session_state.setdefault("stock_orders_uploaded_file", None)
    st.session_state.setdefault("invoice_archives_upload_result", None)
    st.session_state.setdefault("invoice_archives_send_message", None)
    st.session_state.setdefault("invoice_archives_uploaded_files", [])

    for spec in CONTRACT_SPECS:
        st.session_state.setdefault(text_state_key(spec.section), "")


def request_clear_capture() -> None:
    st.session_state["clear_capture_pending"] = True


def cancel_clear_capture() -> None:
    st.session_state["clear_capture_pending"] = False


def clear_capture() -> None:
    for spec in CONTRACT_SPECS:
        st.session_state[text_state_key(spec.section)] = ""
    st.session_state["parsed_documents"] = {}
    st.session_state["validation_reports"] = {}
    st.session_state["consolidated_document"] = None
    st.session_state["send_message"] = None
    st.session_state["clear_capture_pending"] = False
