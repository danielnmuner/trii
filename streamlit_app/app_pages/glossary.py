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
import pandas as pd

from glossary_specs import GLOSSARY_SECTIONS

st.write(
    "Este glosario traduce los términos técnicos de Trii a una lectura práctica para operación, validación de señales y toma de decisiones."
)

for section in GLOSSARY_SECTIONS:
    with st.container(border=True):
        st.subheader(section.title)
        st.caption(f"*{section.summary}*")
        st.table(
            pd.DataFrame(
                [
                    {
                        "Métrica / concepto": entry.term,
                        "Definición práctica": entry.practical_definition,
                        "Cómo usarlo": entry.how_to_use,
                        "Qué decisión soporta": entry.decision_support,
                    }
                    for entry in section.entries
                ]
            )
        )
