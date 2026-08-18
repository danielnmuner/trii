from __future__ import annotations

import re

from trii_ingestion.models.technical import TechnicalIndicator, TechnicalIndicatorsSnapshot
from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.parsers.common import clean_lines, normalize_key, parse_signal


class TechnicalOscillatorsParser(TextParser):
    section = SectionType.TECHNICAL_OSCILLATORS

    def score(self, text: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if "Osciladores" in text:
            score += 0.4
            reasons.append("contains oscillators heading")
        if "RSI 7" in text and "RSI 21" in text:
            score += 0.25
            reasons.append("contains RSI rows")
        if "MACD" in text:
            score += 0.15
            reasons.append("contains MACD row")
        if "Williams %R" in text:
            score += 0.1
            reasons.append("contains Williams %R row")
        if "Detalles técnicos" in text:
            score += 0.1
            reasons.append("contains technical details heading")
        return self._bounded_score(score), reasons

    def parse(self, text: str) -> TechnicalIndicatorsSnapshot:
        lines = clean_lines(text)
        self._ensure_parseable(lines, ["Osciladores", "Compra", "Mantener", "Venta", "Detalles técnicos"])

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
        start_index = lines.index("Indicador\tValor\tSeñal\tComentario") + 1 if "Indicador\tValor\tSeñal\tComentario" in lines else lines.index("Indicador\tValor\tSeñal\tComentario".replace("\t", " ")) + 1
        return lines[start_index:]

    @staticmethod
    def _parse_indicator_header(line: str) -> tuple[str, float]:
        match = re.match(r"(.+?)\s+(-?\d+(?:\.\d+)?)$", line)
        if not match:
            raise ValueError(f"Could not parse indicator header: {line}")
        return match.group(1), float(match.group(2))

    @staticmethod
    def _map_indicator_key(name: str) -> str:
        mapping = {
            "Estocástico Lento D": "slow_stochastic_d",
            "Estocástico Rápido D": "fast_stochastic_d",
            "Williams %R": "williams_r",
        }
        return mapping.get(name, normalize_key(name))
