from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from trii_ingestion.models.consolidated import (
    ConsolidatedSnapshot,
    ConsolidatedStockSnapshot,
    ConsolidatedSupportResistanceSnapshot,
    ConsolidatedTechnicalSnapshot,
)
from trii_ingestion.models.stock_snapshot import StockSnapshot
from trii_ingestion.models.support_and_resistance import SupportResistanceSnapshot
from trii_ingestion.models.technical import TechnicalIndicatorsSnapshot
from trii_ingestion.models.types import SectionType


@dataclass(frozen=True)
class ReconciliationResult:
    document: ConsolidatedSnapshot


class ReconciliationService:
    def __init__(self, timezone_name: str = "America/Bogota") -> None:
        self._timezone_name = timezone_name

    def reconcile(self, documents: dict[str, BaseModel]) -> ReconciliationResult:
        required_sections = [
            SectionType.STOCK_SNAPSHOT,
            SectionType.TECHNICAL_OSCILLATORS,
            SectionType.TECHNICAL_MOVING_AVERAGES,
            SectionType.SUPPORT_AND_RESISTANCE,
        ]
        missing_sections = [section.value for section in required_sections if section.value not in documents]
        if missing_sections:
            raise ValueError(
                "Faltan contratos obligatorios para consolidar el JSON final: "
                + ", ".join(missing_sections)
            )

        stock_snapshot = self._expect_type(documents[SectionType.STOCK_SNAPSHOT.value], StockSnapshot)
        technical_oscillators = self._expect_type(
            documents[SectionType.TECHNICAL_OSCILLATORS.value],
            TechnicalIndicatorsSnapshot,
        )
        technical_moving_averages = self._expect_type(
            documents[SectionType.TECHNICAL_MOVING_AVERAGES.value],
            TechnicalIndicatorsSnapshot,
        )
        support_and_resistance = self._expect_type(
            documents[SectionType.SUPPORT_AND_RESISTANCE.value],
            SupportResistanceSnapshot,
        )

        self._ensure_consistency(
            [
                stock_snapshot,
                technical_oscillators,
                technical_moving_averages,
                support_and_resistance,
            ]
        )
        self._cross_validate_market_data(
            stock_snapshot=stock_snapshot,
            technical_moving_averages=technical_moving_averages,
            support_and_resistance=support_and_resistance,
        )

        timezone = ZoneInfo(self._timezone_name)
        captured_at = datetime.now(timezone).isoformat()

        return ReconciliationResult(
            document=ConsolidatedSnapshot(
                symbol=stock_snapshot.symbol,
                asset_name=stock_snapshot.asset_name,
                currency=stock_snapshot.currency,
                captured_at=captured_at,
                timezone=self._timezone_name,
                stock_snapshot=ConsolidatedStockSnapshot(
                    **stock_snapshot.model_dump(exclude={"symbol", "asset_name", "currency"})
                ),
                technical_oscillators=ConsolidatedTechnicalSnapshot(
                    **technical_oscillators.model_dump(exclude={"symbol", "asset_name", "currency"})
                ),
                technical_moving_averages=ConsolidatedTechnicalSnapshot(
                    **technical_moving_averages.model_dump(exclude={"symbol", "asset_name", "currency"})
                ),
                support_and_resistance=ConsolidatedSupportResistanceSnapshot(
                    **support_and_resistance.model_dump(exclude={"symbol", "asset_name", "currency"})
                ),
            )
        )

    @staticmethod
    def _ensure_consistency(documents: list[BaseModel]) -> None:
        symbols = {getattr(document, "symbol", None) for document in documents}
        asset_names = {getattr(document, "asset_name", None) for document in documents}
        currencies = {getattr(document, "currency", None) for document in documents}

        if len(symbols) != 1:
            raise ValueError("Los contratos cargados no pertenecen al mismo símbolo.")
        if len(asset_names) != 1:
            raise ValueError("Los contratos cargados no pertenecen al mismo nombre de especie.")
        if len(currencies) != 1:
            raise ValueError("Los contratos cargados no comparten la misma moneda.")

    @staticmethod
    def _cross_validate_market_data(
        *,
        stock_snapshot: StockSnapshot,
        technical_moving_averages: TechnicalIndicatorsSnapshot,
        support_and_resistance: SupportResistanceSnapshot,
    ) -> None:
        issues: list[str] = []
        last_price = stock_snapshot.last_price
        close_price = support_and_resistance.daily.close_price

        if last_price <= 0:
            issues.append("El precio actual del resumen de la acción no es válido.")
        else:
            close_gap = abs(close_price - last_price) / last_price
            if close_gap > 0.2:
                issues.append(
                    "El precio de cierre de soportes y resistencias está demasiado lejos del precio actual del resumen."
                )

        moving_average_values = [indicator.value for indicator in technical_moving_averages.indicators]
        if moving_average_values and last_price > 0:
            near_price_count = sum(0.6 * last_price <= value <= 1.4 * last_price for value in moving_average_values)
            if near_price_count < max(3, len(moving_average_values) // 2):
                issues.append(
                    "Las medias móviles y bandas no guardan una relación razonable con el precio actual; revisa si pegaste otra acción."
                )

        support_prices = [level.price for level in support_and_resistance.daily.levels]
        if support_prices and last_price > 0:
            if not any(0.6 * last_price <= value <= 1.4 * last_price for value in support_prices):
                issues.append(
                    "Los niveles de soporte y resistencia no son coherentes con el precio actual de la acción."
                )

        if issues:
            raise ValueError(" ".join(issues))

    @staticmethod
    def _expect_type(document: BaseModel, expected_type: type[BaseModel]) -> BaseModel:
        if not isinstance(document, expected_type):
            raise TypeError(f"Tipo de documento inesperado: {type(document).__name__}")
        return document
