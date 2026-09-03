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
    / "current-snapshots-pruner"
    / "src"
    / "handler.py"
)

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

spec = importlib.util.spec_from_file_location("current_snapshots_pruner_handler", LAMBDA_FILE)
assert spec is not None and spec.loader is not None
pruner_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pruner_handler)


class FakeBatchWriter:
    def __init__(self, table: "FakeCurrentSnapshotsTable") -> None:
        self.table = table

    def __enter__(self) -> "FakeBatchWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def delete_item(self, *, Key: dict[str, str]) -> dict:
        self.table.deleted_keys.append(dict(Key))
        self.table.items = [
            item
            for item in self.table.items
            if not (
                item["symbol"] == Key["symbol"]
                and item["captured_at"] == Key["captured_at"]
            )
        ]
        return {}


class FakeCurrentSnapshotsTable:
    def __init__(self, items: list[dict[str, str]], page_size: int = 100) -> None:
        self.items = list(items)
        self.page_size = page_size
        self.deleted_keys: list[dict[str, str]] = []
        self.query_calls: list[dict] = []

    def query(self, **kwargs: dict) -> dict:
        self.query_calls.append(dict(kwargs))
        symbol = kwargs["KeyConditionExpression"]._values[1]
        symbol_items = sorted(
            [item for item in self.items if item["symbol"] == symbol],
            key=lambda item: item["captured_at"],
            reverse=not kwargs.get("ScanIndexForward", True),
        )

        start_index = 0
        exclusive_start_key = kwargs.get("ExclusiveStartKey")
        if exclusive_start_key is not None:
            for index, item in enumerate(symbol_items):
                if (
                    item["symbol"] == exclusive_start_key["symbol"]
                    and item["captured_at"] == exclusive_start_key["captured_at"]
                ):
                    start_index = index + 1
                    break

        page_items = symbol_items[start_index:start_index + self.page_size]
        response: dict[str, object] = {"Items": page_items}
        if start_index + self.page_size < len(symbol_items):
            last_item = page_items[-1]
            response["LastEvaluatedKey"] = {
                "symbol": last_item["symbol"],
                "captured_at": last_item["captured_at"],
            }
        return response

    def batch_writer(self) -> FakeBatchWriter:
        return FakeBatchWriter(self)


def test_handler_prunes_all_but_latest_two_snapshots_per_symbol() -> None:
    table = FakeCurrentSnapshotsTable(
        [
            {"symbol": "NUCO", "captured_at": "2026-08-30T08:31:30-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-30T08:31:00-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-30T08:30:30-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-30T08:30:00-05:00"},
        ],
        page_size=2,
    )
    pruner_handler.CURRENT_SNAPSHOTS_TABLE = table

    response = pruner_handler.handler(
        {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "symbol": {"S": "nuco"},
                            "captured_at": {"S": "2026-08-30T08:31:30-05:00"},
                        }
                    },
                }
            ]
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload == {
        "processed_symbols": 1,
        "deleted_items": 2,
        "ignored_records": 0,
    }
    assert table.deleted_keys == [
        {"symbol": "NUCO", "captured_at": "2026-08-30T08:30:30-05:00"},
        {"symbol": "NUCO", "captured_at": "2026-08-30T08:30:00-05:00"},
    ]
    assert [item["captured_at"] for item in sorted(table.items, key=lambda item: item["captured_at"], reverse=True)] == [
        "2026-08-30T08:31:30-05:00",
        "2026-08-30T08:31:00-05:00",
    ]
    assert table.query_calls[0]["ConsistentRead"] is True
    assert table.query_calls[0]["ScanIndexForward"] is False


def test_handler_ignores_non_insert_records_and_deduplicates_symbols() -> None:
    table = FakeCurrentSnapshotsTable(
        [
            {"symbol": "ISA", "captured_at": "2026-08-30T08:31:30-05:00"},
            {"symbol": "ISA", "captured_at": "2026-08-30T08:31:00-05:00"},
        ]
    )
    pruner_handler.CURRENT_SNAPSHOTS_TABLE = table

    response = pruner_handler.handler(
        {
            "Records": [
                {
                    "eventName": "REMOVE",
                    "dynamodb": {},
                },
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "symbol": {"S": "isa"},
                            "captured_at": {"S": "2026-08-30T08:31:30-05:00"},
                        }
                    },
                },
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "NewImage": {
                            "symbol": {"S": "ISA"},
                            "captured_at": {"S": "2026-08-30T08:31:00-05:00"},
                        }
                    },
                },
            ]
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload == {
        "processed_symbols": 1,
        "deleted_items": 0,
        "ignored_records": 1,
    }
    assert len(table.query_calls) == 1
