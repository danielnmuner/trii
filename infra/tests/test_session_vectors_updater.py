from __future__ import annotations

import importlib.util
import json
import os
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_FILE = (
    ROOT_DIR
    / "infra"
    / "prod"
    / "services"
    / "lambda"
    / "session-vectors-updater"
    / "src"
    / "handler.py"
)

os.environ.setdefault("SESSION_VECTORS_TABLE", "test-session-vectors")
os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("ANALYTICS_CATALOG_TABLE", "test-analytics-catalog")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

spec = importlib.util.spec_from_file_location("session_vectors_updater_handler", LAMBDA_FILE)
assert spec is not None and spec.loader is not None
session_vectors_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session_vectors_handler)


class FakeSessionVectorsTable:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict] = {}
        self.batch_writer_put_count = 0

    def get_item(self, *, Key: dict) -> dict:
        item = self.items.get((Key["symbol"], Key["record_type"]))
        return {} if item is None else {"Item": dict(item)}

    def put_item(self, *, Item: dict) -> dict:
        self.items[(Item["symbol"], Item["record_type"])] = dict(Item)
        return {}

    def batch_writer(self) -> "FakeSessionVectorsBatchWriter":
        return FakeSessionVectorsBatchWriter(self)


class FakeSessionVectorsBatchWriter:
    def __init__(self, table: FakeSessionVectorsTable) -> None:
        self.table = table

    def __enter__(self) -> "FakeSessionVectorsBatchWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def put_item(self, *, Item: dict) -> dict:
        self.table.batch_writer_put_count += 1
        return self.table.put_item(Item=Item)


class FakeAnalyticsCatalogTable:
    def __init__(self, item: dict | None) -> None:
        self.item = item

    def get_item(self, *, Key: dict) -> dict:
        assert Key == {"pk": "analytics_catalog"}
        return {} if self.item is None else {"Item": dict(self.item)}


class FakeCurrentSnapshotsTable:
    def __init__(self, items: list[dict]) -> None:
        self.items = list(items)
        self.query_calls = 0

    def query(self, **kwargs: dict) -> dict:
        self.query_calls += 1
        assert kwargs["IndexName"] == "captured-date-index"
        assert kwargs["ProjectionExpression"] == "#symbol, captured_at, microprice, mid_price, last_price, traded_value, traded_volume"
        assert kwargs["ExpressionAttributeNames"] == {"#symbol": "symbol"}
        return {"Items": list(self.items)}


def test_handler_projects_snapshot_into_manifest_and_segment_items() -> None:
    table = FakeSessionVectorsTable()
    session_vectors_handler.SESSION_VECTORS_TABLE = table

    response = session_vectors_handler.handler(
        {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "symbol": {"S": "nuco"},
                            "captured_at": {"S": "2026-08-30T08:31:00-05:00"},
                            "captured_date": {"S": "2026-08-30"},
                            "microprice": {"N": "2645.5"},
                            "mid_price": {"N": "2646"},
                            "last_price": {"N": "2645"},
                            "traded_value": {"N": "1322000"},
                            "traded_volume": {"N": "500"},
                        }
                    },
                }
            ]
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["mode"] == "stream"
    assert payload["processed_records"] == 1
    assert payload["written_count"] == 1

    manifest = table.items[("NUCO", "session_vector#2026-08-30")]
    segment = table.items[("NUCO", "session_vector#2026-08-30#segment#000")]

    assert manifest["latest_sample_index"] == 2
    assert manifest["latest_captured_at"] == "2026-08-30T08:31:00-05:00"
    assert manifest["segment_count"] == 1
    assert manifest["samples_per_segment"] == 156

    assert segment["segment_index"] == 0
    assert segment["from_sample_index"] == 2
    assert segment["to_sample_index"] == 2
    assert segment["microprice_series"] == [None, None, Decimal("2645.5")]
    assert segment["mid_price_series"] == [None, None, Decimal("2646")]
    assert segment["last_price_series"] == [None, None, Decimal("2645")]
    assert segment["vwap_series"] == [None, None, Decimal("2644")]
    expected_expiry = int(datetime.fromisoformat("2026-08-30T08:31:00-05:00").astimezone(ZoneInfo("America/Bogota")).timestamp()) + (24 * 60 * 60)
    assert manifest["expires_at"] == expected_expiry
    assert segment["expires_at"] == expected_expiry


def test_handler_manual_run_rebuilds_latest_catalog_day_for_all_symbols() -> None:
    table = FakeSessionVectorsTable()
    current_snapshots = FakeCurrentSnapshotsTable(
        [
            {
                "symbol": "ECOPETROL",
                "captured_at": "2026-08-30T08:30:30-05:00",
                "captured_date": "2026-08-30",
                "microprice": Decimal("2640"),
                "mid_price": Decimal("2641"),
                "last_price": Decimal("2639"),
                "traded_value": Decimal("2641000"),
                "traded_volume": Decimal("1000"),
            },
            {
                "symbol": "NUCO",
                "captured_at": "2026-08-30T08:30:00-05:00",
                "captured_date": "2026-08-30",
                "microprice": Decimal("100"),
                "mid_price": Decimal("101"),
                "last_price": Decimal("99"),
                "traded_value": Decimal("101000"),
                "traded_volume": Decimal("1000"),
            },
            {
                "symbol": "NUCO",
                "captured_at": "2026-08-30T08:30:30-05:00",
                "captured_date": "2026-08-30",
                "microprice": Decimal("102"),
                "mid_price": Decimal("103"),
                "last_price": Decimal("101"),
                "traded_value": Decimal("206000"),
                "traded_volume": Decimal("2000"),
            },
        ]
    )
    catalog = FakeAnalyticsCatalogTable({"pk": "analytics_catalog", "trading_date": "2026-08-30"})
    session_vectors_handler.SESSION_VECTORS_TABLE = table
    session_vectors_handler.CURRENT_SNAPSHOTS_TABLE = current_snapshots
    session_vectors_handler.ANALYTICS_CATALOG_TABLE = catalog

    response = session_vectors_handler.handler({}, None)

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload == {
        "mode": "manual",
        "trading_date": "2026-08-30",
        "catalog_found": True,
        "snapshots_read": 3,
        "symbols_processed": 2,
        "written_items": 4,
        "ttl_hours": 72,
    }
    assert current_snapshots.query_calls == 1
    assert table.batch_writer_put_count == 4

    nuco_manifest = table.items[("NUCO", "session_vector#2026-08-30")]
    nuco_segment = table.items[("NUCO", "session_vector#2026-08-30#segment#000")]
    ecopetrol_manifest = table.items[("ECOPETROL", "session_vector#2026-08-30")]
    ecopetrol_segment = table.items[("ECOPETROL", "session_vector#2026-08-30#segment#000")]

    assert nuco_manifest["latest_sample_index"] == 1
    assert nuco_manifest["segment_count"] == 1
    assert nuco_segment["microprice_series"] == [Decimal("100"), Decimal("102")]
    assert nuco_segment["mid_price_series"] == [Decimal("101"), Decimal("103")]
    assert nuco_segment["last_price_series"] == [Decimal("99"), Decimal("101")]
    assert nuco_segment["vwap_series"] == [Decimal("101"), Decimal("103")]
    nuco_expected_expiry = int(datetime.fromisoformat("2026-08-30T08:30:30-05:00").astimezone(ZoneInfo("America/Bogota")).timestamp()) + (72 * 60 * 60)
    assert nuco_manifest["expires_at"] == nuco_expected_expiry
    assert nuco_segment["expires_at"] == nuco_expected_expiry

    assert ecopetrol_manifest["latest_sample_index"] == 1
    assert ecopetrol_segment["microprice_series"] == [None, Decimal("2640")]
    assert ecopetrol_segment["mid_price_series"] == [None, Decimal("2641")]
    assert ecopetrol_segment["last_price_series"] == [None, Decimal("2639")]
    assert ecopetrol_segment["vwap_series"] == [None, Decimal("2641")]
    assert ecopetrol_manifest["expires_at"] == nuco_expected_expiry


def test_handler_manual_run_returns_empty_summary_when_catalog_has_no_trading_day() -> None:
    table = FakeSessionVectorsTable()
    current_snapshots = FakeCurrentSnapshotsTable([])
    catalog = FakeAnalyticsCatalogTable(None)
    session_vectors_handler.SESSION_VECTORS_TABLE = table
    session_vectors_handler.CURRENT_SNAPSHOTS_TABLE = current_snapshots
    session_vectors_handler.ANALYTICS_CATALOG_TABLE = catalog

    response = session_vectors_handler.handler({}, None)

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload == {
        "mode": "manual",
        "trading_date": None,
        "catalog_found": False,
        "snapshots_read": 0,
        "symbols_processed": 0,
        "written_items": 0,
    }
    assert current_snapshots.query_calls == 0
    assert table.items == {}
