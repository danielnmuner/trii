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

    def test_rejects_invalid_archive_payload(self) -> None:
        with self.assertRaises(ValueError):
            self.service.inspect_archives(archives=[("broken.zip", b"not-a-zip")])


if __name__ == "__main__":
    unittest.main()
