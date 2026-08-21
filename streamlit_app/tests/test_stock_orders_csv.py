from __future__ import annotations

import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from trii_ingestion.services.stock_orders_csv import StockOrdersCsvService


class StockOrdersCsvServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StockOrdersCsvService()
        self.sample_bytes = (APP_DIR.parent / "orders-trii.csv").read_bytes()

    def test_parses_orders_csv_example(self) -> None:
        result = self.service.parse(raw_bytes=self.sample_bytes)

        self.assertGreater(result.record_count, 0)
        self.assertIn("NUCO", result.symbols)
        self.assertEqual(result.columns[0], "Fecha y hora")
        self.assertTrue(result.storage_name.startswith("stock-order-"))
        self.assertTrue(result.storage_name.endswith("-america-bogota-trii.csv"))
        self.assertTrue(result.source_file_checksum)
        self.assertEqual(result.preview_rows[0]["created_at"], "2026-08-14T09:38:00-05:00")
        self.assertEqual(result.records[0]["created_at"], "2026-08-14T09:38:00-05:00")
        self.assertNotIn("ordered_at", result.records[0])
        self.assertEqual(result.records[0]["created_month"], "2026-08")

    def test_rejects_csv_with_missing_columns(self) -> None:
        bad_csv = b"Fecha y hora,S\xc3\xadmbolo de la acci\xc3\xb3n\n14 ago 2026,NUCO\n"

        with self.assertRaises(ValueError):
            self.service.parse(raw_bytes=bad_csv)


if __name__ == "__main__":
    unittest.main()
