from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from state import init_state

st.set_page_config(page_title="Parser de contratos de Trii", page_icon="T", layout="wide")
init_state()

st.markdown(
    """
    <style>
    div.stButton > button[kind="secondary"],
    div.stFormSubmitButton > button[kind="secondary"] {
        background-color: #02fb7e;
        color: #000000;
        border: 1px solid #02fb7e;
    }

    div.stButton > button[kind="secondary"]:hover,
    div.stFormSubmitButton > button[kind="secondary"]:hover {
        background-color: #02fb7e;
        color: #000000;
        border: 1px solid #02fb7e;
        filter: brightness(0.97);
    }

    div.stButton > button[kind="secondary"]:focus,
    div.stFormSubmitButton > button[kind="secondary"]:focus {
        color: #000000;
        border: 1px solid #02fb7e;
        box-shadow: 0 0 0 0.2rem rgba(2, 251, 126, 0.25);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = {
    "": [
        st.Page(
            "app_pages/analytics.py",
            title="Analytics",
            icon=":material/analytics:",
        ),
        st.Page(
            "app_pages/capture.py",
            title="Captura",
            icon=":material/data_object:",
            default=True,
        ),
        st.Page(
            "app_pages/financial_information.py",
            title="Movimientos",
            icon=":material/account_balance_wallet:",
        ),
        st.Page(
            "app_pages/invoices.py",
            title="Facturas",
            icon=":material/receipt_long:",
        ),
        st.Page(
            "app_pages/faqs.py",
            title="FAQS",
            icon=":material/live_help:",
        ),
        st.Page(
            "app_pages/glossary.py",
            title="Glosario",
            icon=":material/menu_book:",
        ),
        st.Page(
            "app_pages/guide.py",
            title="Referencia visual",
            icon=":material/help_center:",
        ),
    ]
}

page = st.navigation(pages, position="sidebar")

st.title("Parser de contratos de Trii")
page.run()
