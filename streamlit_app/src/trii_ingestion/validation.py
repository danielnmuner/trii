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
                        message="No se detectó texto para el contrato de resumen de la acción.",
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
                        message="La fila de `Mejor compra` está incompleta o tiene un formato no reconocido.",
                        hint="La línea esperada debe parecerse a `33636 • $ 822,00`.",
                    )
                )

        if "Mejor venta" in lines:
            index = lines.index("Mejor venta")
            if index + 1 >= len(lines) or not re.match(r"^\d+\s*[•-]\s*\$\s*[\d\.,]+$", lines[index + 1]):
                issues.append(
                    ValidationIssue(
                        code="invalid_best_ask_row",
                        message="La fila de `Mejor venta` está incompleta o tiene un formato no reconocido.",
                        hint="La línea esperada debe parecerse a `43067 • $ 846,00`.",
                    )
                )

        self._require_side_table(lines, "Mejor compra", "Mejor venta", "Compra", "bid", issues)
        self._require_side_table(lines, "Mejor venta", "Indicadores", "Venta", "ask", issues)

        required_indicators = [
            "Cierre anterior",
            "Mejor compra",
            "Mejor venta",
            "Precio máximo",
            "Precio mínimo",
            "Valor volumen",
            "Volumen",
        ]
        for indicator in required_indicators:
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


class TechnicalOscillatorsValidator(ContractValidator):
    section = SectionType.TECHNICAL_OSCILLATORS

    def validate(self, text: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        lines = clean_lines(text)
        if not lines:
            return ValidationReport(
                section=self.section,
                issues=[
                    ValidationIssue(
                        code="empty_text",
                        message="No se detectó texto para el contrato de osciladores.",
                        hint="Copia todo el bloque desde `Osciladores` hasta la última fila del cuadro.",
                    )
                ],
            )

        expected_lines = [
            ("Osciladores", "missing_heading", "Falta el encabezado `Osciladores`."),
            ("Actualizado el", "missing_updated_at", "Falta la línea de actualización."),
            ("Compra", "missing_buy_summary", "Falta el total de señales de compra."),
            ("Mantener", "missing_hold_summary", "Falta el total de señales de mantener."),
            ("Venta", "missing_sell_summary", "Falta el total de señales de venta."),
            ("Detalles técnicos", "missing_details_heading", "Falta el encabezado `Detalles técnicos`."),
        ]
        for expected, code, message in expected_lines:
            if not any(line.startswith(expected) for line in lines):
                issues.append(
                    ValidationIssue(
                        code=code,
                        message=message,
                        hint="Copia el bloque completo de osciladores, incluyendo el resumen superior y la tabla.",
                    )
                )

        expected_indicators = [
            "RSI 7",
            "RSI 21",
            "RSI 50",
            "RSI 200",
            "Estocástico Lento D",
            "Estocástico Rápido D",
            "MACD",
            "Williams %R",
        ]
        for indicator in expected_indicators:
            if not any(line.startswith(indicator) for line in lines):
                issues.append(
                    ValidationIssue(
                        code=f"missing_{indicator}",
                        message=f"Falta la fila del indicador `{indicator}`.",
                        hint="Evita copiar solo una parte de la tabla; incluye todas las filas del cuadro técnico.",
                    )
                )

        return ValidationReport(section=self.section, issues=issues)


class TechnicalMovingAveragesValidator(ContractValidator):
    section = SectionType.TECHNICAL_MOVING_AVERAGES

    def validate(self, text: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        lines = clean_lines(text)
        if not lines:
            return ValidationReport(
                section=self.section,
                issues=[
                    ValidationIssue(
                        code="empty_text",
                        message="No se detectó texto para el contrato de medias móviles.",
                        hint="Copia todo el bloque desde `Media Móvil` hasta `Bollinger Down`.",
                    )
                ],
            )

        expected_lines = [
            ("Media Móvil", "missing_heading", "Falta el encabezado `Media Móvil`."),
            ("Actualizado el", "missing_updated_at", "Falta la línea de actualización."),
            ("Compra", "missing_buy_summary", "Falta el total de señales de compra."),
            ("Mantener", "missing_hold_summary", "Falta el total de señales de mantener."),
            ("Venta", "missing_sell_summary", "Falta el total de señales de venta."),
            ("Detalles técnicos", "missing_details_heading", "Falta el encabezado `Detalles técnicos`."),
        ]
        for expected, code, message in expected_lines:
            if not any(line.startswith(expected) for line in lines):
                issues.append(
                    ValidationIssue(
                        code=code,
                        message=message,
                        hint="Copia el bloque completo de medias móviles, incluyendo resumen y tabla.",
                    )
                )

        expected_indicators = [
            "MMS 7",
            "MMS 21",
            "MMS 200",
            "Momento 14",
            "Bollinger Up",
            "Bollinger Down",
        ]
        for indicator in expected_indicators:
            if not any(line.startswith(indicator) for line in lines):
                issues.append(
                    ValidationIssue(
                        code=f"missing_{indicator}",
                        message=f"Falta la fila del indicador `{indicator}`.",
                        hint="La selección debe incluir todas las filas visibles de la tabla técnica.",
                    )
                )

        return ValidationReport(section=self.section, issues=issues)


class SupportAndResistanceValidator(ContractValidator):
    section = SectionType.SUPPORT_AND_RESISTANCE

    def validate(self, text: str) -> ValidationReport:
        issues: list[ValidationIssue] = []
        lines = clean_lines(text)
        if not lines:
            return ValidationReport(
                section=self.section,
                issues=[
                    ValidationIssue(
                        code="empty_text",
                        message="No se detectó texto para el contrato de soportes y resistencias.",
                        hint="Copia desde `Soporte y resistencia diario` hasta el final del comentario de largo plazo.",
                    )
                ],
            )

        if "Soporte y resistencia diario" not in lines:
            issues.append(
                ValidationIssue(
                    code="missing_daily_heading",
                    message="Falta el encabezado `Soporte y resistencia diario`.",
                    hint="Este contrato siempre debe incluir primero el bloque diario.",
                )
            )
        if "Soporte y resistencia a largo plazo" not in lines:
            issues.append(
                ValidationIssue(
                    code="missing_long_term_heading",
                    message="Falta el encabezado `Soporte y resistencia a largo plazo`.",
                    hint="No cortes el texto antes del segundo bloque de análisis.",
                )
            )

        close_price_lines = [line for line in lines if line.startswith("Precio de cierre")]
        if len(close_price_lines) < 2:
            issues.append(
                ValidationIssue(
                    code="missing_close_prices",
                    message="Se esperaban dos líneas de `Precio de cierre` y no se encontraron completas.",
                    hint="Debe haber una para el bloque diario y otra para el bloque de largo plazo.",
                )
            )

        row_pattern = re.compile(r"^(Resistencia|Soporte)\s+\d\s+\$\s*[\d\.,]+\s+[+-]?[\d\.,]+%$")
        valid_rows = [line for line in lines if row_pattern.match(line)]
        if len(valid_rows) < 8:
            issues.append(
                ValidationIssue(
                    code="insufficient_level_rows",
                    message=f"Se detectaron solo {len(valid_rows)} filas válidas de soportes y resistencias.",
                    hint="La captura esperada incluye cuatro niveles del bloque diario y cuatro del bloque de largo plazo.",
                )
            )

        return ValidationReport(section=self.section, issues=issues)


class ValidationService:
    def __init__(self, validators: list[ContractValidator] | None = None) -> None:
        self._validators = validators or [
            StockSnapshotValidator(),
            TechnicalOscillatorsValidator(),
            TechnicalMovingAveragesValidator(),
            SupportAndResistanceValidator(),
        ]

    def validate(self, text: str, section: SectionType) -> ValidationReport:
        validator = self._validator_by_section(section)
        return validator.validate(text)

    def _validator_by_section(self, section: SectionType) -> ContractValidator:
        for validator in self._validators:
            if validator.section == section:
                return validator
        raise ValueError(f"No validator registered for section: {section}")
