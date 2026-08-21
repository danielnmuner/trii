from __future__ import annotations
from datetime import datetime
from html import escape
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st

from backend import BackendConfigurationError, get_backend_client
from trii_ingestion.services import (
    ApiGatewayClientError,
    build_analytics_summary,
    build_historic_z_score_context,
    build_trade_simulation,
    now_in_bogota,
)


@st.cache_data(ttl=60, show_spinner=False)
def _load_analytics_catalog(days: int) -> dict:
    client = get_backend_client()
    return client.get_analytics_catalog(days=days)


@st.cache_data(ttl=60, show_spinner=False)
def _load_analytics_snapshot(symbol: str) -> dict:
    client = get_backend_client()
    return client.get_analytics_snapshot(symbol=symbol)


def _refresh_recent_snapshots_cache() -> None:
    _load_analytics_catalog.clear()
    _load_analytics_snapshot.clear()
    st.session_state["analytics_last_manual_refresh"] = now_in_bogota()


def _safe_float(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_metric_value(metric_key: str, value: float | None) -> str:
    if value is None:
        return "n/a"

    if metric_key in {"spread", "bid_depth_total_5", "ask_depth_total_5", "traded_volume"}:
        return f"{value:,.0f}"
    if metric_key == "traded_value":
        return f"{value:,.0f}"
    if metric_key == "vwap_cumulative":
        return f"{value:,.2f}"
    if metric_key == "daily_change_amount":
        return f"{value:,.2f}"
    if metric_key == "daily_change_percent":
        return f"{(value / 100):,.2f}%"
    if metric_key in {"mid_price", "microprice"}:
        return f"{value:,.2f}"
    if metric_key == "spread_bps":
        return f"{value:,.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{value:,.2f}"
    if metric_key == "depth_weighted_microprice_deviation":
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def _format_cop_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    formatted = f"{round(value):,.0f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {formatted}"


def _format_metric_delta(metric_key: str, current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None:
        return None

    delta = current - previous
    if metric_key == "spread_bps":
        return f"{delta:+.2f} bps"
    if metric_key in {"obi_l1", "obi_top_5", "book_pressure_ratio"}:
        return f"{delta:+.2f}"
    return f"{delta:+,.2f}"


def _compute_cumulative_vwap(record: dict | None) -> float | None:
    if not isinstance(record, dict):
        return None
    traded_value = _safe_float(record, "traded_value")
    traded_volume = _safe_float(record, "traded_volume")
    if traded_value is None or traded_volume in (None, 0):
        return None
    return traded_value / traded_volume


def _format_metric_delta_with_relative(metric_key: str, current: float | None, previous: float | None) -> str | None:
    absolute_delta = _format_metric_delta(metric_key, current, previous)
    if absolute_delta is None or previous in (None, 0):
        return absolute_delta

    relative_delta = ((current - previous) / previous) * 100
    return f"{absolute_delta} ({relative_delta:+.2f}%)"


def _build_market_kpi_definitions() -> list[dict[str, str]]:
    return [
        {"key": "last_price", "label": "Ultimo precio"},
        {"key": "vwap_cumulative", "label": "VWAP acumulado"},
        {"key": "best_prices", "label": "Mejor compra / venta"},
        {"key": "price_range", "label": "Maximo / minimo"},
        {"key": "spread", "label": "Spread"},
        {"key": "traded_volume", "label": "Volumen negociado"},
        {"key": "traded_value", "label": "Valor negociado"},
    ]


def _build_symbol_analytics_groups(
    analytics_payloads: list[dict],
    selected_symbols: list[str],
) -> list[tuple[str, dict, list[dict]]]:
    grouped = {
        str(payload.get("symbol", "")).strip().upper(): payload
        for payload in analytics_payloads
        if str(payload.get("symbol", "")).strip()
    }

    groups: list[tuple[str, dict, list[dict]]] = []
    for symbol in selected_symbols:
        payload = grouped.get(symbol)
        if not payload:
            continue
        records = [
            record
            for record in [
                payload.get("current_snapshot"),
                payload.get("previous_snapshot"),
            ]
            if isinstance(record, dict) and record
        ]
        if records:
            groups.append((symbol, payload, records))

    return groups


def _signal_tone(label: str) -> str:
    normalized = label.strip().lower()
    if normalized == "anomaly":
        return "green"
    if normalized == "review":
        return "blue"
    return "gray"


def _format_signed_cop(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}{_format_cop_price(abs(value))}"


def _sample_count_label(sample_count: int) -> str | None:
    if sample_count <= 0:
        return None
    return f"{sample_count:,}"


def _format_signed_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _format_plain_integer(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{round(float(value)):,}"


def _simulation_driver_tone(tone: str | None) -> str:
    normalized = str(tone or "").strip().lower()
    if normalized == "green":
        return "analytics-simulation-driver-green"
    if normalized == "red":
        return "analytics-simulation-driver-red"
    return "analytics-simulation-driver-gray"


def _format_elapsed_seconds(total_seconds: int) -> str:
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds:02d}s"


def _refresh_tone(total_seconds: int) -> str:
    if total_seconds < 60:
        return "green"
    if total_seconds <= 300:
        return "orange"
    return "red"


def _feed_age_tone(total_seconds: int) -> str:
    if total_seconds > 600:
        return "red"
    if total_seconds > 300:
        return "orange"
    return "green"


def _format_trigger_reason(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("-", " ").replace("_", " ")
    if not normalized:
        return None
    return normalized.title()


def _resolve_symbol_sample_count(current_stats: dict) -> int:
    counts = [
        int(stat_item.get("sample_count", 0) or 0)
        for stat_item in current_stats.values()
        if isinstance(stat_item, dict)
    ]
    return max(counts, default=0)


def _parse_record_timestamp(raw_value: str | None, reference_time: datetime) -> datetime | None:
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=reference_time.tzinfo)
    return parsed.astimezone(reference_time.tzinfo)


def _format_z_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}σ"


def _format_samples(value: int) -> str:
    return f"{value:,}"


def _build_diagnostic_cell(*args: str) -> dict[str, str]:
    if len(args) == 2:
        text, tone = args
        return {"title": "", "text": text, "tone": tone}
    if len(args) == 3:
        title, text, tone = args
        return {"title": title, "text": text, "tone": tone}
    raise ValueError("Unexpected diagnostic cell arguments.")


def _spread_diagnostic(spread_bps: float | None) -> dict[str, str]:
    value_label = _format_metric_value("spread_bps", spread_bps)
    if spread_bps is None:
        return _build_diagnostic_cell(f"No hay lectura operativa de spread disponible; el panel no puede estimar el costo real de entrar al libro ahora mismo ({value_label}).", "gray")
    if spread_bps > 150:
        return _build_diagnostic_cell(
            f"El spread se abrio hasta {value_label}, una señal de liquidez muy limitada: entrar de inmediato implica pagar caro por prioridad y conviene reducir urgencia, tamaño o agresividad.",
            "red",
        )
    if spread_bps <= 30:
        return _build_diagnostic_cell(
            f"El spread se mantiene en {value_label}, un rango eficiente para ejecutar con friccion baja; el libro acompaña decisiones rapidas sin castigar tanto el cruce.",
            "green",
        )
    return _build_diagnostic_cell(
        f"El spread marca {value_label}, un punto intermedio: el mercado sigue siendo operable, pero no ofrece una ventaja clara de costo si necesitas entrar con urgencia.",
        "blue",
    )


def _obi_l1_diagnostic(obi_l1: float | None, obi_top_5: float | None) -> dict[str, str]:
    l1_label = _format_metric_value("obi_l1", obi_l1)
    top5_label = _format_metric_value("obi_top_5", obi_top_5)
    if obi_l1 is None:
        return _build_diagnostic_cell(f"No hay una lectura valida de presion en punta; sin OBI L1 el panel no puede concluir si la mejor postura favorece compra o venta ({l1_label}).", "gray")
    if obi_l1 > 0.6:
        return _build_diagnostic_cell(
            f"El libro muestra dominio comprador en punta con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la demanda visible sostiene la mejor compra y favorece continuidad alcista de muy corto plazo.",
            "green",
        )
    if obi_l1 < -0.6:
        return _build_diagnostic_cell(
            f"El libro muestra dominio vendedor en punta con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la oferta visible presiona la mejor venta y aumenta el riesgo de continuation bajista inmediata.",
            "red",
        )
    return _build_diagnostic_cell(
        f"El libro luce equilibrado con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la punta no muestra un sesgo dominante y conviene esperar confirmacion antes de leer direccion.",
        "blue",
    )


def _microprice_diagnostic(delta_micro: float | None) -> dict[str, str]:
    value_label = _format_metric_value("depth_weighted_microprice_deviation", delta_micro)
    if delta_micro is None:
        return _build_diagnostic_cell(f"No hay referencia valida de microprice frente al mid; sin ese delta el panel no puede medir si la masa visible empuja el precio justo ({value_label}).", "gray")
    if delta_micro < 0:
        return _build_diagnostic_cell(
            f"El microprice cae {value_label} por debajo del mid, lo que sugiere que la masa visible en L1 empuja el precio justo hacia abajo y favorece sesgo bajista inmediato.",
            "red",
        )
    if delta_micro > 0:
        return _build_diagnostic_cell(
            f"El microprice supera el mid en {value_label}, señal de que la masa visible en L1 empuja el precio justo hacia arriba y respalda sesgo alcista inmediato.",
            "green",
        )
    return _build_diagnostic_cell(
        f"El microprice y el mid permanecen practicamente alineados ({value_label}), de modo que la punta no transmite una inclinacion clara en este instante.",
        "blue",
    )


def _vwap_diagnostic(last_price: float | None, vwap_value: float | None) -> dict[str, str]:
    delta_vwap = None if last_price is None or vwap_value is None else last_price - vwap_value
    if delta_vwap is None:
        return _build_diagnostic_cell("No hay comparacion valida contra VWAP acumulado; sin valor y volumen negociado consistentes el panel no puede saber si el precio cotiza con prima o descuento.", "gray")
    value_label = _format_metric_value("depth_weighted_microprice_deviation", delta_vwap)
    if delta_vwap > 0:
        return _build_diagnostic_cell(
            f"El ultimo precio se negocia {value_label} por encima del VWAP acumulado, una señal de que el mercado sigue pagando prima frente al promedio efectivo de la sesion.",
            "green",
        )
    if delta_vwap < 0:
        return _build_diagnostic_cell(
            f"El ultimo precio se negocia {value_label} por debajo del VWAP acumulado, una señal de descuento frente al flujo efectivo de la sesion y menor disposicion a pagar arriba.",
            "red",
        )
    return _build_diagnostic_cell(
        f"El ultimo precio se mantiene alineado con el VWAP acumulado ({value_label}), lo que sugiere que la sesion sigue negociando cerca de su promedio ponderado.",
        "blue",
    )


def _z_spread_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return _build_diagnostic_cell(
            f"Aun no hay suficiente historial para juzgar si el spread actual es anomalo; la muestra disponible ({_format_samples(sample_count)}) todavia no sostiene una lectura estadistica confiable.",
            "gray",
        )
    if z_score >= 2.0:
        return _build_diagnostic_cell(
            f"El spread corre en {_format_z_score(z_score)}, muy por encima de su rango habitual, y eso sugiere un costo de entrada anormalmente alto para este simbolo en este momento.",
            "red",
        )
    if z_score <= -2.0:
        return _build_diagnostic_cell(
            f"El spread corre en {_format_z_score(z_score)}, una compresion extrema frente a su historia; el libro esta mas cerrado de lo normal y puede estar preparando un movimiento direccional.",
            "green",
        )
    return _build_diagnostic_cell(
        f"El spread se mantiene en {_format_z_score(z_score)} frente a su historia reciente, de modo que el costo de ejecucion sigue dentro del comportamiento estadisticamente esperado.",
        "blue",
    )


def _z_obi5_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return _build_diagnostic_cell(
            f"Aun no hay suficiente historial para decidir si la profundidad visible es inusual; la muestra disponible ({_format_samples(sample_count)}) no alcanza para una lectura estadistica estable.",
            "gray",
        )
    if z_score >= 2.0:
        return _build_diagnostic_cell(
            f"El OBI Top 5 corre en {_format_z_score(z_score)}, señal de acumulacion compradora atipica: la profundidad en compra supera con claridad su patron habitual.",
            "green",
        )
    if z_score <= -2.0:
        return _build_diagnostic_cell(
            f"El OBI Top 5 corre en {_format_z_score(z_score)}, señal de acumulacion vendedora atipica: la profundidad en venta supera con claridad su patron habitual.",
            "red",
        )
    return _build_diagnostic_cell(
        f"El OBI Top 5 marca {_format_z_score(z_score)}, una lectura que sigue dentro de rango y no muestra una distorsion estadistica fuerte en la profundidad visible.",
        "blue",
    )


def _spoofing_risk_diagnostic(obi_l1: float | None, delta_micro: float | None, z_spread: float | None) -> dict[str, str]:
    if obi_l1 is None or delta_micro is None or z_spread is None:
        return _build_diagnostic_cell("Todavia faltan señales para decidir si la punta puede estar enviando una impresión engañosa; sin conflicto suficiente entre libro y spread no conviene sobrerreaccionar.", "gray")
    if obi_l1 > 0.5 and delta_micro < 0 and z_spread >= 1.5:
        return _build_diagnostic_cell(
            "La punta parece compradora, pero la profundidad y el spread la contradicen; este desacople es compatible con una trampa de liquidez y amerita revisar antes de perseguir la señal.",
            "red",
        )
    return _build_diagnostic_cell(
        f"La punta, la profundidad y el spread no muestran un conflicto severo; por ahora el libro no exhibe la clase de desacople que suele levantar sospecha de trampa de liquidez.",
        "blue",
    )


def _stale_data_diagnostic(lag_seconds: int | None) -> dict[str, str]:
    if lag_seconds is None:
        return _build_diagnostic_cell("No fue posible medir la latencia del feed, así que esta lectura debe tratarse con cautela hasta confirmar que el snapshot realmente corresponde al estado actual del mercado.", "gray")
    if lag_seconds > 300:
        return _build_diagnostic_cell(
            f"El snapshot llega con un rezago de {_format_elapsed_seconds(lag_seconds)}, suficiente para degradar una lectura de corto plazo; antes de actuar conviene asumir que el mercado pudo haber cambiado.",
            "red",
        )
    return _build_diagnostic_cell(f"El feed mantiene un rezago de {_format_elapsed_seconds(lag_seconds)}, todavía razonable para lectura táctica; la información sigue siendo útil para una decisión inmediata.", "green")


def _format_z_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}{chr(963)}"


def _spread_diagnostic(spread_bps: float | None) -> dict[str, str]:
    value_label = _format_metric_value("spread_bps", spread_bps)
    if spread_bps is None:
        return _build_diagnostic_cell(
            "Spread relativo",
            f"No hay una lectura operativa valida del spread en este instante, asi que el panel no puede estimar con disciplina el costo real de cruzar el libro ahora mismo ({value_label}).",
            "gray",
        )
    if spread_bps > 150:
        return _build_diagnostic_cell(
            "Spread relativo",
            f"El spread se abrio hasta {value_label}; la entrada pierde eficiencia y conviene bajar urgencia, trabajar el precio con mas paciencia o reducir agresividad antes de cruzar el libro.",
            "red",
        )
    if spread_bps <= 30:
        return _build_diagnostic_cell(
            "Spread relativo",
            f"El spread se mantiene en {value_label}; el costo de cruce sigue contenido y el libro ofrece una ventana razonable para ejecutar rapido sin castigar tanto el punto de entrada.",
            "green",
        )
    return _build_diagnostic_cell(
        "Spread relativo",
        f"El spread marca {value_label}; el mercado sigue siendo operable, pero no entrega una ventaja clara de costo y todavia conviene evitar perseguir precio sin una confirmacion adicional.",
        "blue",
    )


def _obi_l1_diagnostic(obi_l1: float | None, obi_top_5: float | None) -> dict[str, str]:
    l1_label = _format_metric_value("obi_l1", obi_l1)
    top5_label = _format_metric_value("obi_top_5", obi_top_5)
    if obi_l1 is None:
        return _build_diagnostic_cell(
            "Presion en punta",
            f"No hay una lectura valida de presion en punta; sin OBI L1 el panel no puede concluir si la mejor postura favorece compra o venta ({l1_label}).",
            "gray",
        )
    if obi_l1 > 0.6:
        return _build_diagnostic_cell(
            "Presion en punta",
            f"El libro muestra dominio comprador con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la demanda visible sostiene la mejor compra y favorece continuidad alcista de muy corto plazo.",
            "green",
        )
    if obi_l1 < -0.6:
        return _build_diagnostic_cell(
            "Presion en punta",
            f"El libro muestra dominio vendedor con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la oferta visible presiona la mejor venta y aumenta el riesgo de continuidad bajista inmediata.",
            "red",
        )
    return _build_diagnostic_cell(
        "Presion en punta",
        f"El libro luce equilibrado con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la punta no muestra un sesgo dominante y conviene esperar confirmacion antes de leer direccion con conviccion.",
        "blue",
    )


def _microprice_diagnostic(delta_micro: float | None) -> dict[str, str]:
    value_label = _format_metric_value("depth_weighted_microprice_deviation", delta_micro)
    if delta_micro is None:
        return _build_diagnostic_cell(
            "Microprice vs mid",
            f"No hay referencia valida de microprice frente al mid; sin ese delta el panel no puede medir si la masa visible empuja el precio justo ({value_label}).",
            "gray",
        )
    if delta_micro < 0:
        return _build_diagnostic_cell(
            "Microprice vs mid",
            f"El microprice cae {value_label} por debajo del mid; la masa visible en L1 empuja el precio justo hacia abajo y debilita cualquier lectura compradora demasiado optimista.",
            "red",
        )
    if delta_micro > 0:
        return _build_diagnostic_cell(
            "Microprice vs mid",
            f"El microprice supera el mid en {value_label}; la masa visible en L1 empuja el precio justo hacia arriba y respalda un sesgo alcista inmediato con mejor fundamento.",
            "green",
        )
    return _build_diagnostic_cell(
        "Microprice vs mid",
        f"El microprice y el mid permanecen practicamente alineados ({value_label}); la punta no transmite una inclinacion clara y el libro sigue neutral en el margen.",
        "blue",
    )


def _vwap_diagnostic(last_price: float | None, vwap_value: float | None) -> dict[str, str]:
    delta_vwap = None if last_price is None or vwap_value is None else last_price - vwap_value
    if delta_vwap is None:
        return _build_diagnostic_cell(
            "Precio vs VWAP",
            "No hay comparacion valida contra VWAP acumulado; sin valor y volumen negociado consistentes el panel no puede saber si el precio cotiza con prima o descuento.",
            "gray",
        )
    value_label = _format_metric_value("depth_weighted_microprice_deviation", delta_vwap)
    if delta_vwap > 0:
        return _build_diagnostic_cell(
            "Precio vs VWAP",
            f"El ultimo precio se negocia {value_label} por encima del VWAP acumulado; el mercado sigue pagando prima frente al promedio efectivo de la sesion y no esta soltando precio con facilidad.",
            "green",
        )
    if delta_vwap < 0:
        return _build_diagnostic_cell(
            "Precio vs VWAP",
            f"El ultimo precio se negocia {value_label} por debajo del VWAP acumulado; hay descuento frente al flujo efectivo de la sesion y menor disposicion a seguir pagando arriba.",
            "red",
        )
    return _build_diagnostic_cell(
        "Precio vs VWAP",
        f"El ultimo precio se mantiene alineado con el VWAP acumulado ({value_label}); la sesion sigue balanceada alrededor de su promedio ponderado sin prima ni castigo claros.",
        "blue",
    )


def _z_spread_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return _build_diagnostic_cell(
            "Z-Score spread",
            f"Muestra aun insuficiente ({_format_samples(sample_count)}) para decidir si el spread actual ya se salio de su rango historico confiable.",
            "gray",
        )
    if z_score >= 2.0:
        return _build_diagnostic_cell(
            "Z-Score spread",
            f"El spread corre en {_format_z_score(z_score)} y el costo de entrada ya esta muy por encima de su rango normal; antes de ejecutar conviene revisar con mas disciplina.",
            "red",
        )
    if z_score <= -2.0:
        return _build_diagnostic_cell(
            "Z-Score spread",
            f"El spread corre en {_format_z_score(z_score)} y el libro esta mas cerrado de lo normal; la ejecucion luce especialmente competitiva en este momento.",
            "green",
        )
    return _build_diagnostic_cell(
        "Z-Score spread",
        f"El spread marca {_format_z_score(z_score)} y el costo de ejecucion sigue dentro del comportamiento estadisticamente esperado para la jornada.",
        "blue",
    )


def _z_obi5_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return _build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"Muestra aun insuficiente ({_format_samples(sample_count)}) para decidir si la profundidad visible ya es estadisticamente inusual.",
            "gray",
        )
    if z_score >= 2.0:
        return _build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"El OBI Top 5 corre en {_format_z_score(z_score)} y la acumulacion compradora ya supera con claridad su patron habitual.",
            "green",
        )
    if z_score <= -2.0:
        return _build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"El OBI Top 5 corre en {_format_z_score(z_score)} y la acumulacion vendedora ya supera con claridad su patron habitual.",
            "red",
        )
    return _build_diagnostic_cell(
        "Z-Score OBI Top 5",
        f"El OBI Top 5 marca {_format_z_score(z_score)} y la profundidad visible sigue dentro de rango sin una distorsion estadistica fuerte.",
        "blue",
    )


def _spoofing_risk_diagnostic(obi_l1: float | None, delta_micro: float | None, z_spread: float | None) -> dict[str, str]:
    if obi_l1 is None or delta_micro is None or z_spread is None:
        return _build_diagnostic_cell(
            "Riesgo de spoofing",
            "Todavia faltan senales para decidir si la punta puede estar enviando una impresion enganosa; por ahora no hay base suficiente para elevar esta alerta.",
            "gray",
        )
    if obi_l1 > 0.5 and delta_micro < 0 and z_spread >= 1.5:
        return _build_diagnostic_cell(
            "Riesgo de spoofing",
            "La punta parece compradora, pero la profundidad y el spread la contradicen; este desacople es compatible con una trampa de liquidez y merece revision inmediata.",
            "red",
        )
    return _build_diagnostic_cell(
        "Riesgo de spoofing",
        "La punta, la profundidad y el spread no muestran un conflicto severo; por ahora el libro no exhibe un desacople que sugiera trampa de liquidez.",
        "blue",
    )


def _stale_data_diagnostic(lag_seconds: int | None) -> dict[str, str]:
    if lag_seconds is None:
        return _build_diagnostic_cell(
            "Latencia operativa",
            "No fue posible medir la latencia del feed; esta lectura debe tratarse con cautela hasta confirmar que el snapshot sigue vigente.",
            "gray",
        )
    if lag_seconds > 300:
        return _build_diagnostic_cell(
            "Latencia operativa",
            f"El snapshot llega con un rezago de {_format_elapsed_seconds(lag_seconds)}; para corto plazo ya no conviene asumir que el mercado sigue igual.",
            "red",
        )
    return _build_diagnostic_cell(
        "Latencia operativa",
        f"El feed mantiene un rezago de {_format_elapsed_seconds(lag_seconds)} y la informacion sigue siendo util para una decision tactica inmediata.",
        "green",
    )


def _build_diagnostic_cells(module_key: str, payload: dict, records: list[dict]) -> list[dict[str, str]]:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    current_stats = payload.get("current_stats", {})
    current_time = now_in_bogota()
    latest_timestamp = _parse_record_timestamp(str(latest_record.get("captured_at") or ""), current_time)
    lag_seconds = None if latest_timestamp is None else max(int((current_time - latest_timestamp).total_seconds()), 0)

    spread_bps = _safe_float(latest_record, "spread_bps")
    obi_l1 = _safe_float(latest_record, "obi_l1")
    obi_top_5 = _safe_float(latest_record, "obi_top_5")
    delta_micro = _safe_float(latest_record, "depth_weighted_microprice_deviation")
    last_price = _safe_float(latest_record, "last_price")
    vwap_value = _compute_cumulative_vwap(latest_record)
    z_spread_context = build_historic_z_score_context(current_stats.get("spread_bps"))

    modules = {
        "execution": [
            _spread_diagnostic(spread_bps),
            _obi_l1_diagnostic(obi_l1, obi_top_5),
            _microprice_diagnostic(delta_micro),
            _vwap_diagnostic(last_price, vwap_value),
        ],
        "alerts": [
            _z_spread_diagnostic(current_stats.get("spread_bps")),
            _z_obi5_diagnostic(current_stats.get("obi_top_5")),
            _spoofing_risk_diagnostic(obi_l1, delta_micro, z_spread_context["z_score"]),
            _stale_data_diagnostic(lag_seconds),
        ],
    }
    return modules[module_key]


def _render_diagnostic_reference(section_key: str) -> None:
    if section_key == "execution":
        references = [
            {
                "title": "Spread relativo",
                "formula_lines": [
                    r"\text{Mid Price}=\frac{P_{ask}+P_{bid}}{2}",
                    r"\text{Spread BPS}=\left(\frac{P_{ask}-P_{bid}}{\text{Mid Price}}\right)\times10{,}000",
                ],
                "rule_lines": [
                    r"\text{Spread BPS}>150\Rightarrow\text{Iliquidez Alta}",
                    r"\text{Spread BPS}\leq30\Rightarrow\text{Liquidez Alta}",
                    r"\text{Otro}\Rightarrow\text{Spread Normal}",
                ],
                "info": "Prioriza esta lectura cuando necesites decidir si puedes ejecutar rapido o si el costo de cruce ya es demasiado alto; si el spread expresado en basis points (BPS) se abre, la orden a mercado pierde calidad aunque el sesgo del libro luzca atractivo.",
            },
            {
                "title": "Presion del libro",
                "formula_lines": [
                    r"\text{OBI}_{L1}=\frac{V_{bid,1}-V_{ask,1}}{V_{bid,1}+V_{ask,1}}",
                    r"\text{OBI}_{Top5}=\frac{\sum_{i=1}^{5}V_{bid,i}-\sum_{i=1}^{5}V_{ask,i}}{\sum_{i=1}^{5}V_{bid,i}+\sum_{i=1}^{5}V_{ask,i}}",
                ],
                "rule_lines": [
                    r"\text{OBI}_{L1}>0.6\Rightarrow\text{Fuerte Compra}",
                    r"\text{OBI}_{L1}<-0.6\Rightarrow\text{Fuerte Venta}",
                    r"\text{Otro}\Rightarrow\text{Punta Balanceada}",
                ],
                "info": "Usa esta metrica para leer quien manda en la punta y si ese dominio se sostiene en profundidad; Order Book Imbalance (OBI) de nivel 1 y de Top 5 ayuda a distinguir entre interes real y un libro aparentemente cargado pero poco consistente.",
            },
            {
                "title": "Microprice delta",
                "formula_lines": [
                    r"\text{Microprice}=\frac{V_{bid,1}\cdot P_{ask}+V_{ask,1}\cdot P_{bid}}{V_{bid,1}+V_{ask,1}}",
                    r"\Delta_{micro}=\text{Microprice}-\text{Mid Price}",
                ],
                "rule_lines": [
                    r"\Delta_{micro}<0\Rightarrow\text{Sesgo Bajista}",
                    r"\Delta_{micro}>0\Rightarrow\text{Sesgo Alcista}",
                    r"\Delta_{micro}=0\Rightarrow\text{Sesgo Neutral}",
                ],
                "info": "Toma esta lectura como una validacion de masa en nivel 1 (L1): si el microprice empuja por debajo del mid, la liquidez visible favorece presion vendedora; si empuja arriba, favorece continuidad compradora.",
            },
            {
                "title": "Precio vs VWAP",
                "formula_lines": [
                    r"\text{VWAP}_{acumulado}=\frac{\text{Valor Negociado}}{\text{Volumen Negociado}}",
                    r"\Delta_{VWAP}=P_{ultimo}-\text{VWAP}_{acumulado}",
                ],
                "rule_lines": [
                    r"\Delta_{VWAP}>0\Rightarrow\text{Sobre Promedio}",
                    r"\Delta_{VWAP}<0\Rightarrow\text{Bajo Promedio}",
                    r"\Delta_{VWAP}=0\Rightarrow\text{En Promedio}",
                ],
                "info": "Esta comparacion te dice si el precio actual se esta negociando con prima o con descuento frente al volumen weighted average price (VWAP) acumulado de la jornada; ayuda a separar impulsos genuinos de movimientos que ya vienen cansados.",
            },
        ]
    else:
        references = [
            {
                "title": "Z-Score spread BPS",
                "formula_lines": [
                    r"Z_{spread}=\frac{\text{Spread BPS}-\mu_{spread}}{\sigma_{spread}}",
                ],
                "rule_lines": [
                    r"Z_{spread}\geq2.0\Rightarrow\text{Spread Fuera De Rango}",
                    r"Z_{spread}\leq-2.0\Rightarrow\text{Compresion Extrema}",
                    r"\text{Otro}\Rightarrow\text{Rango Normal}",
                ],
                "info": "Dale prioridad alta cuando el costo de entrada cambia de forma atipica frente a su propia historia, porque un spread expresado en basis points (BPS) fuera de rango puede invalidar una operacion buena en direccion pero mala en ejecucion.",
            },
            {
                "title": "Z-Score OBI Top 5",
                "formula_lines": [
                    r"Z_{OBI5}=\frac{\text{OBI}_{Top5}-\mu_{OBI5}}{\sigma_{OBI5}}",
                ],
                "rule_lines": [
                    r"Z_{OBI5}\geq2.0\Rightarrow\text{Carga Compradora Anomala}",
                    r"Z_{OBI5}\leq-2.0\Rightarrow\text{Carga Vendedora Anomala}",
                    r"\text{Otro}\Rightarrow\text{Profundidad Normal}",
                ],
                "info": "Prioriza esta lectura para detectar cuando Order Book Imbalance (OBI) de Top 5 deja de ser normal para ese simbolo y empieza a parecer una carga institucional o una salida agresiva que merece seguimiento inmediato.",
            },
            {
                "title": "Riesgo de spoofing",
                "formula_lines": [
                    r"\text{OBI}_{L1}>0.5\land\Delta_{micro}<0\land Z_{spread}\geq1.5",
                ],
                "rule_lines": [
                    r"\text{Condicion Verdadera}\Rightarrow\text{Alerta De Trampa}",
                    r"\text{Condicion Falsa}\Rightarrow\text{Sin Senal Activa}",
                ],
                "info": "Esta regla sirve para no perseguir una punta aparentemente compradora que en realidad esta siendo contradicha por la profundidad y por un spread mas riesgoso; si aparece, la prioridad debe ser revisar antes de ejecutar porque el Order Book Imbalance (OBI) de nivel 1 y el microprice estan desacoplados.",
            },
            {
                "title": "Latencia operativa",
                "formula_lines": [
                    r"\text{Lag}=t_{actual}-t_{ultimo\ snapshot}",
                ],
                "rule_lines": [
                    r"\text{Lag}>300s\Rightarrow\text{Dato Envejecido}",
                    r"\text{Otro}\Rightarrow\text{Feed Vigente}",
                ],
                "info": "Esta lectura no habla del mercado sino de la calidad del dato disponible; si el lag crece, cualquier senal de corto plazo pierde valor operativo y debe tratarse con cautela aunque el resto del panel luzca bien, incluso si el feed parece consistente.",
            },
        ]

    cards_markup = []
    for entry in references:
        formula_markup = "".join(
            (
                "<div class='analytics-reference-math-line'>"
                f"\\({escape(formula_line)}\\)"
                "</div>"
            )
            for formula_line in entry["formula_lines"]
        )
        rules_latex = (
            r"\left\{\begin{array}{l}"
            + r" \\ ".join(entry["rule_lines"])
            + r"\end{array}\right."
        )
        rules_markup = (
            "<div class='analytics-reference-rule-line analytics-reference-rule-block'>"
            f"\\[{rules_latex}\\]"
            "</div>"
        )
        cards_markup.append(
            (
                "<div class='analytics-reference-band-item'>"
                f"<div class='analytics-reference-card-title'>{escape(entry['title'])}</div>"
                "<div class='analytics-reference-block-label'>Formula</div>"
                f"<div class='analytics-reference-formula-block'>{formula_markup}</div>"
                "<div class='analytics-reference-block-label'>Reglas</div>"
                f"<div class='analytics-reference-rules-block'>{rules_markup}</div>"
                "<div class='analytics-reference-block-label'>Description</div>"
                f"<div class='analytics-reference-card-copy'>{escape(entry['info'])}</div>"
                "</div>"
            )
        )

    component_height = 260 if section_key == "execution" else 235
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <script>
          window.MathJax = {{
            tex: {{
              inlineMath: [['\\\\(', '\\\\)']],
              displayMath: [['\\\\[', '\\\\]']],
              processEscapes: true
            }},
            svg: {{
              fontCache: 'none'
            }}
          }};
        </script>
        <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
        <style>
          :root {{
            color-scheme: light;
          }}
          body {{
            margin: 0;
            background: transparent;
            font-family: "Source Sans 3", sans-serif;
          }}
          .analytics-reference-band {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            border: 1px solid rgba(8, 33, 20, 0.10);
            border-radius: 10px;
            overflow: hidden;
            background: #ffffff;
          }}
          .analytics-reference-band-item {{
            min-width: 0;
            padding: 0.55rem 0.78rem 0.58rem 0.78rem;
          }}
          .analytics-reference-band-item + .analytics-reference-band-item {{
            border-left: 1px solid rgba(8, 33, 20, 0.10);
          }}
          .analytics-reference-card-title {{
            margin-bottom: 0.24rem;
            font-size: 0.48rem;
            line-height: 1.1;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #6f7a83;
          }}
          .analytics-reference-block-label {{
            margin: 0.12rem 0 0.08rem 0;
            font-size: 0.40rem;
            line-height: 1;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(8, 33, 20, 0.42);
          }}
          .analytics-reference-formula-block,
          .analytics-reference-rules-block {{
            display: flex;
            flex-direction: column;
            gap: 0.08rem;
            padding: 0.12rem 0;
          }}
          .analytics-reference-math-line,
          .analytics-reference-rule-line {{
            width: 100%;
            overflow-x: auto;
            overflow-y: hidden;
            white-space: nowrap;
            text-align: center;
            padding: 0.04rem 0;
          }}
          .analytics-reference-math-line {{
            border-bottom: 1px solid rgba(8, 33, 20, 0.06);
          }}
          .analytics-reference-math-line:last-child {{
            border-bottom: none;
          }}
          .analytics-reference-rule-line {{
            color: #6b7883;
            text-align: center;
            padding-left: 0;
          }}
          .analytics-reference-rule-block {{
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 3.2rem;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 0.06rem 0 0.02rem 0;
          }}
          .analytics-reference-card-copy {{
            margin-top: 0.18rem;
            font-size: 0.44rem;
            line-height: 1.28;
            font-weight: 400;
            color: #5f6971;
          }}
          .analytics-reference-math-line mjx-container {{
            margin: 0 !important;
            font-size: 66% !important;
          }}
          .analytics-reference-rule-line mjx-container {{
            margin: 0 !important;
            font-size: 46% !important;
          }}
        </style>
      </head>
      <body>
        <div class="analytics-reference-band">
          {''.join(cards_markup)}
        </div>
      </body>
    </html>
    """
    st.html(
        html,
        width="stretch",
        unsafe_allow_javascript=True,
    )


def _render_diagnostic_board(
    symbol_record_groups: list[tuple[str, dict, list[dict]]],
    section_key: str,
    section_caption: str,
) -> None:
    st.markdown(
        f"<div class='analytics-diagnostic-caption'>{escape(section_caption)}</div>",
        unsafe_allow_html=True,
    )
    for symbol, payload, records in symbol_record_groups:
        cells = _build_diagnostic_cells(section_key, payload, records)
        if section_key == "execution":
            symbol_markup = (
                "<div class='analytics-light-tape-item analytics-light-tape-symbol analytics-diagnostic-symbol-item'>"
                f"<div class='analytics-light-tape-main'>{escape(symbol)}</div>"
                "</div>"
            )
            cells_markup = "".join(
                (
                    "<div class='analytics-light-tape-item analytics-diagnostic-light-item'>"
                    f"<div class='analytics-diagnostic-title analytics-diagnostic-title-light'>{escape(cell['title'])}</div>"
                    f"<div class='analytics-diagnostic-copy analytics-diagnostic-copy-light'>{escape(cell['text'])}</div>"
                    "</div>"
                )
                for cell in cells
            )
            st.markdown(
                "<div class='analytics-light-tape analytics-diagnostic-strip'>"
                + symbol_markup
                + cells_markup
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            symbol_markup = (
                "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-diagnostic-symbol-item-dark'>"
                f"<div class='analytics-market-tape-main'>{escape(symbol)}</div>"
                "</div>"
            )
            cells_markup = "".join(
                (
                    "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-diagnostic-dark-item'>"
                    f"<div class='analytics-diagnostic-title analytics-diagnostic-title-dark'>{escape(cell['title'])}</div>"
                    f"<div class='analytics-diagnostic-copy analytics-diagnostic-copy-dark'>{escape(cell['text'])}</div>"
                    "</div>"
                )
                for cell in cells
            )
            st.markdown(
                "<div class='analytics-market-tape analytics-diagnostic-strip analytics-diagnostic-strip-dark'>"
                + symbol_markup
                + cells_markup
                + "</div>",
                unsafe_allow_html=True,
            )
    _render_diagnostic_reference(section_key)



def _render_microstructure_tape(symbol: str, payload: dict, records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    current_stats = payload.get("current_stats", {})
    symbol_sample_count = _resolve_symbol_sample_count(current_stats)
    symbol_sample_count_markup = (
        ""
        if symbol_sample_count <= 0
        else f"<div class='analytics-light-tape-sub'>{escape(_sample_count_label(symbol_sample_count) or '')}</div>"
    )
    items: list[str] = [
        (
            "<div class='analytics-light-tape-item analytics-light-tape-symbol'>"
            f"<div class='analytics-light-tape-main'>{escape(symbol)}</div>"
            f"{symbol_sample_count_markup}"
            "</div>"
        )
    ]

    for key, label in (
        ("obi_l1", "OBI L1"),
        ("obi_top_5", "OBI TOP 5"),
        ("spread_bps", "SPREAD BPS"),
        ("mid_price", "MID PRICE"),
        ("microprice", "MICROPRICE"),
    ):
        current_value = _safe_float(latest_record, key)
        previous_value = _safe_float(previous_record, key) if previous_record else None
        delta = _format_metric_delta_with_relative(key, current_value, previous_value) or "No prior point"
        z_score_markup = ""

        if key in {"obi_l1", "obi_top_5", "spread_bps"}:
            z_score_context = build_historic_z_score_context(current_stats.get(key))
            z_score_value = z_score_context["z_score"]
            z_score_label = None if z_score_value is None else f"{z_score_value:+.1f}"
            signal_label = z_score_context["signal_label"]
            z_score_markup = "".join(
                [
                    "<div class='analytics-light-tape-zscore-stack'>",
                    (
                        ""
                        if z_score_label is None
                        else f"<span class='analytics-light-tape-zscore'>{escape(z_score_label)}&sigma;</span>"
                    ),
                    "<div class='analytics-light-tape-zmeta'>",
                    (
                        ""
                        if signal_label is None
                        else f"<span class='analytics-light-tape-zmeta-line analytics-light-tape-zmeta-line-{_signal_tone(str(signal_label))}'>"
                        f"{escape(str(signal_label))}</span>"
                    ),
                    "</div>",
                    "</div>",
                ]
            )

        items.append(
            "".join(
                [
                    "<div class='analytics-light-tape-item'>",
                    "<div class='analytics-light-tape-eyebrow'>",
                    "<span class='analytics-light-tape-dot'></span>",
                    f"<span class='analytics-light-tape-label'>{escape(label)}</span>",
                    "</div>",
                    (
                        "<div class='analytics-light-tape-main-row'>"
                        f"<div class='analytics-light-tape-main'>{escape(_format_metric_value(key, current_value))}</div>"
                        f"{z_score_markup}"
                        "</div>"
                    ),
                    f"<div class='analytics-light-tape-sub'>{escape(delta)}</div>",
                    "</div>",
                ]
            )
        )

    st.markdown(
        "<div class='analytics-light-tape'>"
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_market_tape(records: list[dict]) -> None:
    latest_record = records[0]
    previous_record = records[1] if len(records) > 1 else None
    items: list[str] = []

    for metric in _build_market_kpi_definitions():
        metric_key = metric["key"]
        current_value = (
            _compute_cumulative_vwap(latest_record)
            if metric_key == "vwap_cumulative"
            else _safe_float(latest_record, metric_key)
        )
        tone = "neutral"

        if metric_key == "last_price":
            previous_value = _safe_float(latest_record, "previous_close")
            delta = _format_metric_delta(metric_key, current_value, previous_value)
            if current_value is not None and previous_value is not None:
                tone = "positive" if current_value >= previous_value else "negative"

            daily_change_percent = _safe_float(latest_record, "daily_change_percent")
            percent_markup = ""
            if daily_change_percent is not None:
                percent_value = daily_change_percent / 100
                percent_tone = "positive" if percent_value >= 0 else "negative"
                percent_markup = (
                    f"<span class='analytics-market-tape-inline-percent analytics-market-tape-inline-percent-{percent_tone}'>"
                    f"({escape(_format_metric_value('daily_change_percent', daily_change_percent))})</span>"
                )

            delta_markup = "".join(
                [
                    f"<span>{escape(delta or 'No prior point')}</span>",
                    percent_markup,
                ]
            )

            items.append(
                "".join(
                    [
                        f"<div class='analytics-market-tape-item analytics-market-tape-item-{tone}'>",
                        "<div class='analytics-market-tape-eyebrow'>",
                        f"<span class='analytics-market-tape-label'>{escape(metric['label'])}</span>",
                        "</div>",
                        f"<div class='analytics-market-tape-main'>{escape(_format_metric_value(metric_key, current_value))}</div>",
                        f"<div class='analytics-market-tape-sub analytics-market-tape-sub-inline'>{delta_markup}</div>",
                        "</div>",
                    ]
                )
            )
            continue

        if metric_key in {"traded_volume", "traded_value"}:
            previous_value = _safe_float(previous_record, metric_key) if previous_record else None
            delta = _format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "vwap_cumulative":
            previous_value = _compute_cumulative_vwap(previous_record)
            delta = _format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "spread":
            previous_value = _safe_float(previous_record, metric_key) if previous_record else None
            delta = _format_metric_delta_with_relative(metric_key, current_value, previous_value)
            tone = "market"
        elif metric_key == "best_prices":
            best_bid_price = _safe_float(latest_record, "best_bid_price")
            best_ask_price = _safe_float(latest_record, "best_ask_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor compra</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(best_bid_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Mejor venta</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(best_ask_price))}</div>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
            continue
        elif metric_key == "price_range":
            high_price = _safe_float(latest_record, "high_price")
            low_price = _safe_float(latest_record, "low_price")
            items.append(
                "".join(
                    [
                        "<div class='analytics-market-tape-item analytics-market-tape-item-market analytics-market-tape-item-paired'>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio maximo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(high_price))}</div>",
                        "</div>",
                        "<div class='analytics-market-tape-pair'>",
                        "<div class='analytics-market-tape-pair-label'>Precio minimo</div>",
                        f"<div class='analytics-market-tape-pair-value'>{escape(_format_cop_price(low_price))}</div>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
            continue
        else:
            delta = None

        items.append(
            "".join(
                [
                    f"<div class='analytics-market-tape-item analytics-market-tape-item-{tone}'>",
                    "<div class='analytics-market-tape-eyebrow'>",
                    f"<span class='analytics-market-tape-label'>{escape(metric['label'])}</span>",
                    "</div>",
                    f"<div class='analytics-market-tape-main'>{escape(_format_metric_value(metric['key'], current_value))}</div>",
                    f"<div class='analytics-market-tape-sub'>{escape(delta or 'No prior point')}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(
        "<div class='analytics-market-tape'>"
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_market_ai_recommendation(payload: dict) -> None:
    recommendation = payload.get("market_ai_recommendation")
    if not isinstance(recommendation, dict) or not recommendation:
        return

    summary = str(recommendation.get("recommendation_summary") or "").strip()
    if not summary:
        return

    status = str(recommendation.get("recommendation_status") or "placeholder").strip().lower()
    triggered_rules = [
        str(rule).strip()
        for rule in recommendation.get("triggered_rules", [])
        if str(rule).strip()
    ]
    status_label = {
        "generated": "AI generated",
        "failed": "AI failed",
        "placeholder": "AI placeholder",
    }.get(status, "AI signal")
    rules_label = ", ".join(triggered_rules) if triggered_rules else "No rules"

    st.markdown(
        (
            "<div class='analytics-recommendation-strip'>"
            "<div class='analytics-recommendation-strip-header'>"
            f"<span class='analytics-recommendation-strip-badge'>{escape(status_label)}</span>"
            f"<span class='analytics-recommendation-strip-rules'>{escape(rules_label)}</span>"
            "</div>"
            f"<div class='analytics-recommendation-strip-body'>{escape(summary)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_simulation_strip(payload: dict, records: list[dict]) -> None:
    simulation = build_trade_simulation(payload, records)
    buy_plan = simulation.get("buy_plan")
    sell_plan = simulation.get("sell_plan")
    if not isinstance(buy_plan, dict) or not isinstance(sell_plan, dict):
        return

    def _format_optional_cop(value: object) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return _format_cop_price(numeric_value)

    def _format_optional_signed_cop(value: object) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return _format_signed_cop(numeric_value)

    def _format_optional_bps(value: object) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return f"{numeric_value:,.1f} bps"

    def _format_optional_margin_cop(entry_value: object, target_value: object) -> str:
        try:
            entry_numeric = float(entry_value)
            target_numeric = float(target_value)
        except (TypeError, ValueError):
            return "n/a"
        if entry_numeric <= 0 or target_numeric <= 0:
            return "n/a"
        return _format_cop_price(abs(target_numeric - entry_numeric))

    def _format_capital_label(value: object) -> str:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return _format_cop_price(numeric_value)

    def _collect_driver_markup(plan: dict) -> str:
        preferred_labels = {
            "Prob",
            "Z Spread",
            "Z OBI1",
            "Z OBI5",
            "Delta Micro",
            "Delta VWAP",
            "Entry-Last",
            "Room",
            "Lag",
            "Samples",
        }
        drivers = [
            driver
            for driver in plan.get("drivers", [])
            if isinstance(driver, dict)
            and str(driver.get("label") or "").strip() in preferred_labels
        ]
        return "".join(
            (
                "<span class='analytics-simulation-driver "
                f"{_simulation_driver_tone(driver.get('tone'))}'>"
                f"{escape(str(driver.get('label') or '').strip())} {escape(str(driver.get('value') or '').strip())}"
                "</span>"
            )
            for driver in drivers
        )

    def _render_plan(plan: dict) -> str:
        scenario_label = str(plan.get("scenario_label") or "").strip() or "Escenario"
        order_label = str(plan.get("order_label") or "").strip() or "Orden limite"
        exit_label = str(plan.get("exit_label") or "").strip() or "Salida objetivo"
        tone = str(plan.get("tone") or "gray").strip().lower()
        main_class = {
            "green": "analytics-simulation-main-buy",
            "red": "analytics-simulation-main-sell",
        }.get(tone, "analytics-simulation-main-neutral")

        probability_pct = float(plan.get("probability_pct") or 0.0)
        limit_price = _format_optional_cop(plan.get("limit_price"))
        target_price = _format_optional_cop(plan.get("target_price"))
        quantity = _format_plain_integer(plan.get("share_quantity"))
        capital = _format_capital_label(plan.get("reference_capital_cop"))
        notional = _format_optional_cop(plan.get("reference_notional_cop"))
        net_profit = _format_optional_signed_cop(plan.get("expected_net_profit_cop"))
        net_loss = _format_optional_signed_cop(
            None
            if plan.get("expected_net_loss_cop") is None
            else -abs(float(plan.get("expected_net_loss_cop")))
        )
        required_move = _format_optional_bps(plan.get("required_move_bps"))
        room_bps = _format_optional_bps(plan.get("room_bps"))
        max_feasible_profit = _format_optional_signed_cop(plan.get("max_feasible_net_profit_cop"))
        commission = _format_optional_cop(plan.get("total_commission_cop"))
        entry_gap = _format_optional_bps(plan.get("entry_gap_bps"))
        best_effort_capital = _format_capital_label(plan.get("best_effort_capital_cop"))
        best_effort_notional = _format_optional_cop(plan.get("best_effort_notional_cop"))
        best_effort_quantity = _format_plain_integer(plan.get("best_effort_share_quantity"))
        best_effort_target = _format_optional_cop(plan.get("best_effort_target_price"))
        best_effort_move = _format_optional_bps(plan.get("best_effort_move_bps"))
        best_effort_commission = _format_optional_cop(plan.get("best_effort_total_commission_cop"))
        best_effort_margin = _format_optional_margin_cop(
            plan.get("limit_price"),
            plan.get("best_effort_target_price"),
        )
        drivers_markup = _collect_driver_markup(plan)
        has_setup = (
            plan.get("target_price") is not None
            and plan.get("share_quantity") is not None
            and plan.get("reference_capital_cop") is not None
        )

        if has_setup:
            primary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Capital')}</strong> {escape(capital)} | "
                f"<strong>{escape('Cantidad')}</strong> {escape(quantity)} | "
                f"<strong>{escape('Monto')}</strong> {escape(notional)} | "
                f"<strong>{escape('Profit neto')}</strong> {escape(net_profit)}</div>"
            )
            secondary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Orden limite')}</strong> {escape(limit_price)} | "
                f"<strong>{escape(exit_label)}</strong> {escape(target_price)} | "
                f"<strong>{escape('Move requerido')}</strong> {escape(required_move)} | "
                f"<strong>{escape('Riesgo neto')}</strong> {escape(net_loss)}</div>"
            )
            tertiary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Rango disponible')}</strong> {escape(room_bps)} | "
                f"<strong>{escape('Gap entrada')}</strong> {escape(entry_gap)} | "
                f"<strong>{escape('Prob')}</strong> {escape(f'{probability_pct:,.1f}%')} | "
                f"<strong>{escape('Comision')}</strong> {escape(commission)}</div>"
            )
        else:
            primary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Capital evaluado')}</strong> {escape(best_effort_capital)} | "
                f"<strong>{escape('Cantidad')}</strong> {escape(best_effort_quantity)} | "
                f"<strong>{escape('Monto')}</strong> {escape(best_effort_notional)}</div>"
            )
            secondary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Limite referencia')}</strong> {escape(limit_price)} | "
                f"<strong>{escape('Salida factible')}</strong> {escape(best_effort_target)} | "
                f"<strong>{escape('Profit maximo')}</strong> {escape(max_feasible_profit)} | "
                f"<strong>{escape('Margen esperado')}</strong> {escape(best_effort_margin)}</div>"
            )
            tertiary_line = (
                f"<div class='analytics-simulation-sub'><strong>{escape('Move factible')}</strong> {escape(best_effort_move)} | "
                f"<strong>{escape('Rango disponible')}</strong> {escape(room_bps)} | "
                f"<strong>{escape('Gap entrada')}</strong> {escape(entry_gap)} | "
                f"<strong>{escape('Prob')}</strong> {escape(f'{probability_pct:,.1f}%')} | "
                f"<strong>{escape('Comision')}</strong> {escape(best_effort_commission)}</div>"
            )

        return "".join(
            [
                "<div class='analytics-light-tape-item analytics-simulation-item'>",
                "<div class='analytics-light-tape-eyebrow'>",
                "<span class='analytics-light-tape-dot'></span>",
                f"<span class='analytics-light-tape-label'>{escape(scenario_label)}</span>",
                "</div>",
                f"<div class='analytics-light-tape-main {main_class}'>{escape(order_label)} {escape(limit_price)}</div>",
                primary_line,
                secondary_line,
                tertiary_line,
                f"<div class='analytics-simulation-driver-list'>{drivers_markup}</div>",
                "</div>",
            ]
        )

    st.markdown(
        "<div class='analytics-light-tape analytics-simulation-strip'>"
        + _render_plan(buy_plan)
        + _render_plan(sell_plan)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_kpis(symbol_record_groups: list[tuple[str, dict, list[dict]]]) -> None:
    for symbol, payload, records in symbol_record_groups:
        _render_microstructure_tape(symbol, payload, records)
        _render_market_tape(records)
        _render_simulation_strip(payload, records)
        _render_market_ai_recommendation(payload)
        st.markdown("<div class='analytics-kpi-row-spacer'></div>", unsafe_allow_html=True)


def _render_summary_line(summary: dict[str, str]) -> None:
    current_time = now_in_bogota()
    refresh_reference = (
        st.session_state.get("analytics_last_manual_refresh")
        or st.session_state.get("analytics_session_loaded_at")
        or current_time
    )
    refresh_age_seconds = max(int((current_time - refresh_reference).total_seconds()), 0)
    refresh_tone = _refresh_tone(refresh_age_seconds)
    trigger_reason = _format_trigger_reason(summary.get("trigger_reason"))
    latest_captured_at = str(summary.get("latest_captured_at") or "").strip()
    sample_age_seconds = None
    if latest_captured_at:
        try:
            latest_timestamp = datetime.fromisoformat(latest_captured_at)
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=current_time.tzinfo)
            latest_timestamp = latest_timestamp.astimezone(current_time.tzinfo)
            sample_age_seconds = max(int((current_time - latest_timestamp).total_seconds()), 0)
        except ValueError:
            sample_age_seconds = None
    summary_parts = [
        f":green[:material/event_available: **Desde**] **{summary['from_timestamp']}**",
        f":green[:material/flag: **Hasta**] **{summary['to_timestamp']}**",
        f":green[:material/timer: **TW**] **{summary['tw_seconds']:,}s**",
    ]
    if trigger_reason is not None:
        summary_parts.append(f":green[:material/rss_feed: **Feed**] **{trigger_reason}**")
    if sample_age_seconds is not None:
        sample_tone = _feed_age_tone(sample_age_seconds)
        summary_parts.append(
            f":{sample_tone}[:material/av_timer: **Lag**] **{_format_elapsed_seconds(sample_age_seconds)}**"
        )
    summary_parts.append(
        f":{refresh_tone}[:material/history: **Last Refresh**] **{_format_elapsed_seconds(refresh_age_seconds)}**"
    )
    st.markdown(
        "  |  ".join(summary_parts),
        text_alignment="right",
    )


@st.fragment(run_every=1)
def _render_summary_line_fragment() -> None:
    summary = st.session_state.get("analytics_summary")
    if not isinstance(summary, dict) or not summary:
        return
    current_time = now_in_bogota()
    refresh_reference = (
        st.session_state.get("analytics_last_manual_refresh")
        or st.session_state.get("analytics_session_loaded_at")
        or current_time
    )
    refresh_age_seconds = max(int((current_time - refresh_reference).total_seconds()), 0)
    if refresh_age_seconds >= 300:
        _refresh_recent_snapshots_cache()
        st.rerun()
    _render_summary_line(summary)


st.session_state.setdefault("analytics_last_manual_refresh", None)
st.session_state.setdefault("analytics_session_loaded_at", now_in_bogota())
st.session_state.setdefault("analytics_summary", {})

st.markdown(
    """
    <style>
    .analytics-kpi-row-spacer {
        height: 0.24rem;
    }
    .analytics-light-tape {
        min-height: 42px;
        border-radius: 10px;
        background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 100%);
        border: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        align-items: stretch;
        overflow: hidden;
        margin-bottom: 6px;
    }
    .analytics-light-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.3rem 0.46rem 0.26rem 0.46rem;
        border-right: 1px solid rgba(8, 33, 20, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-light-tape-item:last-child {
        border-right: none;
    }
    .analytics-light-tape-symbol {
        max-width: 120px;
        align-items: center;
        justify-content: center;
    }
    .analytics-light-tape-eyebrow {
        display: flex;
        align-items: center;
        gap: 0.22rem;
        margin-bottom: 0.06rem;
    }
    .analytics-light-tape-dot {
        width: 0.28rem;
        height: 0.28rem;
        border-radius: 999px;
        background: #02fb7e;
        flex-shrink: 0;
    }
    .analytics-light-tape-label {
        color: #082114;
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-light-tape-main {
        color: #000000;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 0.94;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.04rem;
    }
    .analytics-light-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.28rem;
        min-width: 0;
    }
    .analytics-light-tape-zscore {
        color: rgba(8, 33, 20, 0.68);
        font-size: 0.52rem;
        font-weight: 600;
        line-height: 1.0;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-light-tape-zscore-stack {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 0.04rem;
        min-width: 0;
        flex-shrink: 0;
    }
    .analytics-light-tape-zmeta {
        display: flex;
        flex-direction: column;
        gap: 0.01rem;
        min-width: 0;
    }
    .analytics-light-tape-zmeta-line {
        color: rgba(8, 33, 20, 0.54);
        font-size: 0.4rem;
        font-weight: 400;
        line-height: 1.05;
        letter-spacing: 0.01em;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        width: fit-content;
        padding: 0.06rem 0.28rem;
        border-radius: 999px;
        background: rgba(8, 33, 20, 0.06);
    }
    .analytics-light-tape-zmeta-line-green {
        color: #0b6b35;
        background: rgba(2, 251, 126, 0.18);
    }
    .analytics-light-tape-zmeta-line-red {
        color: #b42318;
        background: rgba(255, 95, 87, 0.18);
    }
    .analytics-light-tape-zmeta-line-blue {
        color: #155eef;
        background: rgba(21, 94, 239, 0.14);
    }
    .analytics-light-tape-zmeta-line-gray {
        color: #667085;
        background: rgba(102, 112, 133, 0.12);
    }
    .analytics-light-tape-sub {
        color: rgba(8, 33, 20, 0.62);
        font-size: 0.5rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape {
        min-height: 42px;
        margin-top: 6px;
        border-radius: 10px;
        background: linear-gradient(180deg, #0d1117 0%, #11161d 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        display: flex;
        align-items: stretch;
        overflow: hidden;
    }
    .analytics-market-tape-item {
        flex: 1 1 0;
        min-width: 0;
        padding: 0.32rem 0.48rem 0.28rem 0.48rem;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .analytics-market-tape-item:last-child {
        border-right: none;
    }
    .analytics-market-tape-eyebrow {
        display: flex;
        align-items: center;
        margin-bottom: 0.06rem;
    }
    .analytics-market-tape-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.48rem;
        font-weight: 600;
        line-height: 1.0;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-main-row {
        display: flex;
        align-items: baseline;
        gap: 0.34rem;
        min-width: 0;
    }
    .analytics-market-tape-main {
        color: #f8fafc;
        font-size: 0.8rem;
        font-weight: 700;
        line-height: 0.92;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 0.05rem;
    }
    .analytics-market-tape-inline-percent {
        font-size: 0.54rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        flex-shrink: 0;
    }
    .analytics-market-tape-inline-percent-positive {
        color: #02fb7e;
    }
    .analytics-market-tape-inline-percent-negative {
        color: #ff5f57;
    }
    .analytics-market-tape-sub {
        color: rgba(255, 255, 255, 0.58);
        font-size: 0.46rem;
        font-weight: 500;
        line-height: 0.98;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-market-tape-sub-inline {
        display: inline-flex;
        align-items: baseline;
        gap: 0.28rem;
        white-space: nowrap;
    }
    .analytics-market-tape-item-positive .analytics-market-tape-main,
    .analytics-market-tape-item-positive .analytics-market-tape-sub {
        color: #02fb7e;
    }
    .analytics-market-tape-item-negative .analytics-market-tape-main,
    .analytics-market-tape-item-negative .analytics-market-tape-sub {
        color: #ff5f57;
    }
    .analytics-market-tape-item-market .analytics-market-tape-main {
        color: #8ab4f8;
    }
    .analytics-market-tape-item-paired {
        gap: 0.18rem;
    }
    .analytics-market-tape-pair {
        display: flex;
        flex-direction: column;
        gap: 0.02rem;
    }
    .analytics-market-tape-pair-label {
        color: rgba(255, 255, 255, 0.72);
        font-size: 0.45rem;
        font-weight: 600;
        line-height: 1;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .analytics-market-tape-pair-value {
        color: #8ab4f8;
        font-size: 0.66rem;
        font-weight: 700;
        line-height: 1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-recommendation-strip {
        margin-top: 6px;
        padding: 0.55rem 0.75rem;
        border-radius: 10px;
        border: 1px solid rgba(8, 33, 20, 0.08);
        background: linear-gradient(180deg, #fbfffd 0%, #f4fbf7 100%);
    }
    .analytics-recommendation-strip-header {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        margin-bottom: 0.14rem;
        flex-wrap: wrap;
    }
    .analytics-recommendation-strip-badge {
        font-size: 0.48rem;
        line-height: 1;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #0b6b35;
        background: rgba(2, 251, 126, 0.14);
        border-radius: 999px;
        padding: 0.18rem 0.42rem;
    }
    .analytics-recommendation-strip-rules {
        font-size: 0.52rem;
        color: rgba(8, 33, 20, 0.62);
        font-weight: 500;
    }
    .analytics-recommendation-strip-body {
        font-size: 0.7rem;
        line-height: 1.4;
        color: #082114;
    }
    .analytics-diagnostic-strip {
        margin-top: 0.36rem;
        margin-bottom: 0.5rem;
    }
    .analytics-diagnostic-caption {
        margin-top: 0.12rem;
        margin-bottom: 0.24rem;
        font-size: 0.52rem;
        line-height: 1.2;
        font-weight: 400;
        font-style: italic;
        color: rgba(8, 33, 20, 0.58);
    }
    .analytics-reference-card-title {
        margin-bottom: 0.16rem;
        font-size: 0.46rem;
        line-height: 1.1;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #6f7a83;
    }
    .analytics-reference-card-copy {
        margin-top: 0.12rem;
        font-size: 0.44rem;
        line-height: 1.26;
        font-weight: 400;
        color: #5f6971;
    }
    .analytics-reference-divider {
        width: 1px;
        min-height: 100%;
        height: 100%;
        margin: 0 auto;
        background: rgba(8, 33, 20, 0.1);
    }
    div[data-testid="stLatex"] {
        margin-top: 0.02rem !important;
        margin-bottom: 0.02rem !important;
    }
    div[data-testid="stLatex"] .katex {
        font-size: 0.48em !important;
    }
    div[data-testid="stLatex"] .katex-display {
        margin: 0 !important;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 0.02rem 0;
    }
    div[data-testid="stLatex"] .katex-display > .katex {
        white-space: nowrap;
    }
    .analytics-diagnostic-strip-dark {
        border-radius: 10px;
        overflow: hidden;
    }
    .analytics-diagnostic-symbol-item {
        justify-content: center;
    }
    .analytics-diagnostic-symbol-item-dark {
        justify-content: center;
        display: flex;
        align-items: center;
        min-width: 160px;
    }
    .analytics-diagnostic-light-item,
    .analytics-diagnostic-dark-item {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 0.12rem;
        min-height: 52px;
        padding-top: 0.18rem;
        padding-bottom: 0.18rem;
    }
    .analytics-diagnostic-title {
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-weight: 600;
        line-height: 1.0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .analytics-diagnostic-title-light {
        font-size: 0.48rem;
        color: #082114;
    }
    .analytics-diagnostic-title-dark {
        font-size: 0.48rem;
        color: rgba(255, 255, 255, 0.72);
    }
    .analytics-diagnostic-copy {
        display: block;
        overflow: visible;
        white-space: normal;
        text-wrap: balance;
        width: 100%;
    }
    .analytics-diagnostic-copy-light {
        font-size: 0.44rem;
        line-height: 1.14;
        font-weight: 400;
        color: rgba(8, 33, 20, 0.64);
    }
    .analytics-diagnostic-copy-dark {
        font-size: 0.44rem;
        line-height: 1.14;
        font-weight: 400;
        color: #02fb7e;
    }
    .analytics-simulation-strip {
        margin-top: 0.74rem;
        margin-bottom: 0.5rem;
    }
    .analytics-simulation-item {
        gap: 0.11rem;
    }
    .analytics-simulation-main-buy {
        color: #0b6b35;
    }
    .analytics-simulation-main-sell {
        color: #b42318;
    }
    .analytics-simulation-main-neutral {
        color: rgba(8, 33, 20, 0.72);
    }
    .analytics-simulation-sub {
        color: rgba(8, 33, 20, 0.62);
        font-size: 0.46rem;
        line-height: 1.18;
        font-weight: 500;
        white-space: normal;
        text-wrap: pretty;
    }
    .analytics-simulation-sub strong {
        color: rgba(8, 33, 20, 0.84);
        font-weight: 600;
    }
    .analytics-simulation-driver-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.16rem;
        margin-top: 0.04rem;
    }
    .analytics-simulation-driver {
        display: inline-flex;
        align-items: center;
        padding: 0.08rem 0.28rem;
        border-radius: 999px;
        font-size: 0.42rem;
        font-weight: 500;
        line-height: 1.05;
        white-space: nowrap;
    }
    .analytics-simulation-driver-red {
        background: rgba(180, 35, 24, 0.12);
        color: #b42318;
    }
    .analytics-simulation-driver-gray {
        background: rgba(8, 33, 20, 0.06);
        color: rgba(8, 33, 20, 0.72);
    }
    .analytics-simulation-driver-green {
        background: rgba(2, 251, 126, 0.16);
        color: #0b6b35;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

days = 7

try:
    with st.spinner("Consultando simbolos disponibles..."):
        catalog_response = _load_analytics_catalog(days)

    catalog_result = catalog_response.get("result", {})
    symbols = [
        str(symbol).strip().upper()
        for symbol in catalog_result.get("symbols", [])
        if str(symbol).strip()
    ]

    if not symbols:
        st.info("No se encontraron snapshots disponibles para construir filtros operativos.")
    else:
        filter_columns = st.columns([2.2, 0.7], gap="medium")
        with filter_columns[0]:
            st.markdown("*Symbols*")
            selected_symbols = st.multiselect(
                "Symbols",
                options=symbols,
                default=symbols,
                help="Select one or more symbols for the analytics view.",
                label_visibility="collapsed",
            )
        with filter_columns[1]:
            st.markdown("*Refresh*")
            refresh_requested = st.button(
                "Refresh query",
                icon=":material/refresh:",
                type="secondary",
                width="stretch",
            )

        if refresh_requested:
            _refresh_recent_snapshots_cache()
            st.toast("Consulta actualizada contra API Gateway.")

        analytics_payloads: list[dict] = []
        for selected_symbol in selected_symbols:
            analytics_response = _load_analytics_snapshot(selected_symbol)
            analytics_result = analytics_response.get("result", {})
            if analytics_result.get("current_snapshot"):
                analytics_payloads.append(analytics_result)

        if not selected_symbols:
            st.info("Selecciona al menos un simbolo para cargar la vista analitica.")
        elif not analytics_payloads:
            st.info("No hay snapshots disponibles para los simbolos elegidos.")
        else:
            symbol_record_groups = _build_symbol_analytics_groups(analytics_payloads, selected_symbols)
            filtered_records = [
                record
                for _, _, records in symbol_record_groups
                for record in records
                if isinstance(record, dict)
            ]
            filtered_records.sort(key=lambda item: str(item.get("captured_at", "")), reverse=True)

            summary = build_analytics_summary(
                filtered_records,
                current_time=now_in_bogota(),
            )
            st.session_state["analytics_summary"] = summary
            _render_summary_line_fragment()

            _render_kpis(symbol_record_groups)

            execution_tab, alerts_tab = st.tabs(["Ejecucion", "Alertas"])
            with execution_tab:
                _render_diagnostic_board(
                    symbol_record_groups,
                    "execution",
                    "Lectura tactica para decidir si el mercado ofrece liquidez suficiente, sesgo util en punta y una referencia de precio todavia defendible frente a la sesion.",
                )
            with alerts_tab:
                _render_diagnostic_board(
                    symbol_record_groups,
                    "alerts",
                    "Lectura defensiva para separar ruido normal de eventos que merecen revision inmediata antes de tomar una decision de corto plazo.",
                )
except (BackendConfigurationError, ApiGatewayClientError) as exc:
    st.error("No fue posible consultar los snapshots recientes.")
    st.caption("Referencia interna: `analytics_recent_snapshots`")
    st.write(
        "Revisa la configuracion de `api_gateway_url` y `api_gateway_token` en Streamlit secrets, "
        "o confirma que el API Gateway y la Lambda esten desplegados."
    )
    with st.expander("Detalle tecnico"):
        st.code(str(exc))
