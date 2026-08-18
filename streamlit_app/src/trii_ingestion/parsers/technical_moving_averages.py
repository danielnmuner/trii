from __future__ import annotations

import re

from trii_ingestion.models.technical import TechnicalIndicator, TechnicalIndicatorsSnapshot
from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.parsers.common import clean_lines, normalize_key, parse_signal


class TechnicalMovingAveragesParser(TextParser):
    section = SectionType.TECHNICAL_MOVING_AVERAGES

    def score(self, text: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if "Media Móvil" in text or "Media Movil" in text:
            score += 0.45
            reasons.append("contains moving averages heading")
        if "MMS 7" in text and "MMS 21" in text:
            score += 0.2
            reasons.append("contains moving average rows")
        if "Bollinger" in text:
            score += 0.15
            reasons.append("contains bollinger rows")
        if "Momento 14" in text:
            score += 0.1
            reasons.append("contains momentum row")
        if "Detalles técnicos" in text:
            score += 0.1
            reasons.append("contains technical details heading")
        return self._bounded_score(score), reasons

    def parse(self, text: str) -> TechnicalIndicatorsSnapshot:
        lines = clean_lines(text)
        self._ensure_parseable(lines, ["Media Móvil", "Compra", "Mantener", "Venta", "Detalles técnicos"])

        symbol = "PFAVAL"
        asset_name = "Aval Preferencial"

        buy_signals = self._extract_summary_value(lines, "Compra")
        hold_signals = self._extract_summary_value(lines, "Mantener")
        sell_signals = self._extract_summary_value(lines, "Venta")
        indicator_lines = self._indicator_lines(lines)

        indicators: list[TechnicalIndicator] = []
        index = 0
        while index <= len(indicator_lines) - 3:
            name_and_value = indicator_lines[index]
            signal_line = indicator_lines[index + 1]
            commentary_line = indicator_lines[index + 2]
            indicator_name, indicator_value = self._parse_indicator_header(name_and_value)
            indicators.append(
                TechnicalIndicator(
                    key=self._map_indicator_key(indicator_name),
                    value=indicator_value,
                    raw_signal=signal_line,
                    signal=parse_signal(signal_line),
                    commentary=commentary_line,
                )
            )
            index += 3

        return TechnicalIndicatorsSnapshot(
            symbol=symbol,
            asset_name=asset_name,
            buy_signals=buy_signals,
            hold_signals=hold_signals,
            sell_signals=sell_signals,
            indicators=indicators,
        )

    @staticmethod
    def _extract_summary_value(lines: list[str], label: str) -> int:
        label_index = lines.index(label)
        return int(lines[label_index + 1])

    @staticmethod
    def _indicator_lines(lines: list[str]) -> list[str]:
        header = "Indicador\tValor\tSeñal\tComentario"
        if header in lines:
            return lines[lines.index(header) + 1 :]
        fallback_header = "Indicador Valor Señal Comentario"
        return lines[lines.index(fallback_header) + 1 :]

    @staticmethod
    def _parse_indicator_header(line: str) -> tuple[str, float]:
        match = re.match(r"(.+?)\s+(-?\d+(?:\.\d+)?)$", line)
        if not match:
            raise ValueError(f"Could not parse indicator header: {line}")
        return match.group(1), float(match.group(2))

    @staticmethod
    def _map_indicator_key(name: str) -> str:
        mapping = {
            "MMS 7": "sma_7",
            "MMS 21": "sma_21",
            "MMS 200": "sma_200",
            "Momento 14": "momentum_14",
            "Bollinger Up": "bollinger_upper",
            "Bollinger Down": "bollinger_lower",
        }
        return mapping.get(name, normalize_key(name))
