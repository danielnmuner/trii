from __future__ import annotations

import base64
import importlib
import os
import sys
from pathlib import Path

from botocore.exceptions import ClientError


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_SRC = ROOT_DIR / "infra" / "prod" / "services" / "lambda" / "api-handler" / "src"
if str(LAMBDA_SRC) not in sys.path:
    sys.path.insert(0, str(LAMBDA_SRC))

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("SNAPSHOT_INGESTION_RAW_TABLE", "test-snapshot-raw")
os.environ.setdefault("SNAPSHOT_INGESTION_CHECKSUMS_TABLE", "test-snapshot-checksums")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("MARKET_AI_RECOMMENDATIONS_TABLE", "test-market-ai")
os.environ.setdefault("STOCK_ORDERS_TABLE", "test-stock-orders")
os.environ.setdefault("PARSED_INVOICES_TABLE", "test-parsed-invoices")
os.environ.setdefault("SOURCE_DOCUMENTS_BUCKET", "test-source-documents")
os.environ.setdefault("API_SHARED_TOKEN", "test-token")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

handler = importlib.import_module("handler")


class FakeStockOrdersTable:
    def __init__(self) -> None:
        self.record_checksums: set[str] = set()

    def put_item(self, *, Item, ConditionExpression: str) -> dict:
        assert ConditionExpression == "attribute_not_exists(record_checksum)"
        checksum = str(Item["record_checksum"])
        if checksum in self.record_checksums:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.record_checksums.add(checksum)
        return {}


def _build_orders_payload() -> dict[str, str]:
    raw_bytes = (ROOT_DIR / "orders-trii.csv").read_bytes()
    return {
        "file_name": "orders-trii.csv",
        "file_content_base64": base64.b64encode(raw_bytes).decode("utf-8"),
    }


def _build_normalized_orders_payload() -> dict[str, object]:
    raw_bytes = (ROOT_DIR / "orders-trii.csv").read_bytes()
    records = handler._normalize_order_records(raw_bytes)
    return {
        "file_name": "orders-trii.csv",
        "source_file_checksum": records[0]["source_file_checksum"],
        "records": [
            {
                key: value
                for key, value in record.items()
                if key != "record_checksum"
            }
            for record in records
        ],
    }


def test_persist_orders_imports_all_new_records() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table

    result = handler._persist_orders(_build_orders_payload())

    assert result["received_records"] > 0
    assert result["imported_records"] == result["received_records"]
    assert result["duplicate_records"] == 0
    assert len(fake_table.record_checksums) == result["received_records"]
    assert result["source_file_checksum"]


def test_persist_orders_skips_duplicate_records_from_same_csv_replay() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table
    payload = _build_orders_payload()

    first_result = handler._persist_orders(payload)
    second_result = handler._persist_orders(payload)

    assert first_result["imported_records"] == first_result["received_records"]
    assert second_result["received_records"] == first_result["received_records"]
    assert second_result["imported_records"] == 0
    assert second_result["duplicate_records"] == second_result["received_records"]


def test_persist_orders_accepts_mixed_batch_with_new_and_existing_records() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table
    payload = _build_orders_payload()
    raw_bytes = base64.b64decode(payload["file_content_base64"])
    records = handler._normalize_order_records(raw_bytes)
    fake_table.record_checksums.add(records[0]["record_checksum"])

    result = handler._persist_orders(payload)

    assert result["received_records"] == len(records)
    assert result["duplicate_records"] == 1
    assert result["imported_records"] == len(records) - 1


def test_persist_orders_accepts_normalized_records_payload() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table

    result = handler._persist_orders(_build_normalized_orders_payload())

    assert result["received_records"] > 0
    assert result["imported_records"] == result["received_records"]
    assert result["duplicate_records"] == 0
