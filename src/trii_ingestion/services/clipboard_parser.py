from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers import (
    StockSnapshotParser,
    SupportAndResistanceParser,
    TechnicalMovingAveragesParser,
    TechnicalOscillatorsParser,
)
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.validation import ValidationReport, ValidationService


@dataclass(frozen=True)
class ClassificationResult:
    section: SectionType | None
    confidence: float
    reasons: list[str]


@dataclass(frozen=True)
class AssetContext:
    symbol: str
    asset_name: str
    currency: str


@dataclass(frozen=True)
class ParsedDocument:
    section: SectionType
    document: BaseModel


class ClipboardParserService:
    def __init__(
        self,
        parsers: list[TextParser] | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self._parsers = parsers or [
            StockSnapshotParser(),
            TechnicalOscillatorsParser(),
            TechnicalMovingAveragesParser(),
            SupportAndResistanceParser(),
        ]
        self._validation_service = validation_service or ValidationService()

    def classify(self, text: str) -> ClassificationResult:
        best_section: SectionType | None = None
        best_confidence = 0.0
        best_reasons: list[str] = []

        for parser in self._parsers:
            confidence, reasons = parser.score(text)
            if confidence > best_confidence:
                best_section = parser.section
                best_confidence = confidence
                best_reasons = reasons

        return ClassificationResult(
            section=best_section,
            confidence=best_confidence,
            reasons=best_reasons,
        )

    def parse(
        self,
        text: str,
        section: SectionType | None = None,
        asset_context: AssetContext | None = None,
    ) -> ParsedDocument:
        target_section = section or self.classify(text).section
        if target_section is None:
            raise ValueError("Could not classify clipboard text")

        parser = self._parser_by_section(target_section)
        document = parser.parse(text)
        if target_section != SectionType.STOCK_SNAPSHOT:
            if asset_context is None:
                raise ValueError("El contexto del activo es obligatorio para contratos distintos al resumen de la acción.")
            document = document.model_copy(
                update={
                    "symbol": asset_context.symbol,
                    "asset_name": asset_context.asset_name,
                    "currency": asset_context.currency,
                }
            )
        return ParsedDocument(section=target_section, document=document)

    def validate(self, text: str, section: SectionType) -> ValidationReport:
        return self._validation_service.validate(text, section)

    @staticmethod
    def asset_context_from_documents(documents: dict[str, BaseModel]) -> AssetContext | None:
        stock_snapshot = documents.get(SectionType.STOCK_SNAPSHOT.value)
        if stock_snapshot is None:
            return None
        return AssetContext(
            symbol=getattr(stock_snapshot, "symbol"),
            asset_name=getattr(stock_snapshot, "asset_name"),
            currency=getattr(stock_snapshot, "currency"),
        )

    def _parser_by_section(self, section: SectionType) -> TextParser:
        for parser in self._parsers:
            if parser.section == section:
                return parser
        raise ValueError(f"No parser registered for section: {section}")
