from __future__ import annotations

from html import escape

import streamlit as st

from analytics_utils import (
    SymbolRecordGroup,
    compute_cumulative_vwap,
    format_elapsed_seconds,
    format_metric_value,
    format_samples,
    format_z_score,
    parse_record_timestamp,
    safe_float,
)
from trii_ingestion.services import build_historic_z_score_context, now_in_bogota


def build_diagnostic_cell(*args: str) -> dict[str, str]:
    if len(args) == 2:
        text, tone = args
        return {"title": "", "text": text, "tone": tone}
    if len(args) == 3:
        title, text, tone = args
        return {"title": title, "text": text, "tone": tone}
    raise ValueError("Unexpected diagnostic cell arguments.")


def spread_diagnostic(spread_bps: float | None) -> dict[str, str]:
    value_label = format_metric_value("spread_bps", spread_bps)
    if spread_bps is None:
        return build_diagnostic_cell(
            "Spread relativo",
            f"No hay una lectura operativa valida del spread en este instante, asi que el panel no puede estimar con disciplina el costo real de cruzar el libro ahora mismo ({value_label}).",
            "gray",
        )
    if spread_bps > 150:
        return build_diagnostic_cell(
            "Spread relativo",
            f"El spread se abrio hasta {value_label}; la entrada pierde eficiencia y conviene bajar urgencia, trabajar el precio con mas paciencia o reducir agresividad antes de cruzar el libro.",
            "red",
        )
    if spread_bps <= 30:
        return build_diagnostic_cell(
            "Spread relativo",
            f"El spread se mantiene en {value_label}; el costo de cruce sigue contenido y el libro ofrece una ventana razonable para ejecutar rapido sin castigar tanto el punto de entrada.",
            "green",
        )
    return build_diagnostic_cell(
        "Spread relativo",
        f"El spread marca {value_label}; el mercado sigue siendo operable, pero no entrega una ventaja clara de costo y todavia conviene evitar perseguir precio sin una confirmacion adicional.",
        "blue",
    )


def obi_l1_diagnostic(obi_l1: float | None, obi_top_5: float | None) -> dict[str, str]:
    l1_label = format_metric_value("obi_l1", obi_l1)
    top5_label = format_metric_value("obi_top_5", obi_top_5)
    if obi_l1 is None:
        return build_diagnostic_cell(
            "Presion en punta",
            f"No hay una lectura valida de presion en punta; sin OBI L1 el panel no puede concluir si la mejor postura favorece compra o venta ({l1_label}).",
            "gray",
        )
    if obi_l1 > 0.6:
        return build_diagnostic_cell(
            "Presion en punta",
            f"El libro muestra dominio comprador con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la demanda visible sostiene la mejor compra y favorece continuidad alcista de muy corto plazo.",
            "green",
        )
    if obi_l1 < -0.6:
        return build_diagnostic_cell(
            "Presion en punta",
            f"El libro muestra dominio vendedor con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la oferta visible presiona la mejor venta y aumenta el riesgo de continuidad bajista inmediata.",
            "red",
        )
    return build_diagnostic_cell(
        "Presion en punta",
        f"El libro luce equilibrado con OBI L1 {l1_label} y OBI Top 5 {top5_label}; la punta no muestra un sesgo dominante y conviene esperar confirmacion antes de leer direccion con conviccion.",
        "blue",
    )


def microprice_diagnostic(delta_micro: float | None) -> dict[str, str]:
    value_label = format_metric_value("depth_weighted_microprice_deviation", delta_micro)
    if delta_micro is None:
        return build_diagnostic_cell(
            "Microprice vs mid",
            f"No hay referencia valida de microprice frente al mid; sin ese delta el panel no puede medir si la masa visible empuja el precio justo ({value_label}).",
            "gray",
        )
    if delta_micro < 0:
        return build_diagnostic_cell(
            "Microprice vs mid",
            f"El microprice cae {value_label} por debajo del mid; la masa visible en L1 empuja el precio justo hacia abajo y debilita cualquier lectura compradora demasiado optimista.",
            "red",
        )
    if delta_micro > 0:
        return build_diagnostic_cell(
            "Microprice vs mid",
            f"El microprice supera el mid en {value_label}; la masa visible en L1 empuja el precio justo hacia arriba y respalda un sesgo alcista inmediato con mejor fundamento.",
            "green",
        )
    return build_diagnostic_cell(
        "Microprice vs mid",
        f"El microprice y el mid permanecen practicamente alineados ({value_label}); la punta no transmite una inclinacion clara y el libro sigue neutral en el margen.",
        "blue",
    )


def vwap_diagnostic(last_price: float | None, vwap_value: float | None) -> dict[str, str]:
    delta_vwap = None if last_price is None or vwap_value is None else last_price - vwap_value
    if delta_vwap is None:
        return build_diagnostic_cell(
            "Precio vs VWAP",
            "No hay comparacion valida contra VWAP acumulado; sin valor y volumen negociado consistentes el panel no puede saber si el precio cotiza con prima o descuento.",
            "gray",
        )
    value_label = format_metric_value("depth_weighted_microprice_deviation", delta_vwap)
    if delta_vwap > 0:
        return build_diagnostic_cell(
            "Precio vs VWAP",
            f"El ultimo precio se negocia {value_label} por encima del VWAP acumulado; el mercado sigue pagando prima frente al promedio efectivo de la sesion y no esta soltando precio con facilidad.",
            "green",
        )
    if delta_vwap < 0:
        return build_diagnostic_cell(
            "Precio vs VWAP",
            f"El ultimo precio se negocia {value_label} por debajo del VWAP acumulado; hay descuento frente al flujo efectivo de la sesion y menor disposicion a seguir pagando arriba.",
            "red",
        )
    return build_diagnostic_cell(
        "Precio vs VWAP",
        f"El ultimo precio se mantiene alineado con el VWAP acumulado ({value_label}); la sesion sigue balanceada alrededor de su promedio ponderado sin prima ni castigo claros.",
        "blue",
    )


def z_spread_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return build_diagnostic_cell(
            "Z-Score spread",
            f"Muestra aun insuficiente ({format_samples(sample_count)}) para decidir si el spread actual ya se salio de su rango historico confiable.",
            "gray",
        )
    if z_score >= 2.0:
        return build_diagnostic_cell(
            "Z-Score spread",
            f"El spread corre en {format_z_score(z_score)} y el costo de entrada ya esta muy por encima de su rango normal; antes de ejecutar conviene revisar con mas disciplina.",
            "red",
        )
    if z_score <= -2.0:
        return build_diagnostic_cell(
            "Z-Score spread",
            f"El spread corre en {format_z_score(z_score)} y el libro esta mas cerrado de lo normal; la ejecucion luce especialmente competitiva en este momento.",
            "green",
        )
    return build_diagnostic_cell(
        "Z-Score spread",
        f"El spread marca {format_z_score(z_score)} y el costo de ejecucion sigue dentro del comportamiento estadisticamente esperado para la jornada.",
        "blue",
    )


def z_obi5_diagnostic(stat_item: dict | None) -> dict[str, str]:
    context = build_historic_z_score_context(stat_item)
    z_score = context["z_score"]
    sample_count = int(context["sample_count"] or 0)
    if z_score is None:
        return build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"Muestra aun insuficiente ({format_samples(sample_count)}) para decidir si la profundidad visible ya es estadisticamente inusual.",
            "gray",
        )
    if z_score >= 2.0:
        return build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"El OBI Top 5 corre en {format_z_score(z_score)} y la acumulacion compradora ya supera con claridad su patron habitual.",
            "green",
        )
    if z_score <= -2.0:
        return build_diagnostic_cell(
            "Z-Score OBI Top 5",
            f"El OBI Top 5 corre en {format_z_score(z_score)} y la acumulacion vendedora ya supera con claridad su patron habitual.",
            "red",
        )
    return build_diagnostic_cell(
        "Z-Score OBI Top 5",
        f"El OBI Top 5 marca {format_z_score(z_score)} y la profundidad visible sigue dentro de rango sin una distorsion estadistica fuerte.",
        "blue",
    )


def spoofing_risk_diagnostic(
    obi_l1: float | None,
    delta_micro: float | None,
    z_spread: float | None,
) -> dict[str, str]:
    if obi_l1 is None or delta_micro is None or z_spread is None:
        return build_diagnostic_cell(
            "Riesgo de spoofing",
            "Todavia faltan senales para decidir si la punta puede estar enviando una impresion enganosa; por ahora no hay base suficiente para elevar esta alerta.",
            "gray",
        )
    if obi_l1 > 0.5 and delta_micro < 0 and z_spread >= 1.5:
        return build_diagnostic_cell(
            "Riesgo de spoofing",
            "La punta parece compradora, pero la profundidad y el spread la contradicen; este desacople es compatible con una trampa de liquidez y merece revision inmediata.",
            "red",
        )
    return build_diagnostic_cell(
        "Riesgo de spoofing",
        "La punta, la profundidad y el spread no muestran un conflicto severo; por ahora el libro no exhibe un desacople que sugiera trampa de liquidez.",
        "blue",
    )


def stale_data_diagnostic(lag_seconds: int | None) -> dict[str, str]:
    if lag_seconds is None:
        return build_diagnostic_cell(
            "Latencia operativa",
            "No fue posible medir la latencia del feed; esta lectura debe tratarse con cautela hasta confirmar que el snapshot sigue vigente.",
            "gray",
        )
    if lag_seconds > 300:
        return build_diagnostic_cell(
            "Latencia operativa",
            f"El snapshot llega con un rezago de {format_elapsed_seconds(lag_seconds)}; para corto plazo ya no conviene asumir que el mercado sigue igual.",
            "red",
        )
    return build_diagnostic_cell(
        "Latencia operativa",
        f"El feed mantiene un rezago de {format_elapsed_seconds(lag_seconds)} y la informacion sigue siendo util para una decision tactica inmediata.",
        "green",
    )


def build_diagnostic_cells(module_key: str, payload: dict, records: list[dict]) -> list[dict[str, str]]:
    latest_record = records[0]
    current_stats = payload.get("current_stats", {})
    current_time = now_in_bogota()
    latest_timestamp = parse_record_timestamp(str(latest_record.get("captured_at") or ""), current_time)
    lag_seconds = None if latest_timestamp is None else max(int((current_time - latest_timestamp).total_seconds()), 0)

    spread_bps = safe_float(latest_record, "spread_bps")
    obi_l1 = safe_float(latest_record, "obi_l1")
    obi_top_5 = safe_float(latest_record, "obi_top_5")
    delta_micro = safe_float(latest_record, "depth_weighted_microprice_deviation")
    last_price = safe_float(latest_record, "last_price")
    vwap_value = compute_cumulative_vwap(latest_record)
    z_spread_context = build_historic_z_score_context(current_stats.get("spread_bps"))

    modules = {
        "execution": [
            spread_diagnostic(spread_bps),
            obi_l1_diagnostic(obi_l1, obi_top_5),
            microprice_diagnostic(delta_micro),
            vwap_diagnostic(last_price, vwap_value),
        ],
        "alerts": [
            z_spread_diagnostic(current_stats.get("spread_bps")),
            z_obi5_diagnostic(current_stats.get("obi_top_5")),
            spoofing_risk_diagnostic(obi_l1, delta_micro, z_spread_context["z_score"]),
            stale_data_diagnostic(lag_seconds),
        ],
    }
    return modules[module_key]


def render_diagnostic_reference(section_key: str) -> None:
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


def render_diagnostic_board(
    symbol_record_groups: list[SymbolRecordGroup],
    section_key: str,
    section_caption: str,
) -> None:
    st.markdown(
        f"<div class='analytics-diagnostic-caption'>{escape(section_caption)}</div>",
        unsafe_allow_html=True,
    )
    for symbol, payload, records in symbol_record_groups:
        cells = build_diagnostic_cells(section_key, payload, records)
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
    render_diagnostic_reference(section_key)
