from __future__ import annotations

import re

from trii_ingestion.models.stock_snapshot import OrderBookLevel, StockSnapshot
from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.parsers.common import clean_lines, parse_int, parse_money, parse_percent


class StockSnapshotParser(TextParser):
    section = SectionType.STOCK_SNAPSHOT

    def score(self, text: str) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if "Líneas de profundidad" in text:
            score += 0.45
            reasons.append("contains market depth heading")
        if "Mejor compra" in text and "Mejor venta" in text:
            score += 0.25
            reasons.append("contains best bid and ask headings")
        if "Indicadores" in text:
            score += 0.2
            reasons.append("contains indicator section")
        if "Cantidad\tCompra" in text or "Cantidad Compra" in text:
            score += 0.1
            reasons.append("contains bid table header")
        return self._bounded_score(score), reasons

    def parse(self, text: str) -> StockSnapshot:
        lines = clean_lines(text)
        self._ensure_parseable(lines, ["Líneas de profundidad", "Mejor compra", "Mejor venta", "Indicadores"])

        symbol = self._extract_symbol(lines)
        asset_name = self._extract_asset_name(lines)
        last_price = self._extract_last_price(lines)
        daily_change_amount, daily_change_percent, daily_change_direction = self._extract_daily_change(lines)
        bid_levels, best_bid_quantity, best_bid_price = self._extract_bid_side(lines)
        ask_levels, best_ask_quantity, best_ask_price = self._extract_ask_side(lines)
        indicators = self._extract_indicators(lines)

        spread = round(best_ask_price - best_bid_price, 2)
        mid_price = round((best_bid_price + best_ask_price) / 2, 2)

        return StockSnapshot(
            symbol=symbol,
            asset_name=asset_name,
            last_price=last_price,
            daily_change_amount=daily_change_amount,
            daily_change_percent=daily_change_percent,
            daily_change_direction=daily_change_direction,
            previous_close=indicators["previous_close"],
            best_bid_price=best_bid_price,
            best_bid_quantity=best_bid_quantity,
            best_ask_price=best_ask_price,
            best_ask_quantity=best_ask_quantity,
            spread=spread,
            mid_price=mid_price,
            high_price=indicators["high_price"],
            low_price=indicators["low_price"],
            traded_value=indicators["traded_value"],
            traded_volume=indicators["traded_volume"],
            bid_levels=bid_levels,
            ask_levels=ask_levels,
        )

    @staticmethod
    def _extract_symbol(lines: list[str]) -> str:
        for line in lines[:5]:
            if re.fullmatch(r"[A-Z0-9]{3,12}", line):
                return line
        raise ValueError("Could not extract symbol")

    @staticmethod
    def _extract_asset_name(lines: list[str]) -> str:
        for index, line in enumerate(lines):
            if line.startswith("Hoy "):
                for candidate in reversed(lines[:index]):
                    if "$" not in candidate and not candidate.startswith("(") and not re.fullmatch(r"[A-Z0-9]{3,12}", candidate):
                        return candidate
        raise ValueError("Could not extract asset name")

    @staticmethod
    def _extract_last_price(lines: list[str]) -> float:
        for index, line in enumerate(lines):
            if line.startswith("Hoy "):
                for candidate in reversed(lines[:index]):
                    if "$" in candidate:
                        return parse_money(candidate)
        raise ValueError("Could not extract last price")

    @staticmethod
    def _extract_daily_change(lines: list[str]) -> tuple[float, float, str]:
        for line in lines:
            match = re.match(r"Hoy\s+(subi[oó]|baj[oó])\s+\$\s*([\d\.,]+)\s+\(([-+\d\.,]+)%\)", line)
            if match:
                direction = "up" if "sub" in match.group(1).lower() else "down"
                return parse_money(match.group(2)), parse_percent(match.group(3)), direction
        return 0.0, 0.0, "flat"

    def _extract_bid_side(self, lines: list[str]) -> tuple[list[OrderBookLevel], int, float]:
        best_bid_idx = lines.index("Mejor compra")
        best_bid_match = re.match(r"(\d+)\s*[•-]\s*\$\s*([\d\.,]+)", lines[best_bid_idx + 1])
        if not best_bid_match:
            raise ValueError("Could not parse best bid row")

        header_index = self._find_header_index(lines, best_bid_idx, "Compra")
        start_index = header_index + 1
        end_index = lines.index("Mejor venta")
        levels = self._extract_levels(lines[start_index:end_index])
        return levels, int(best_bid_match.group(1)), parse_money(best_bid_match.group(2))

    def _extract_ask_side(self, lines: list[str]) -> tuple[list[OrderBookLevel], int, float]:
        best_ask_idx = lines.index("Mejor venta")
        best_ask_match = re.match(r"(\d+)\s*[•-]\s*\$\s*([\d\.,]+)", lines[best_ask_idx + 1])
        if not best_ask_match:
            raise ValueError("Could not parse best ask row")

        header_index = self._find_header_index(lines, best_ask_idx, "Venta")
        start_index = header_index + 1
        end_index = lines.index("Indicadores")
        levels = self._extract_levels(lines[start_index:end_index])
        return levels, int(best_ask_match.group(1)), parse_money(best_ask_match.group(2))

    @staticmethod
    def _find_header_index(lines: list[str], start_index: int, side_label: str) -> int:
        for index in range(start_index, min(start_index + 5, len(lines))):
            if lines[index].startswith("Cantidad") and side_label in lines[index]:
                return index
        raise ValueError(f"Could not find table header for {side_label}")

    @staticmethod
    def _extract_levels(raw_lines: list[str]) -> list[OrderBookLevel]:
        levels: list[OrderBookLevel] = []
        for index, line in enumerate(raw_lines, start=1):
            match = re.match(r"(\d+)\s+\$\s*([\d\.,]+)", line)
            if not match:
                continue
            levels.append(
                OrderBookLevel(
                    level=index,
                    quantity=parse_int(match.group(1)),
                    price=parse_money(match.group(2)),
                )
            )
        if not levels:
            raise ValueError("No order book levels found")
        return levels

    @staticmethod
    def _extract_indicators(lines: list[str]) -> dict[str, float | int]:
        indicator_key_map = {
            "Cierre anterior": "previous_close",
            "Mejor compra": "best_bid",
            "Mejor venta": "best_ask",
            "Precio máximo": "high_price",
            "Precio mínimo": "low_price",
            "Valor volumen": "traded_value",
            "Volumen": "traded_volume",
        }
        indicators: dict[str, float | int] = {}
        start_index = lines.index("Indicadores") + 1
        index = start_index
        while index < len(lines) - 1:
            key = lines[index]
            value = lines[index + 1]
            if key not in indicator_key_map:
                index += 1
                continue
            normalized_key = indicator_key_map[key]
            if normalized_key == "traded_volume":
                indicators[normalized_key] = parse_int(value)
            else:
                indicators[normalized_key] = parse_money(value)
            index += 2

        required = {"previous_close", "high_price", "low_price", "traded_value", "traded_volume"}
        missing = required - indicators.keys()
        if missing:
            raise ValueError(f"Missing indicator values: {sorted(missing)}")
        return indicators
