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
