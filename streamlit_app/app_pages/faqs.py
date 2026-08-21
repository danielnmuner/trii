from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from faq_content import FAQ_ENTRIES

st.write("Preguntas frecuentes clave sobre operación, mercado y funcionalidades de Trii.")

for entry in FAQ_ENTRIES:
    with st.expander(entry.question, expanded=False):
        for paragraph in entry.answer_paragraphs:
            st.write(paragraph)
