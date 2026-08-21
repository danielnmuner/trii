from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_FILE = (
    ROOT_DIR
    / "infra"
    / "prod"
    / "services"
    / "lambda"
    / "analytics-catalog-backfill"
    / "src"
    / "handler.py"
)

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("ANALYTICS_CATALOG_TABLE", "test-analytics-catalog")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

spec = importlib.util.spec_from_file_location("analytics_catalog_backfill_handler", LAMBDA_FILE)
assert spec is not None and spec.loader is not None
backfill_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backfill_handler)


class FakeCurrentSnapshotsTable:
    def __init__(self, snapshots_by_date: dict[str, list[dict]]) -> None:
        self.snapshots_by_date = snapshots_by_date
        self.probe_calls: list[str] = []

    def query(self, **query_kwargs):
        expression = str(query_kwargs["KeyConditionExpression"])
        trading_date = expression.split(" = ")[-1].strip().replace("'", "")
        self.probe_calls.append(trading_date)
        limit = query_kwargs.get("Limit")
        items = list(self.snapshots_by_date.get(trading_date, []))
        if limit is not None:
            items = items[:limit]
        return {"Items": items}


class FakeAnalyticsCatalogTable:
    def __init__(self, existing_item: dict | None = None) -> None:
        self.item = existing_item
        self.written_items: list[dict] = []

    def get_item(self, *, Key: dict) -> dict:
        assert Key == {"pk": "analytics_catalog"}
        if self.item is None:
            return {}
        return {"Item": dict(self.item)}

    def put_item(self, *, Item: dict) -> dict:
        self.written_items.append(dict(Item))
        self.item = dict(Item)
        return {}


def test_backfill_preview_uses_latest_available_trading_date() -> None:
    snapshots_by_date = {
        "2026-08-20": [
            {"symbol": "NUCO", "captured_at": "2026-08-20T14:55:00-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-20T15:00:00-05:00"},
            {"symbol": "ISA", "captured_at": "2026-08-20T14:58:00-05:00"},
        ]
    }
    backfill_handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable(snapshots_by_date)
    catalog_table = FakeAnalyticsCatalogTable()
    backfill_handler.ANALYTICS_CATALOG_TABLE = catalog_table
    backfill_handler._find_latest_trading_date = lambda lookback_days=14: "2026-08-20"
    backfill_handler._load_snapshots_for_trading_date = lambda trading_date: list(
        snapshots_by_date.get(trading_date, [])
    )

    response = backfill_handler.handler({"apply": False}, None)
    payload = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert payload["apply"] is False
    assert payload["trading_date"] == "2026-08-20"
    assert payload["catalog_symbol_count"] == 2
    assert payload["catalog_record_count"] == 2
    assert payload["to_timestamp"] == "2026-08-20T15:00:00-05:00"
    assert payload["records"][0]["symbol"] == "ISA"
    assert payload["records"][1]["previous_snapshot_key"]["captured_at"] == "2026-08-20T14:55:00-05:00"
    assert catalog_table.written_items == []


def test_backfill_apply_overwrites_catalog_globally() -> None:
    snapshots_by_date = {
        "2026-08-20": [
            {"symbol": "NUCO", "captured_at": "2026-08-20T14:55:00-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-20T15:00:00-05:00"},
            {"symbol": "ISA", "captured_at": "2026-08-20T14:58:00-05:00"},
            {"symbol": "CIB", "captured_at": "2026-08-20T14:57:00-05:00"},
        ]
    }
    backfill_handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable(snapshots_by_date)
    catalog_table = FakeAnalyticsCatalogTable(existing_item={"pk": "analytics_catalog", "catalog_version": 7})
    backfill_handler.ANALYTICS_CATALOG_TABLE = catalog_table
    backfill_handler._load_snapshots_for_trading_date = lambda trading_date: list(
        snapshots_by_date.get(trading_date, [])
    )

    response = backfill_handler.handler(
        {
            "apply": True,
            "trading_date": "2026-08-20",
        },
        None,
    )
    payload = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert payload["updated"] is True
    assert payload["catalog_symbol_count"] == 3
    assert payload["records"] == [
        {
            "symbol": "CIB",
            "current_snapshot_key": {
                "symbol": "CIB",
                "captured_at": "2026-08-20T14:57:00-05:00",
            },
            "previous_snapshot_key": None,
        },
        {
            "symbol": "ISA",
            "current_snapshot_key": {
                "symbol": "ISA",
                "captured_at": "2026-08-20T14:58:00-05:00",
            },
            "previous_snapshot_key": None,
        },
        {
            "symbol": "NUCO",
            "current_snapshot_key": {
                "symbol": "NUCO",
                "captured_at": "2026-08-20T15:00:00-05:00",
            },
            "previous_snapshot_key": {
                "symbol": "NUCO",
                "captured_at": "2026-08-20T14:55:00-05:00",
            },
        },
    ]
    assert len(catalog_table.written_items) == 1
    assert catalog_table.written_items[0]["catalog_version"] == 8
