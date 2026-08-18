from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PreparedInvoiceDocument:
    archive_name: str
    archive_stem: str
    xml_file_name: str
    pdf_file_name: str
    xml_bytes: bytes
    pdf_bytes: bytes
    xml_s3_key: str
    pdf_s3_key: str


@dataclass(frozen=True)
class InvoiceArchivesUploadResult:
    captured_at: str
    timezone: str
    archive_count: int
    xml_count: int
    pdf_count: int
    preview_rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class PreparedInvoiceArchives:
    upload_result: InvoiceArchivesUploadResult
    documents: tuple[PreparedInvoiceDocument, ...]


class InvoiceArchivesService:
    timezone_name = "America/Bogota"

    def prepare_archives(self, *, archives: list[tuple[str, bytes]]) -> PreparedInvoiceArchives:
        if not archives:
            raise ValueError("Debes cargar al menos un archivo ZIP de factura.")

        captured_at = datetime.now(ZoneInfo(self.timezone_name))
        documents = [
            self._prepare_single_archive(name=name, raw_bytes=raw_bytes, captured_at=captured_at)
            for name, raw_bytes in archives
        ]

        return PreparedInvoiceArchives(
            upload_result=InvoiceArchivesUploadResult(
                captured_at=captured_at.isoformat(),
                timezone=self.timezone_name,
                archive_count=len(documents),
                xml_count=len(documents),
                pdf_count=len(documents),
                preview_rows=tuple(
                    {
                        "Archivo ZIP": document.archive_name,
                        "XML detectado": document.xml_file_name,
                        "PDF detectado": document.pdf_file_name,
                        "XML destino S3": document.xml_s3_key,
                        "PDF destino S3": document.pdf_s3_key,
                    }
                    for document in documents
                ),
            ),
            documents=tuple(documents),
        )

    def inspect_archives(self, *, archives: list[tuple[str, bytes]]) -> InvoiceArchivesUploadResult:
        return self.prepare_archives(archives=archives).upload_result

    def _prepare_single_archive(
        self,
        *,
        name: str,
        raw_bytes: bytes,
        captured_at: datetime,
    ) -> PreparedInvoiceDocument:
        try:
            with ZipFile(BytesIO(raw_bytes)) as zip_file:
                members = [member for member in zip_file.namelist() if not member.endswith("/")]
                if not members:
                    raise ValueError(f"El archivo `{name}` no contiene documentos internos.")

                xml_members = [member for member in members if member.lower().endswith(".xml")]
                pdf_members = [member for member in members if member.lower().endswith(".pdf")]

                if len(xml_members) != 1:
                    raise ValueError(
                        f"El archivo `{name}` debe contener exactamente un XML y se encontraron {len(xml_members)}."
                    )
                if len(pdf_members) != 1:
                    raise ValueError(
                        f"El archivo `{name}` debe contener exactamente un PDF y se encontraron {len(pdf_members)}."
                    )

                xml_member = xml_members[0]
                pdf_member = pdf_members[0]
                archive_stem = PurePosixPath(name).stem
                xml_file_name = PurePosixPath(xml_member).name
                pdf_file_name = PurePosixPath(pdf_member).name

                return PreparedInvoiceDocument(
                    archive_name=name,
                    archive_stem=archive_stem,
                    xml_file_name=xml_file_name,
                    pdf_file_name=pdf_file_name,
                    xml_bytes=zip_file.read(xml_member),
                    pdf_bytes=zip_file.read(pdf_member),
                    xml_s3_key=self._build_s3_key(
                        captured_at=captured_at,
                        archive_stem=archive_stem,
                        file_name=xml_file_name,
                    ),
                    pdf_s3_key=self._build_s3_key(
                        captured_at=captured_at,
                        archive_stem=archive_stem,
                        file_name=pdf_file_name,
                    ),
                )
        except BadZipFile as exc:
            raise ValueError(f"El archivo `{name}` no es un ZIP válido.") from exc

    @staticmethod
    def _build_s3_key(*, captured_at: datetime, archive_stem: str, file_name: str) -> str:
        return f"invoices/{captured_at.strftime('%Y/%m/%d')}/{archive_stem}/{file_name}"
