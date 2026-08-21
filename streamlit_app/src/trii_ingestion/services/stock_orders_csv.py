from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
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

BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}
SPANISH_DATETIME_PATTERN = re.compile(
    r"^\s*(?P<day>\d{1,2})\s+"
    r"(?P<month>[A-Za-záéíóúñÁÉÍÓÚÑ]{3,})\s+"
    r"(?P<year>\d{4}),\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+"
    r"(?P<meridiem>[ap])\.\s*m\.\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StockOrdersUploadResult:
    storage_name: str
    captured_at: str
    timezone: str
    record_count: int
    symbols: tuple[str, ...]
    columns: tuple[str, ...]
    preview_rows: tuple[dict[str, object], ...]
    records: tuple[dict[str, object], ...]
    source_file_checksum: str


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

        captured_at = datetime.now(BOGOTA_TIMEZONE)
        source_file_checksum = hashlib.sha256(raw_bytes).hexdigest()
        normalized_records = self._normalize_rows(
            rows,
            source_file_checksum=source_file_checksum,
        )
        unique_symbols = tuple(sorted({str(record["symbol"]) for record in normalized_records}))

        return StockOrdersUploadResult(
            storage_name=self._build_storage_name(captured_at),
            captured_at=captured_at.isoformat(),
            timezone=self.timezone_name,
            record_count=len(normalized_records),
            symbols=unique_symbols,
            columns=columns,
            preview_rows=tuple(self._build_preview_row(record) for record in normalized_records[:10]),
            records=tuple(normalized_records),
            source_file_checksum=source_file_checksum,
        )

    def _normalize_rows(
        self,
        rows: list[dict[str, str]],
        *,
        source_file_checksum: str,
    ) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        seen_checksums: set[str] = set()

        for line_number, row in enumerate(rows, start=2):
            record = self._normalize_row(
                row,
                source_file_checksum=source_file_checksum,
                source_line_number=line_number,
            )
            checksum = str(record["record_checksum"])
            if checksum in seen_checksums:
                raise ValueError(
                    "El CSV de movimientos contiene checksums duplicados dentro del mismo archivo; se rechaza el lote completo."
                )
            seen_checksums.add(checksum)
            records.append(record)

        return records

    def _normalize_row(
        self,
        row: dict[str, str],
        *,
        source_file_checksum: str,
        source_line_number: int,
    ) -> dict[str, object]:
        created_at = self._parse_created_at(row["Fecha y hora"])
        symbol = row["Símbolo de la acción"].strip().upper()
        record: dict[str, object] = {
            "source_file_checksum": source_file_checksum,
            "source_line_number": source_line_number,
            "created_at": created_at,
            "created_month": created_at[:7],
            "created_at_symbol": f"{created_at}#{symbol}",
            "symbol": symbol,
            "order_side": self._normalize_order_side(row["Tipo de orden"]),
            "raw_status": row["Estado"],
            "normalized_status": self._normalize_status(row["Estado"]),
            "requested_quantity": self._parse_requested_quantity(
                row["Acciones completadas"],
                row["Acciones pendientes"],
            ),
            "filled_quantity": self._parse_quantity(row["Acciones completadas"]),
            "pending_quantity": self._parse_quantity(row["Acciones pendientes"]),
            "price_per_share": self._parse_decimal_text(row["Precio por acción"]),
            "gross_amount": self._parse_decimal_text(row["Total invertido"]),
            "commission_amount": self._parse_decimal_text(row["Valor comisión"]),
            "net_amount": self._parse_decimal_text(row["Total estimado"]),
            "currency": "COP",
        }
        record["record_checksum"] = self._order_record_checksum(record)
        return record

    @staticmethod
    def _clean_row(row: dict[str, str | None]) -> dict[str, str]:
        return {key: (value or "").strip() for key, value in row.items()}

    @staticmethod
    def _build_storage_name(captured_at: datetime) -> str:
        timestamp = captured_at.strftime("%Y%m%dT%H%M%S")
        return f"stock-order-{timestamp}-america-bogota-trii.csv"

    @staticmethod
    def _build_preview_row(record: dict[str, object]) -> dict[str, object]:
        return {
            "created_at": record["created_at"],
            "symbol": record["symbol"],
            "order_side": record["order_side"],
            "status": record["normalized_status"],
            "requested_quantity": record["requested_quantity"],
            "filled_quantity": record["filled_quantity"],
            "pending_quantity": record["pending_quantity"],
            "price_per_share": record["price_per_share"],
            "gross_amount": record["gross_amount"],
            "commission_amount": record["commission_amount"],
            "net_amount": record["net_amount"],
        }

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

    @staticmethod
    def _parse_created_at(raw_value: str) -> str:
        match = SPANISH_DATETIME_PATTERN.match(raw_value)
        if not match:
            raise ValueError(f"Fecha y hora inválida: {raw_value}")

        month_key = match.group("month")[:3].lower()
        month = SPANISH_MONTHS.get(month_key)
        if month is None:
            raise ValueError(f"Mes no soportado en fecha: {raw_value}")

        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        meridiem = match.group("meridiem").lower()
        if meridiem == "p" and hour != 12:
            hour += 12
        if meridiem == "a" and hour == 12:
            hour = 0

        timestamp = datetime(
            year=int(match.group("year")),
            month=month,
            day=int(match.group("day")),
            hour=hour,
            minute=minute,
            tzinfo=BOGOTA_TIMEZONE,
        )
        return timestamp.isoformat()

    @staticmethod
    def _parse_decimal_text(raw_value: str) -> str:
        value = raw_value.strip().replace("$", "").replace(" ", "")
        if not value:
            return "0"
        if "," in value and "." in value:
            value = value.replace(",", "")
        elif "," in value:
            value = value.replace(",", ".")
        try:
            return str(Decimal(value))
        except InvalidOperation as exc:
            raise ValueError(f"Valor numérico inválido: {raw_value}") from exc

    @staticmethod
    def _parse_quantity(raw_value: str) -> int:
        value = raw_value.strip()
        if not value:
            return 0
        return int(value.split("/")[0])

    @classmethod
    def _parse_requested_quantity(cls, completed_value: str, pending_value: str) -> int:
        pending_quantity = cls._parse_quantity(pending_value)
        completed_clean = completed_value.strip()
        requested_hint = None

        if "/" in completed_clean:
            requested_hint = int(completed_clean.split("/", maxsplit=1)[1])

        filled_quantity = cls._parse_quantity(completed_clean)
        requested_quantity = filled_quantity + pending_quantity
        if requested_hint is not None:
            requested_quantity = max(requested_quantity, requested_hint)
        return requested_quantity

    @staticmethod
    def _normalize_status(raw_status: str) -> str:
        mapping = {
            "aprobado": "approved",
            "cancelado": "cancelled",
            "pendiente": "pending",
            "rechazado": "rejected",
        }
        return mapping.get(raw_status.strip().lower(), "unknown")

    @staticmethod
    def _normalize_order_side(raw_value: str) -> str:
        normalized = raw_value.strip().lower()
        if normalized == "compra":
            return "buy"
        if normalized == "venta":
            return "sell"
        raise ValueError(f"Tipo de orden no soportado: {raw_value}")

    @staticmethod
    def _order_record_checksum(record: dict[str, object]) -> str:
        canonical_payload = {
            "created_at": record["created_at"],
            "symbol": record["symbol"],
            "order_side": record["order_side"],
            "raw_status": record["raw_status"],
            "requested_quantity": record["requested_quantity"],
            "filled_quantity": record["filled_quantity"],
            "pending_quantity": record["pending_quantity"],
            "price_per_share": record["price_per_share"],
            "gross_amount": record["gross_amount"],
            "commission_amount": record["commission_amount"],
            "net_amount": record["net_amount"],
            "currency": record["currency"],
        }
        return hashlib.sha256(
            json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
