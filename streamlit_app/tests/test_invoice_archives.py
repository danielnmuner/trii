from __future__ import annotations

import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from trii_ingestion.services.invoice_archives import InvoiceArchivesService


class InvoiceArchivesServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = InvoiceArchivesService()
        invoice_dir = APP_DIR.parent / "invoices"
        self.samples = [
            (path.name, path.read_bytes())
            for path in sorted(invoice_dir.glob("*.zip"))[:2]
        ]

    def test_inspects_invoice_archives(self) -> None:
        result = self.service.inspect_archives(archives=self.samples)

        self.assertEqual(result.archive_count, 2)
        self.assertEqual(result.xml_count, 2)
        self.assertEqual(result.pdf_count, 2)
        self.assertEqual(len(result.preview_rows), 2)
        self.assertIn("XML destino S3", result.preview_rows[0])
        self.assertIn("PDF destino S3", result.preview_rows[0])

    def test_prepares_invoice_archives_with_extracted_documents(self) -> None:
        prepared = self.service.prepare_archives(archives=self.samples[:1])

        self.assertEqual(prepared.upload_result.archive_count, 1)
        self.assertEqual(len(prepared.documents), 1)
        document = prepared.documents[0]
        self.assertTrue(document.xml_file_name.lower().endswith(".xml"))
        self.assertTrue(document.pdf_file_name.lower().endswith(".pdf"))
        self.assertTrue(document.xml_s3_key.endswith(document.xml_file_name))
        self.assertTrue(document.pdf_s3_key.endswith(document.pdf_file_name))
        self.assertGreater(len(document.xml_bytes), 0)
        self.assertGreater(len(document.pdf_bytes), 0)

    def test_rejects_invalid_archive_payload(self) -> None:
        with self.assertRaises(ValueError):
            self.service.inspect_archives(archives=[("broken.zip", b"not-a-zip")])


if __name__ == "__main__":
    unittest.main()
