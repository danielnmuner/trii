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


def init_state() -> None:
    st.session_state.setdefault("stock_orders_upload_result", None)
    st.session_state.setdefault("stock_orders_send_message", None)
    st.session_state.setdefault("invoice_archives_upload_result", None)
    st.session_state.setdefault("invoice_archives_send_message", None)
