from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from trii_ingestion.models.types import SectionType
from trii_ingestion.parsers.common import clean_lines


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    hint: str


@dataclass(frozen=True)
class ValidationReport:
    section: SectionType
    issues: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.issues


class ContractValidator(ABC):
    section: SectionType

    @abstractmethod
    def validate(self, text: str) -> ValidationReport:
        raise NotImplementedError


class StockSnapshotValidator(ContractValidator):
    section = SectionType.STOCK_SNAPSHOT

    def validate(self, text: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        lines = clean_lines(text)
        if not lines:
            return ValidationReport(
                section=self.section,
                issues=[
                    ValidationIssue(
                        code="empty_text",
                        message="No se detecto texto para el contrato de indicadores principales.",
                        hint="Copia desde el ticker y el precio actual hasta el final del bloque de indicadores.",
                    )
                ],
            )

        self._require_line(
            lines,
            "Líneas de profundidad",
            issues,
            "missing_market_depth",
            "Falta el encabezado `Líneas de profundidad`.",
            "Verifica que copiaste el bloque técnico principal y no solo la parte superior de la ficha.",
        )
        self._require_line(
            lines,
            "Mejor compra",
            issues,
            "missing_best_bid_heading",
            "Falta el encabezado `Mejor compra`.",
            "Incluye el bloque completo de profundidad de mercado.",
        )
        self._require_line(
            lines,
            "Mejor venta",
            issues,
            "missing_best_ask_heading",
            "Falta el encabezado `Mejor venta`.",
            "Incluye tanto la parte de compra como la de venta.",
        )
        self._require_line(
            lines,
            "Indicadores",
            issues,
            "missing_indicators_heading",
            "Falta el bloque `Indicadores`.",
            "Debes copiar hasta `Volumen`, no solo las líneas de profundidad.",
        )

        if "Mejor compra" in lines:
            index = lines.index("Mejor compra")
            if index + 1 >= len(lines) or not re.match(r"^\d+\s*[•-]\s*\$\s*[\d\.,]+$", lines[index + 1]):
                issues.append(
                    ValidationIssue(
                        code="invalid_best_bid_row",
                        message="La fila de `Mejor compra` esta incompleta o tiene un formato no reconocido.",
                        hint="La línea esperada debe parecerse a `33636 • $ 822,00`.",
                    )
                )

        if "Mejor venta" in lines:
            index = lines.index("Mejor venta")
            if index + 1 >= len(lines) or not re.match(r"^\d+\s*[•-]\s*\$\s*[\d\.,]+$", lines[index + 1]):
                issues.append(
                    ValidationIssue(
                        code="invalid_best_ask_row",
                        message="La fila de `Mejor venta` esta incompleta o tiene un formato no reconocido.",
                        hint="La línea esperada debe parecerse a `43067 • $ 846,00`.",
                    )
                )

        self._require_side_table(lines, "Mejor compra", "Mejor venta", "Compra", "bid", issues)
        self._require_side_table(lines, "Mejor venta", "Indicadores", "Venta", "ask", issues)

        for indicator in (
            "Cierre anterior",
            "Mejor compra",
            "Mejor venta",
            "Precio máximo",
            "Precio mínimo",
            "Valor volumen",
            "Volumen",
        ):
            if indicator not in lines:
                issues.append(
                    ValidationIssue(
                        code=f"missing_indicator_{indicator}",
                        message=f"Falta el indicador `{indicator}`.",
                        hint="Asegúrate de copiar el bloque completo de indicadores sin recortar el final.",
                    )
                )

        return ValidationReport(section=self.section, issues=issues)

    @staticmethod
    def _require_line(
        lines: list[str],
        target: str,
        issues: list[ValidationIssue],
        code: str,
        message: str,
        hint: str,
    ) -> None:
        if target not in lines:
            issues.append(ValidationIssue(code=code, message=message, hint=hint))

    def _require_side_table(
        self,
        lines: list[str],
        start_label: str,
        end_label: str,
        side_label: str,
        code_prefix: str,
        issues: list[ValidationIssue],
    ) -> None:
        if start_label not in lines or end_label not in lines:
            return

        start_index = lines.index(start_label)
        end_index = lines.index(end_label)
        header_index = None
        for index in range(start_index, min(start_index + 5, len(lines))):
            if lines[index].startswith("Cantidad") and side_label in lines[index]:
                header_index = index
                break

        if header_index is None:
            issues.append(
                ValidationIssue(
                    code=f"missing_{code_prefix}_header",
                    message=f"Falta el encabezado `Cantidad {side_label}`.",
                    hint="Incluye también la cabecera de la tabla, no solo las filas numéricas.",
                )
            )
            return

        level_rows = [
            line for line in lines[header_index + 1 : end_index] if re.match(r"^\d+\s+\$\s*[\d\.,]+$", line)
        ]
        if len(level_rows) < 5:
            issues.append(
                ValidationIssue(
                    code=f"insufficient_{code_prefix}_rows",
                    message=f"Se detectaron solo {len(level_rows)} filas válidas en la tabla de `{side_label}`.",
                    hint="La captura esperada para este contrato debe incluir las cinco puntas visibles.",
                )
            )


class ValidationService:
    def __init__(self, validators: list[ContractValidator] | None = None) -> None:
        self._validators = validators or [StockSnapshotValidator()]

    def validate(self, text: str, section: SectionType) -> ValidationReport:
        validator = self._validator_by_section(section)
        return validator.validate(text)

    def _validator_by_section(self, section: SectionType) -> ContractValidator:
        for validator in self._validators:
            if validator.section == section:
                return validator
        raise ValueError(f"No validator registered for section: {section}")
