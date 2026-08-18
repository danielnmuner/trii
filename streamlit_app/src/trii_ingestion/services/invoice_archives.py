from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class InvoiceArchiveSummary:
    archive_name: str
    size_bytes: int
    xml_file_name: str
    pdf_file_name: str
    other_file_count: int
    suggested_s3_key: str


@dataclass(frozen=True)
class InvoiceArchivesUploadResult:
    captured_at: str
    timezone: str
    archive_count: int
    xml_count: int
    pdf_count: int
    preview_rows: tuple[dict[str, str | int], ...]


class InvoiceArchivesService:
    timezone_name = "America/Bogota"

    def inspect_archives(self, *, archives: list[tuple[str, bytes]]) -> InvoiceArchivesUploadResult:
        if not archives:
            raise ValueError("Debes cargar al menos un archivo ZIP de factura.")

        captured_at = datetime.now(ZoneInfo(self.timezone_name))
        archive_summaries = [
            self._inspect_single_archive(name=name, raw_bytes=raw_bytes, captured_at=captured_at)
            for name, raw_bytes in archives
        ]

        return InvoiceArchivesUploadResult(
            captured_at=captured_at.isoformat(),
            timezone=self.timezone_name,
            archive_count=len(archive_summaries),
            xml_count=len(archive_summaries),
            pdf_count=len(archive_summaries),
            preview_rows=tuple(
                {
                    "Archivo ZIP": summary.archive_name,
                    "XML detectado": summary.xml_file_name,
                    "PDF detectado": summary.pdf_file_name,
                    "Otros archivos": summary.other_file_count,
                    "Tamaño (bytes)": summary.size_bytes,
                    "S3 sugerido": summary.suggested_s3_key,
                }
                for summary in archive_summaries
            ),
        )

    def _inspect_single_archive(
        self,
        *,
        name: str,
        raw_bytes: bytes,
        captured_at: datetime,
    ) -> InvoiceArchiveSummary:
        try:
            with ZipFile(BytesIO(raw_bytes)) as zip_file:
                members = [
                    member
                    for member in zip_file.namelist()
                    if not member.endswith("/")
                ]
        except BadZipFile as exc:
            raise ValueError(f"El archivo `{name}` no es un ZIP válido.") from exc

        if not members:
            raise ValueError(f"El archivo `{name}` no contiene documentos internos.")

        xml_files = [member for member in members if member.lower().endswith(".xml")]
        pdf_files = [member for member in members if member.lower().endswith(".pdf")]

        if len(xml_files) != 1:
            raise ValueError(
                f"El archivo `{name}` debe contener exactamente un XML y se encontraron {len(xml_files)}."
            )
        if len(pdf_files) != 1:
            raise ValueError(
                f"El archivo `{name}` debe contener exactamente un PDF y se encontraron {len(pdf_files)}."
            )

        other_file_count = len(members) - len(xml_files) - len(pdf_files)

        return InvoiceArchiveSummary(
            archive_name=name,
            size_bytes=len(raw_bytes),
            xml_file_name=xml_files[0],
            pdf_file_name=pdf_files[0],
            other_file_count=other_file_count,
            suggested_s3_key=self._build_s3_key(captured_at=captured_at, archive_name=name),
        )

    @staticmethod
    def _build_s3_key(*, captured_at: datetime, archive_name: str) -> str:
        return (
            f"invoices/{captured_at.strftime('%Y/%m/%d')}/"
            f"{archive_name}"
        )
