from __future__ import annotations

import re
import unicodedata
from datetime import date

from trii_ingestion.models.types import Signal

_SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

_SIGNAL_MAP = {
    "compra_fuerte": Signal.STRONG_BUY,
    "compra": Signal.BUY,
    "mantener": Signal.HOLD,
    "venta": Signal.SELL,
    "venta_fuerte": Signal.STRONG_SELL,
}


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_money(value: str) -> float:
    normalized = value.replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")
    return float(normalized)


def parse_int(value: str) -> int:
    digits_only = re.sub(r"[^\d-]", "", value)
    return int(digits_only)


def parse_percent(value: str) -> float:
    normalized = value.replace("%", "").replace(" ", "").replace(",", ".")
    return float(normalized)


def normalize_key(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value.strip().lower())
    return cleaned.strip("_")


def parse_signal(value: str) -> Signal:
    normalized = normalize_key(value)
    if normalized in _SIGNAL_MAP:
        return _SIGNAL_MAP[normalized]

    # Flexible handling for technical sections where Trii may append arrows,
    # emphasis words, or minor UI variants to the same semantic signal.
    if "compra" in normalized and "fuerte" in normalized:
        return Signal.STRONG_BUY
    if "venta" in normalized and "fuerte" in normalized:
        return Signal.STRONG_SELL
    if "mantener" in normalized:
        return Signal.HOLD
    if "compra" in normalized:
        return Signal.BUY
    if "venta" in normalized:
        return Signal.SELL

    raise ValueError(f"Señal técnica no soportada: {value}")


def parse_spanish_date(line: str) -> str:
    match = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})\s+(\d{4})", line)
    if not match:
        raise ValueError(f"Could not parse date from line: {line}")
    day = int(match.group(1))
    month_key = normalize_key(match.group(2))[:3]
    month = _SPANISH_MONTHS[month_key]
    year = int(match.group(3))
    return date(year, month, day).isoformat()


def find_line_index(lines: list[str], needle: str) -> int:
    for index, line in enumerate(lines):
        if line == needle:
            return index
    raise ValueError(f"Expected line not found: {needle}")
