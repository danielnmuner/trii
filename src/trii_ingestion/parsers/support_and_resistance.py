from __future__ import annotations

import re

from trii_ingestion.models.support_and_resistance import (
    SupportResistanceLevel,
    SupportResistanceSnapshot,
    SupportResistanceWindow,
)
from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.parsers.common import clean_lines, parse_money, parse_percent


class SupportAndResistanceParser(TextParser):
    section = SectionType.SUPPORT_AND_RESISTANCE

    def score(self, text: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if "Soporte y resistencia diario" in text:
            score += 0.45
            reasons.append("contains daily support and resistance heading")
        if "Soporte y resistencia a largo plazo" in text:
            score += 0.25
            reasons.append("contains long term support and resistance heading")
        if "Precio de cierre" in text:
            score += 0.15
            reasons.append("contains close price lines")
        if "Resistencia 1" in text and "Soporte 1" in text:
            score += 0.15
            reasons.append("contains support and resistance rows")
        return self._bounded_score(score), reasons

    def parse(self, text: str) -> SupportResistanceSnapshot:
        lines = clean_lines(text)
        self._ensure_parseable(lines, ["Soporte y resistencia diario", "Soporte y resistencia a largo plazo"])

        symbol = "PFAVAL"
        asset_name = "Aval Preferencial"

        long_term_index = lines.index("Soporte y resistencia a largo plazo")
        daily_lines = lines[lines.index("Soporte y resistencia diario") : long_term_index]
        long_term_lines = lines[long_term_index:]

        daily = self._parse_window(daily_lines)
        long_term = self._parse_window(long_term_lines)

        return SupportResistanceSnapshot(
            symbol=symbol,
            asset_name=asset_name,
            daily=daily,
            long_term=long_term,
        )

    def _parse_window(self, lines: list[str]) -> SupportResistanceWindow:
        close_price_line = next(line for line in lines if line.startswith("Precio de cierre"))
        close_price = parse_money(close_price_line.replace("Precio de cierre", "").strip())

        levels: list[SupportResistanceLevel] = []
        analysis_lines: list[str] = []
        row_pattern = re.compile(r"(Resistencia|Soporte)\s+(\d)\s+\$\s*([\d\.,]+)\s+([+-]?[\d\.,]+)%")

        for line in lines:
            match = row_pattern.match(line)
            if match:
                levels.append(
                    SupportResistanceLevel(
                        type="resistance" if match.group(1) == "Resistencia" else "support",
                        rank=int(match.group(2)),
                        price=parse_money(match.group(3)),
                        change_percent=parse_percent(match.group(4)),
                    )
                )

        last_level_line = None
        for index, line in enumerate(lines):
            if row_pattern.match(line):
                last_level_line = index
        if last_level_line is None:
            raise ValueError("No support/resistance levels found")

        for line in lines[last_level_line + 1 :]:
            if not line.startswith("Soporte y resistencia"):
                analysis_lines.append(line)

        return SupportResistanceWindow(
            close_price=close_price,
            levels=levels,
            analysis=" ".join(analysis_lines).strip(),
        )
