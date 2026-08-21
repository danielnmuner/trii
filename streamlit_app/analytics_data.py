from __future__ import annotations

import streamlit as st

from backend import get_backend_client
from trii_ingestion.services import now_in_bogota


ANALYTICS_CACHE_TTL_SECONDS = 60
DEFAULT_ZSCORE_LIMIT = 250
DEFAULT_DAILY_CLOSING_LIMIT = 500


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def load_analytics_catalog() -> dict:
    client = get_backend_client()
    return client.get_analytics_catalog()


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def load_analytics_snapshot(symbol: str) -> dict:
    client = get_backend_client()
    return client.get_analytics_snapshot(symbol=symbol)


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def load_zscore_opportunities(symbol: str, trading_date: str, limit: int = DEFAULT_ZSCORE_LIMIT) -> dict:
    client = get_backend_client()
    return client.get_analytics_zscore_opportunities(
        symbol=symbol,
        trading_date=trading_date,
        limit=limit,
    )


@st.cache_data(ttl=ANALYTICS_CACHE_TTL_SECONDS, show_spinner=False)
def load_daily_closing_snapshots(symbol: str, limit: int = DEFAULT_DAILY_CLOSING_LIMIT) -> dict:
    client = get_backend_client()
    return client.get_analytics_daily_closing(
        symbol=symbol,
        limit=limit,
    )


def refresh_analytics_core_cache() -> None:
    load_analytics_catalog.clear()
    load_analytics_snapshot.clear()
    st.session_state["analytics_last_manual_refresh"] = now_in_bogota()


def refresh_zscore_cache() -> None:
    load_zscore_opportunities.clear()
    st.session_state["analytics_zscore_last_refresh"] = now_in_bogota()


def refresh_daily_closing_cache() -> None:
    load_daily_closing_snapshots.clear()
    st.session_state["analytics_daily_closing_last_refresh"] = now_in_bogota()
