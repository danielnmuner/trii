from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers import StockSnapshotParser
from trii_ingestion.parsers.base import TextParser
from trii_ingestion.validation import ValidationReport, ValidationService


@dataclass(frozen=True)
class ClassificationResult:
    section: SectionType | None
    confidence: float
    reasons: list[str]


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
        self._parsers = parsers or [StockSnapshotParser()]
        self._validation_service = validation_service or ValidationService()

    def classify(self, text: str) -> ClassificationResult:
        parser = self._parsers[0]
        confidence, reasons = parser.score(text)
        return ClassificationResult(
            section=parser.section if confidence > 0 else None,
            confidence=confidence,
            reasons=reasons,
        )

    def parse(
        self,
        text: str,
        section: SectionType | None = None,
    ) -> ParsedDocument:
        target_section = section or self.classify(text).section
        if target_section is None:
            raise ValueError("Could not classify clipboard text")
        if target_section != SectionType.STOCK_SNAPSHOT:
            raise ValueError("Solo se soporta el contrato `stock_snapshot`.")

        parser = self._parser_by_section(target_section)
        return ParsedDocument(section=target_section, document=parser.parse(text))

    def validate(self, text: str, section: SectionType) -> ValidationReport:
        return self._validation_service.validate(text, section)

    def _parser_by_section(self, section: SectionType) -> TextParser:
        for parser in self._parsers:
            if parser.section == section:
                return parser
        raise ValueError(f"No parser registered for section: {section}")
