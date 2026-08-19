from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd
import streamlit as st

from glossary_specs import GLOSSARY_SECTIONS

st.write(
    "Este glosario traduce los terminos tecnicos de Trii a una lectura practica para operacion, validacion de senales y toma de decisiones."
)

for section in GLOSSARY_SECTIONS:
    with st.container(border=True):
        st.subheader(section.title)
        st.caption(f"*{section.summary}*")
        st.table(
            pd.DataFrame(
                [
                    {
                        "Metrica / concepto": entry.term,
                        "Formula": entry.formula,
                        "Variables": entry.variables,
                        "Definicion practica": entry.practical_definition,
                        "Como usarlo": entry.how_to_use,
                        "Que decision soporta": entry.decision_support,
                    }
                    for entry in section.entries
                ]
            )
        )
