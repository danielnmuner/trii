from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo


EXPECTED_STOCK_ORDER_COLUMNS: tuple[str, ...] = (
    "Fecha y hora",
    "Símbolo de la acción",
    "Tipo de orden",
    "Estado",
    "Acciones completadas",
    "Acciones pendientes",
    "Precio por acción",
    "Total invertido",
    "Valor comisión",
    "Total estimado",
)


@dataclass(frozen=True)
class StockOrdersUploadResult:
    storage_name: str
    captured_at: str
    timezone: str
    record_count: int
    symbols: tuple[str, ...]
    columns: tuple[str, ...]
    preview_rows: tuple[dict[str, str], ...]


class StockOrdersCsvService:
    timezone_name = "America/Bogota"

    def parse(self, *, raw_bytes: bytes) -> StockOrdersUploadResult:
        text = raw_bytes.decode("utf-8-sig").strip()
        if not text:
            raise ValueError("El archivo CSV está vacío.")

        reader = csv.DictReader(StringIO(text))
        columns = tuple(reader.fieldnames or ())
        self._validate_columns(columns)

        rows = [self._clean_row(row) for row in reader]
        rows = [row for row in rows if any(value for value in row.values())]
        if not rows:
            raise ValueError("El archivo CSV no contiene órdenes válidas.")

        captured_at = datetime.now(ZoneInfo(self.timezone_name))
        unique_symbols = tuple(sorted({row["Símbolo de la acción"] for row in rows if row["Símbolo de la acción"]}))

        return StockOrdersUploadResult(
            storage_name=self._build_storage_name(captured_at),
            captured_at=captured_at.isoformat(),
            timezone=self.timezone_name,
            record_count=len(rows),
            symbols=unique_symbols,
            columns=columns,
            preview_rows=tuple(rows[:10]),
        )

    @staticmethod
    def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
        return {key: (value or "").strip() for key, value in row.items()}

    @staticmethod
    def _build_storage_name(captured_at: datetime) -> str:
        timestamp = captured_at.strftime("%Y%m%dT%H%M%S")
        return f"stock-order-{timestamp}-america-bogota-trii.csv"

    @staticmethod
    def _validate_columns(columns: tuple[str, ...]) -> None:
        if columns == EXPECTED_STOCK_ORDER_COLUMNS:
            return

        missing_columns = [
            column for column in EXPECTED_STOCK_ORDER_COLUMNS if column not in columns
        ]
        unexpected_columns = [column for column in columns if column not in EXPECTED_STOCK_ORDER_COLUMNS]

        details: list[str] = []
        if missing_columns:
            details.append("faltan: " + ", ".join(missing_columns))
        if unexpected_columns:
            details.append("sobran: " + ", ".join(unexpected_columns))

        raise ValueError(
            "El CSV de órdenes no coincide con la estructura esperada de Trii; " + "; ".join(details) + "."
        )
