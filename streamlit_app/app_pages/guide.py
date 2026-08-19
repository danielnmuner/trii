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

from contract_specs import CONTRACT_SPECS

st.write(
    "Esta referencia visual ubica el bloque que hoy alimenta el snapshot persistido y resume por que sus campos son suficientes para construir el registro principal de mercado."
)

for row_start in range(0, len(CONTRACT_SPECS), 2):
    columns = st.columns(2, gap="large")
    row_specs = CONTRACT_SPECS[row_start : row_start + 2]

    for column, (index, spec) in zip(columns, enumerate(row_specs, start=row_start + 1), strict=False):
        with column:
            with st.container(border=True):
                st.subheader(f"{index}. {spec.title}")
                st.image(str(spec.image_path), caption=spec.title, width="stretch")
                st.caption(f"*{spec.importance_note}*")
