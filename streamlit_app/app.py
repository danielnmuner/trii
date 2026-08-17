from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from state import init_state

st.set_page_config(page_title="Parser de contratos de Trii", page_icon="T", layout="wide")
init_state()

pages = {
    "": [
        st.Page(
            "app_pages/capture.py",
            title="Captura",
            icon=":material/data_object:",
            default=True,
        ),
        st.Page(
            "app_pages/guide.py",
            title="Guía de copiado",
            icon=":material/help_center:",
        ),
    ]
}

page = st.navigation(pages, position="sidebar")

st.title("Parser de contratos de Trii")
page.run()
