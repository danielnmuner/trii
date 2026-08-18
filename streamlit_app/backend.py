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

from trii_ingestion.services import ApiGatewayClient


class BackendConfigurationError(RuntimeError):
    pass


def get_backend_client() -> ApiGatewayClient:
    backend_section = st.secrets.get("trii_backend", {})
    base_url = (
        _read_secret(backend_section, "api_gateway_url")
        or _read_secret(st.secrets, "api_gateway_url")
        or _read_secret(st.secrets, "API_GATEWAY_URL")
    )
    token = (
        _read_secret(backend_section, "api_gateway_token")
        or _read_secret(st.secrets, "api_gateway_token")
        or _read_secret(st.secrets, "API_GATEWAY_TOKEN")
    )

    if not base_url or not token:
        raise BackendConfigurationError(
            "Faltan secretos del backend. Configura `api_gateway_url` y `api_gateway_token` en Streamlit secrets."
        )

    return ApiGatewayClient(base_url=base_url, token=token)


def _read_secret(container, key: str):
    if hasattr(container, "get"):
        value = container.get(key)
        if isinstance(value, str):
            value = value.strip()
        return value or None
    return None
