from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
MIGRATOR_SRC = (
    ROOT_DIR
    / "infra"
    / "prod"
    / "services"
    / "lambda"
    / "historic-stats-summary-migrator"
    / "src"
)
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

_module_spec = importlib.util.spec_from_file_location(
    "historic_stats_summary_migrator_handler",
    MIGRATOR_SRC / "handler.py",
)
if _module_spec is None or _module_spec.loader is None:
    raise RuntimeError("No fue posible cargar historic-stats-summary-migrator handler.")

_module = importlib.util.module_from_spec(_module_spec)
sys.modules[_module_spec.name] = _module
_module_spec.loader.exec_module(_module)


class FakeHistoricStatsTable:
    def __init__(self) -> None:
        self.items = {
            ("NUCO", "vwap"): {
                "pk": "NUCO",
                "sk": "vwap",
                "symbol": "NUCO",
                "metric": "vwap",
                "stddev": 12.5,
                "sample_count": 120,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
            ("NUCO", "spread_bps"): {
                "pk": "NUCO",
                "sk": "spread_bps",
                "symbol": "NUCO",
                "metric": "spread_bps",
                "latest_value": 5.5,
                "mean": 4.9,
                "stddev": 0.3,
                "sample_count": 120,
                "min_value": 4.4,
                "max_value": 5.7,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
            ("NUCO", "obi_l1"): {
                "pk": "NUCO",
                "sk": "obi_l1",
                "symbol": "NUCO",
                "metric": "obi_l1",
                "latest_value": 0.4,
                "mean": 0.1,
                "stddev": 0.05,
                "sample_count": 120,
                "min_value": -0.4,
                "max_value": 0.6,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
            ("NUCO", "obi_top_5"): {
                "pk": "NUCO",
                "sk": "obi_top_5",
                "symbol": "NUCO",
                "metric": "obi_top_5",
                "latest_value": 0.2,
                "mean": 0.15,
                "stddev": 0.07,
                "sample_count": 120,
                "min_value": -0.3,
                "max_value": 0.5,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
            ("NUCO", "traded_volume"): {
                "pk": "NUCO",
                "sk": "traded_volume",
                "symbol": "NUCO",
                "metric": "traded_volume",
                "latest_value": 1000,
                "mean": 850,
                "stddev": 100,
                "sample_count": 120,
                "min_value": 100,
                "max_value": 1000,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
            ("NUCO", "traded_value"): {
                "pk": "NUCO",
                "sk": "traded_value",
                "symbol": "NUCO",
                "metric": "traded_value",
                "latest_value": 2500000,
                "mean": 1800000,
                "stddev": 250000,
                "sample_count": 120,
                "min_value": 150000,
                "max_value": 2500000,
                "stats_version": 9,
                "last_source_captured_at": "2026-09-04T15:00:00-05:00",
            },
        }
        self.put_items: list[dict] = []
        self.deleted_keys: list[dict] = []

    def scan(self, **kwargs) -> dict:
        return {"Items": [{"pk": pk, "sk": sk} for pk, sk in self.items]}

    def query(self, **kwargs) -> dict:
        symbol = getattr(kwargs["KeyConditionExpression"], "_values")[1]
        return {
            "Items": [
                dict(item)
                for (pk, _sk), item in self.items.items()
                if pk == symbol
            ]
        }

    def put_item(self, *, Item: dict) -> None:
        self.put_items.append(Item)
        self.items[(Item["pk"], Item["sk"])] = dict(Item)

    def batch_writer(self):
        table = self

        class _BatchWriter:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def delete_item(self, *, Key: dict) -> None:
                table.deleted_keys.append(Key)
                table.items.pop((Key["pk"], Key["sk"]), None)

        return _BatchWriter()


def test_migrator_creates_stats_summary_item() -> None:
    fake_table = FakeHistoricStatsTable()
    _module.HISTORIC_STATS_TABLE = fake_table

    response = _module.handler({"mode": "migrate", "symbol": "NUCO"}, None)

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["migrated_symbols"] == 1
    assert payload["invalid_symbols"] == 0
    assert len(fake_table.put_items) == 1
    summary_item = fake_table.put_items[0]
    assert summary_item["pk"] == "NUCO"
    assert summary_item["sk"] == "stats_summary"
    assert summary_item["metric_count"] == 6
    assert summary_item["migration_status"] == "complete"
    assert summary_item["metrics"]["vwap"]["sample_count"] == 120
    assert summary_item["metrics"]["spread_bps"]["latest_value"] == 5.5


def test_migrator_validate_mode_confirms_existing_summary() -> None:
    fake_table = FakeHistoricStatsTable()
    _module.HISTORIC_STATS_TABLE = fake_table
    _module.handler({"mode": "migrate", "symbol": "NUCO"}, None)

    response = _module.handler({"mode": "validate", "symbol": "NUCO"}, None)

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["processed_symbols"] == 1
    assert payload["skipped_symbols"] == 1
    assert payload["results"][0]["valid"] is True


def test_migrator_cleanup_requires_validated_summary() -> None:
    fake_table = FakeHistoricStatsTable()
    _module.HISTORIC_STATS_TABLE = fake_table
    _module.handler({"mode": "migrate", "symbol": "NUCO"}, None)

    response = _module.handler(
        {
            "mode": "cleanup",
            "symbol": "NUCO",
            "confirm_delete_legacy": True,
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["deleted_legacy_items"] == 6
    assert len(fake_table.deleted_keys) == 6
    assert ("NUCO", "stats_summary") in fake_table.items
