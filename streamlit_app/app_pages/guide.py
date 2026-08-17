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

st.write(
    "Esta guía resume dónde se encuentra cada bloque dentro de Trii y qué debe incluirse en el copiado."
)

for spec in CONTRACT_SPECS:
    with st.container(border=True):
        st.subheader(spec.title)
        st.image(str(spec.image_path), caption=spec.title, width="stretch")
        st.write(f"**Qué copiar:** {spec.what_to_copy}")
        st.write(f"**Dónde encontrarlo:** {spec.where_to_find_it}")
        st.write(f"**Cómo copiarlo:** {spec.how_to_copy}")
        st.write("**Cómo pegarlo:** usa `Ctrl + V` directamente en la caja correspondiente del formulario principal.")
