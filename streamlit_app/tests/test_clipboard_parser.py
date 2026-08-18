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
from trii_ingestion.services.reconciliation import ReconciliationService
from trii_ingestion.parsers.common import parse_signal

from .sample_inputs import (
    STOCK_SNAPSHOT_TEXT,
    SUPPORT_AND_RESISTANCE_TEXT,
    TECHNICAL_MOVING_AVERAGES_TEXT,
    TECHNICAL_OSCILLATORS_TEXT,
)


class ClipboardParserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ClipboardParserService()
        self.reconciliation_service = ReconciliationService()
        self.stock_snapshot_document = self.service.parse(
            STOCK_SNAPSHOT_TEXT,
            SectionType.STOCK_SNAPSHOT,
        ).document
        self.asset_context = self.service.asset_context_from_documents(
            {SectionType.STOCK_SNAPSHOT.value: self.stock_snapshot_document}
        )

    def test_classifies_stock_snapshot(self) -> None:
        result = self.service.classify(STOCK_SNAPSHOT_TEXT)
        self.assertEqual(result.section, SectionType.STOCK_SNAPSHOT)

    def test_classifies_technical_oscillators(self) -> None:
        result = self.service.classify(TECHNICAL_OSCILLATORS_TEXT)
        self.assertEqual(result.section, SectionType.TECHNICAL_OSCILLATORS)

    def test_classifies_technical_moving_averages(self) -> None:
        result = self.service.classify(TECHNICAL_MOVING_AVERAGES_TEXT)
        self.assertEqual(result.section, SectionType.TECHNICAL_MOVING_AVERAGES)

    def test_classifies_support_and_resistance(self) -> None:
        result = self.service.classify(SUPPORT_AND_RESISTANCE_TEXT)
        self.assertEqual(result.section, SectionType.SUPPORT_AND_RESISTANCE)

    def test_parses_stock_snapshot_against_fixture(self) -> None:
        parsed = self.service.parse(STOCK_SNAPSHOT_TEXT, SectionType.STOCK_SNAPSHOT)
        expected = self._load_fixture(
            "fixtures/trii/stocks/pfaval/stock_snapshot/pfaval-aval_preferencial.json"
        )
        self.assertEqual(parsed.document.model_dump(mode="json"), expected)

    def test_parses_technical_oscillators_against_fixture(self) -> None:
        parsed = self.service.parse(
            TECHNICAL_OSCILLATORS_TEXT,
            SectionType.TECHNICAL_OSCILLATORS,
            asset_context=self.asset_context,
        )
        expected = self._load_fixture(
            "fixtures/trii/stocks/pfaval/technical_oscillators/pfaval-aval_preferencial.json"
        )
        self.assertEqual(parsed.document.model_dump(mode="json"), expected)

    def test_parses_technical_moving_averages_against_fixture(self) -> None:
        parsed = self.service.parse(
            TECHNICAL_MOVING_AVERAGES_TEXT,
            SectionType.TECHNICAL_MOVING_AVERAGES,
            asset_context=self.asset_context,
        )
        expected = self._load_fixture(
            "fixtures/trii/stocks/pfaval/technical_moving_averages/pfaval-aval_preferencial.json"
        )
        self.assertEqual(parsed.document.model_dump(mode="json"), expected)

    def test_parses_support_and_resistance_against_fixture(self) -> None:
        parsed = self.service.parse(
            SUPPORT_AND_RESISTANCE_TEXT,
            SectionType.SUPPORT_AND_RESISTANCE,
            asset_context=self.asset_context,
        )
        expected = self._load_fixture(
            "fixtures/trii/stocks/pfaval/support_and_resistance/pfaval-aval_preferencial.json"
        )
        self.assertEqual(parsed.document.model_dump(mode="json"), expected)

    def test_validation_detects_missing_indicator_block_in_stock_snapshot(self) -> None:
        broken_text = STOCK_SNAPSHOT_TEXT.replace("Indicadores", "")
        report = self.service.validate(broken_text, SectionType.STOCK_SNAPSHOT)
        self.assertFalse(report.is_valid)
        self.assertTrue(any(issue.code == "missing_indicators_heading" for issue in report.issues))

    def test_validation_detects_missing_long_term_block(self) -> None:
        broken_text = SUPPORT_AND_RESISTANCE_TEXT.split("Soporte y resistencia a largo plazo")[0].strip()
        report = self.service.validate(broken_text, SectionType.SUPPORT_AND_RESISTANCE)
        self.assertFalse(report.is_valid)
        self.assertTrue(any(issue.code == "missing_long_term_heading" for issue in report.issues))

    def test_reconciliation_builds_single_payload(self) -> None:
        documents = {
            SectionType.STOCK_SNAPSHOT.value: self.stock_snapshot_document,
            SectionType.TECHNICAL_OSCILLATORS.value: self.service.parse(
                TECHNICAL_OSCILLATORS_TEXT,
                SectionType.TECHNICAL_OSCILLATORS,
                asset_context=self.asset_context,
            ).document,
            SectionType.TECHNICAL_MOVING_AVERAGES.value: self.service.parse(
                TECHNICAL_MOVING_AVERAGES_TEXT,
                SectionType.TECHNICAL_MOVING_AVERAGES,
                asset_context=self.asset_context,
            ).document,
            SectionType.SUPPORT_AND_RESISTANCE.value: self.service.parse(
                SUPPORT_AND_RESISTANCE_TEXT,
                SectionType.SUPPORT_AND_RESISTANCE,
                asset_context=self.asset_context,
            ).document,
        }
        consolidated = self.reconciliation_service.reconcile(documents).document
        self.assertEqual(consolidated.symbol, "PFAVAL")
        self.assertEqual(consolidated.timezone, "America/Bogota")
        self.assertTrue(consolidated.captured_at.endswith("-05:00"))

    def test_reconciliation_fails_when_a_contract_is_missing(self) -> None:
        documents = {
            SectionType.STOCK_SNAPSHOT.value: self.stock_snapshot_document
        }
        with self.assertRaises(ValueError):
            self.reconciliation_service.reconcile(documents)

    def test_non_stock_contract_requires_asset_context(self) -> None:
        with self.assertRaises(ValueError):
            self.service.parse(
                TECHNICAL_OSCILLATORS_TEXT,
                SectionType.TECHNICAL_OSCILLATORS,
            )

    def test_parse_signal_supports_strong_variants(self) -> None:
        self.assertEqual(parse_signal("Compra fuerte").value, "strong_buy")
        self.assertEqual(parse_signal("Venta fuerte").value, "strong_sell")
        self.assertEqual(parse_signal("Compra fuerte ↑").value, "strong_buy")
        self.assertEqual(parse_signal("Venta fuerte ↓").value, "strong_sell")
        self.assertEqual(parse_signal("Compra ↑").value, "buy")
        self.assertEqual(parse_signal("Venta ↓").value, "sell")

    def test_technical_indicator_preserves_raw_signal(self) -> None:
        parsed = self.service.parse(
            TECHNICAL_MOVING_AVERAGES_TEXT,
            SectionType.TECHNICAL_MOVING_AVERAGES,
            asset_context=self.asset_context,
        )
        momentum = next(
            indicator for indicator in parsed.document.indicators if indicator.key == "momentum_14"
        )
        self.assertEqual(momentum.raw_signal, "Compra")
        self.assertEqual(momentum.signal.value, "buy")

    @staticmethod
    def _load_fixture(relative_path: str) -> dict:
        path = APP_DIR / relative_path
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
