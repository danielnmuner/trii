from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = APP_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from trii_ingestion.models.types import SectionType
from trii_ingestion.services.clipboard_parser import ClipboardParserService

from .sample_inputs import STOCK_SNAPSHOT_TEXT


class ClipboardParserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ClipboardParserService()

    def test_classifies_stock_snapshot(self) -> None:
        result = self.service.classify(STOCK_SNAPSHOT_TEXT)
        self.assertEqual(result.section, SectionType.STOCK_SNAPSHOT)

    def test_parses_stock_snapshot_against_fixture(self) -> None:
        parsed = self.service.parse(STOCK_SNAPSHOT_TEXT, SectionType.STOCK_SNAPSHOT)
        expected = self._load_fixture(
            "fixtures/trii/stocks/pfaval/stock_snapshot/pfaval-aval_preferencial.json"
        )
        self.assertEqual(parsed.document.model_dump(mode="json"), expected)

    def test_validation_detects_missing_indicator_block_in_stock_snapshot(self) -> None:
        broken_text = STOCK_SNAPSHOT_TEXT.replace("Indicadores", "")
        report = self.service.validate(broken_text, SectionType.STOCK_SNAPSHOT)
        self.assertFalse(report.is_valid)
        self.assertTrue(any(issue.code == "missing_indicators_heading" for issue in report.issues))

    @staticmethod
    def _load_fixture(relative_path: str) -> dict:
        path = APP_DIR / relative_path
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
