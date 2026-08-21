from __future__ import annotations

import streamlit as st


def init_state() -> None:
    st.session_state.setdefault("stock_orders_upload_result", None)
    st.session_state.setdefault("stock_orders_send_message", None)
    st.session_state.setdefault("invoice_archives_upload_result", None)
    st.session_state.setdefault("invoice_archives_send_message", None)
