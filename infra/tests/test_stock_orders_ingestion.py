from __future__ import annotations

import base64
import csv
import hashlib
import importlib
import os
import sys
from pathlib import Path
from io import StringIO

from botocore.exceptions import ClientError
import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_SRC = ROOT_DIR / "infra" / "prod" / "services" / "lambda" / "api-handler" / "src"
if str(LAMBDA_SRC) not in sys.path:
    sys.path.insert(0, str(LAMBDA_SRC))

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("DAILY_CLOSING_SNAPSHOTS_TABLE", "test-daily-closing")
os.environ.setdefault("SESSION_VECTORS_TABLE", "test-session-vectors")
os.environ.setdefault("ANALYTICS_CATALOG_TABLE", "test-analytics-catalog")
os.environ.setdefault("STOCK_ORDERS_TABLE", "test-stock-orders")
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


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: list[dict[str, object]] = []

    def put_object(self, **kwargs) -> dict:
        self.objects.append(kwargs)
        return {}


def _build_orders_payload() -> dict[str, str]:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=handler.EXPECTED_STOCK_ORDER_COLUMNS)
    writer.writeheader()
    writer.writerow(
        dict(
            zip(
                handler.EXPECTED_STOCK_ORDER_COLUMNS,
                [
                    "13 ago 2026, 1:59 p. m.",
                    "NUCO",
                    "Venta",
                    "Aprobada",
                    "15/15",
                    "0",
                    "43700",
                    "8303000",
                    "0",
                    "8303000",
                ],
                strict=True,
            )
        )
    )
    writer.writerow(
        dict(
            zip(
                handler.EXPECTED_STOCK_ORDER_COLUMNS,
                [
                    "13 ago 2026, 2:15 p. m.",
                    "CIB",
                    "Compra",
                    "Aprobada",
                    "10/10",
                    "0",
                    "1250",
                    "12500",
                    "0",
                    "12500",
                ],
                strict=True,
            )
        )
    )
    raw_bytes = buffer.getvalue().encode("utf-8")
    return {
        "user_name": "Daniel Muner",
        "file_name": "orders-trii.csv",
        "file_content_base64": base64.b64encode(raw_bytes).decode("utf-8"),
    }


def _build_normalized_orders_payload() -> dict[str, object]:
    raw_bytes = base64.b64decode(_build_orders_payload()["file_content_base64"])
    records = handler._normalize_order_records(raw_bytes, user_name="daniel-muner")
    return {
        "user_name": "Daniel Muner",
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
    first_checksum = next(iter(fake_table.record_checksums))
    stored_record = next(
        record
        for record in handler._normalize_order_records(
            base64.b64decode(_build_orders_payload()["file_content_base64"]),
            user_name="daniel-muner",
        )
        if record["record_checksum"] == first_checksum
    )

    assert result["received_records"] > 0
    assert result["imported_records"] == result["received_records"]
    assert result["duplicate_records"] == 0
    assert len(fake_table.record_checksums) == result["received_records"]
    assert result["source_file_checksum"]
    assert result["user_name"] == "daniel-muner"
    assert stored_record["user_name"] == "daniel-muner"
    assert str(stored_record["imported_at"]).endswith("-05:00")


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
    records = handler._normalize_order_records(raw_bytes, user_name="daniel-muner")
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


def test_persist_orders_uses_user_scope_in_checksum() -> None:
    raw_bytes = base64.b64decode(_build_orders_payload()["file_content_base64"])

    daniel_records = handler._normalize_order_records(raw_bytes, user_name="daniel")
    maria_records = handler._normalize_order_records(raw_bytes, user_name="maria")

    assert daniel_records[0]["record_checksum"] != maria_records[0]["record_checksum"]


def test_persist_orders_rejects_non_approved_csv_records() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table
    payload = _build_orders_payload()
    raw_bytes = base64.b64decode(payload["file_content_base64"]).decode("utf-8")
    payload["file_content_base64"] = base64.b64encode(
        raw_bytes.replace("Aprobada", "Cancelado", 1).encode("utf-8")
    ).decode("utf-8")

    with pytest.raises(ValueError, match="ordenes aprobadas"):
        handler._persist_orders(payload)


def test_persist_orders_rejects_non_approved_normalized_records_payload() -> None:
    fake_table = FakeStockOrdersTable()
    handler.STOCK_ORDERS_TABLE = fake_table
    payload = _build_normalized_orders_payload()
    payload["records"][0]["raw_status"] = "Cancelado"

    with pytest.raises(ValueError, match="ordenes aprobadas"):
        handler._persist_orders(payload)


def test_persist_invoices_prefixes_s3_keys_with_user_name() -> None:
    fake_s3 = FakeS3Client()
    handler.S3_CLIENT = fake_s3
    xml_bytes = b"<xml />"
    expected_checksum = hashlib.sha256(xml_bytes).hexdigest()

    result = handler._persist_invoices(
        {
            "user_name": "Daniel Muner",
            "documents": [
                {
                    "archive_name": "invoice-001.zip",
                    "archive_stem": "invoice-001",
                    "xml_file_name": "invoice.xml",
                    "pdf_file_name": "invoice.pdf",
                    "xml_content_base64": base64.b64encode(xml_bytes).decode("utf-8"),
                    "pdf_content_base64": base64.b64encode(b"%PDF-1.4").decode("utf-8"),
                }
            ],
        }
    )

    assert result["user_name"] == "daniel-muner"
    assert result["documents"][0]["archive_stem"] == "invoice-001"
    assert result["documents"][0]["source_xml_checksum"] == expected_checksum
    assert result["documents"][0]["source_folder_s3_prefix"] == f"invoices/daniel-muner/{expected_checksum}/"
    assert result["documents"][0]["xml_s3_key"] == f"invoices/daniel-muner/{expected_checksum}/invoice.xml"
    assert result["documents"][0]["pdf_s3_key"] == f"invoices/daniel-muner/{expected_checksum}/invoice.pdf"
    assert len(fake_s3.objects) == 2
