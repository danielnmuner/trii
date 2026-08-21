from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

from botocore.exceptions import ClientError


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_FILE = (
    ROOT_DIR
    / "infra"
    / "prod"
    / "services"
    / "lambda"
    / "analytics-catalog-updater"
    / "src"
    / "handler.py"
)

os.environ.setdefault("ANALYTICS_CATALOG_TABLE", "test-analytics-catalog")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

spec = importlib.util.spec_from_file_location("analytics_catalog_updater_handler", LAMBDA_FILE)
assert spec is not None and spec.loader is not None
catalog_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_handler)


class FakeAnalyticsCatalogTable:
    def __init__(self) -> None:
        self.item: dict | None = None

    def get_item(self, *, Key: dict) -> dict:
        assert Key == {"pk": "analytics_catalog"}
        if self.item is None:
            return {}
        return {"Item": dict(self.item)}

    def put_item(
        self,
        *,
        Item: dict,
        ConditionExpression: str,
        ExpressionAttributeValues: dict | None = None,
    ) -> dict:
        if ConditionExpression == "attribute_not_exists(pk)":
            if self.item is not None:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                    "PutItem",
                )
        elif ConditionExpression == "catalog_version = :expected_version":
            expected_version = ExpressionAttributeValues[":expected_version"]
            current_version = None if self.item is None else self.item.get("catalog_version")
            if current_version != expected_version:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "version mismatch"}},
                    "PutItem",
                )
        else:
            raise AssertionError(f"Unexpected condition: {ConditionExpression}")

        self.item = dict(Item)
        return {}


def _stream_insert(symbol: str, captured_at: str) -> dict:
    return {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                "symbol": {"S": symbol},
                "captured_at": {"S": captured_at},
                "captured_date": {"S": captured_at[:10]},
            }
        },
    }


def test_handler_builds_catalog_for_latest_trading_date_only() -> None:
    table = FakeAnalyticsCatalogTable()
    catalog_handler.ANALYTICS_CATALOG_TABLE = table

    response = catalog_handler.handler(
        {
            "Records": [
                _stream_insert("NUCO", "2026-08-20T14:55:00-05:00"),
                _stream_insert("ISA", "2026-08-20T14:58:00-05:00"),
                _stream_insert("NUCO", "2026-08-20T15:00:00-05:00"),
            ]
        },
        None,
    )

    payload = json.loads(response["body"])
    assert payload["updated"] is True
    assert payload["processed_records"] == 3
    assert table.item is not None
    assert table.item["trading_date"] == "2026-08-20"
    assert table.item["to_timestamp"] == "2026-08-20T15:00:00-05:00"
    assert table.item["symbol_count"] == 2
    assert table.item["record_count"] == 2
    assert table.item["symbols"] == ["ISA", "NUCO"]
    assert table.item["records"][1]["current_snapshot_key"]["captured_at"] == "2026-08-20T15:00:00-05:00"
    assert table.item["records"][1]["previous_snapshot_key"]["captured_at"] == "2026-08-20T14:55:00-05:00"


def test_handler_replaces_catalog_when_newer_trading_date_arrives() -> None:
    table = FakeAnalyticsCatalogTable()
    table.item = {
        "pk": "analytics_catalog",
        "record_type": "analytics_catalog",
        "trading_date": "2026-08-20",
        "to_timestamp": "2026-08-20T15:00:00-05:00",
        "symbol_count": 2,
        "record_count": 2,
        "symbols": ["ISA", "NUCO"],
        "records": [
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
        ],
        "catalog_version": 4,
        "updated_at": "2026-08-20T15:00:10-05:00",
    }
    catalog_handler.ANALYTICS_CATALOG_TABLE = table

    response = catalog_handler.handler(
        {
            "Records": [
                _stream_insert("CIB", "2026-08-21T09:01:00-05:00"),
            ]
        },
        None,
    )

    payload = json.loads(response["body"])
    assert payload["updated"] is True
    assert table.item is not None
    assert table.item["trading_date"] == "2026-08-21"
    assert table.item["symbols"] == ["CIB"]
    assert table.item["record_count"] == 1
    assert table.item["catalog_version"] == 5
    assert table.item["records"][0]["previous_snapshot_key"] is None
