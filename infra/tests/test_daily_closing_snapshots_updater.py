from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path

from botocore.exceptions import ClientError


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_FILE = (
    ROOT_DIR
    / "infra"
    / "prod"
    / "services"
    / "lambda"
    / "daily-closing-snapshots-updater"
    / "src"
    / "handler.py"
)

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("DAILY_CLOSING_SNAPSHOTS_TABLE", "test-daily-closing-snapshots")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

spec = importlib.util.spec_from_file_location("daily_closing_snapshots_handler", LAMBDA_FILE)
assert spec is not None and spec.loader is not None
daily_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily_handler)


class FakeCurrentSnapshotsTable:
    def __init__(self, snapshots_by_date: dict[str, list[dict]]) -> None:
        self.snapshots_by_date = snapshots_by_date

    def query(self, **query_kwargs):
        expression = str(query_kwargs["KeyConditionExpression"])
        trading_date = expression.split(" = ")[-1].strip()
        trading_date = trading_date.replace("'", "")
        return {"Items": list(self.snapshots_by_date.get(trading_date, []))}

    def scan(self, **_scan_kwargs):
        items = []
        for trading_date in sorted(self.snapshots_by_date):
            items.extend({"captured_date": trading_date} for _ in self.snapshots_by_date[trading_date])
        return {"Items": items}


class FakeDailyClosingSnapshotsTable:
    def __init__(self, existing_items: list[dict]) -> None:
        self.existing_items = list(existing_items)
        self.written_items: list[dict] = []

    def scan(self, **_scan_kwargs):
        return {"Items": list(self.existing_items)}

    def put_item(self, *, Item, ConditionExpression: str):
        assert ConditionExpression == "attribute_not_exists(symbol) AND attribute_not_exists(trading_date)"
        already_exists = any(
            existing["symbol"] == Item["symbol"] and existing["trading_date"] == Item["trading_date"]
            for existing in [*self.existing_items, *self.written_items]
        )
        if already_exists:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.written_items.append(Item)
        return {}


def test_select_latest_snapshot_per_symbol_prefers_last_captured_at() -> None:
    latest = daily_handler._select_latest_snapshot_per_symbol(
        [
            {"symbol": "NUCO", "captured_at": "2026-08-10T14:30:00-05:00"},
            {"symbol": "NUCO", "captured_at": "2026-08-10T14:45:00-05:00"},
            {"symbol": "ISA", "captured_at": "2026-08-10T14:10:00-05:00"},
        ]
    )

    assert latest["NUCO"]["captured_at"] == "2026-08-10T14:45:00-05:00"
    assert latest["ISA"]["captured_at"] == "2026-08-10T14:10:00-05:00"


def test_handler_writes_only_missing_symbol_day_records() -> None:
    snapshots_by_date = {
        "2026-08-10": [
            {
                "symbol": "NUCO",
                "asset_name": "Nu Holdings",
                "currency": "COP",
                "captured_at": "2026-08-10T14:30:00-05:00",
                "snapshot_checksum": "nuco-early",
                "last_price": 100,
                "daily_change_amount": 1,
                "daily_change_percent": 2,
                "previous_close": 99,
                "best_bid_price": 99,
                "best_ask_price": 101,
                "high_price": 102,
                "low_price": 98,
                "traded_value": 1000,
                "traded_volume": 10,
            },
            {
                "symbol": "NUCO",
                "asset_name": "Nu Holdings",
                "currency": "COP",
                "captured_at": "2026-08-10T14:45:00-05:00",
                "snapshot_checksum": "nuco-close",
                "last_price": 110,
                "daily_change_amount": 11,
                "daily_change_percent": 12,
                "previous_close": 99,
                "best_bid_price": 109,
                "best_ask_price": 111,
                "high_price": 112,
                "low_price": 98,
                "traded_value": 1500,
                "traded_volume": 15,
            },
            {
                "symbol": "ISA",
                "asset_name": "ISA",
                "currency": "COP",
                "captured_at": "2026-08-10T14:40:00-05:00",
                "snapshot_checksum": "isa-close",
                "last_price": 210,
                "daily_change_amount": 5,
                "daily_change_percent": 3,
                "previous_close": 205,
                "best_bid_price": 209,
                "best_ask_price": 211,
                "high_price": 212,
                "low_price": 204,
                "traded_value": 2000,
                "traded_volume": 20,
            },
        ],
        "2026-08-11": [
            {
                "symbol": "NUCO",
                "asset_name": "Nu Holdings",
                "currency": "COP",
                "captured_at": "2026-08-11T14:50:00-05:00",
                "snapshot_checksum": "nuco-next-close",
                "last_price": 120,
                "daily_change_amount": 10,
                "daily_change_percent": 4,
                "previous_close": 110,
                "best_bid_price": 119,
                "best_ask_price": 121,
                "high_price": 122,
                "low_price": 109,
                "traded_value": 3000,
                "traded_volume": 30,
            }
        ],
    }
    closing_table = FakeDailyClosingSnapshotsTable(
        [
            {
                "symbol": "ISA",
                "trading_date": "2026-08-10",
            }
        ]
    )

    daily_handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable(snapshots_by_date)
    daily_handler.DAILY_CLOSING_SNAPSHOTS_TABLE = closing_table
    daily_handler._now_bogota = lambda: datetime.fromisoformat("2026-08-11T16:00:00-05:00")
    daily_handler._load_snapshots_for_trading_date = lambda trading_date: list(snapshots_by_date.get(trading_date, []))

    response = daily_handler.handler(
        {
            "apply": True,
            "trading_date_from": "2026-08-10",
            "trading_date_to": "2026-08-11",
        },
        None,
    )
    body = json.loads(response["body"])

    assert body["dates_considered"] == 2
    assert body["dates_with_snapshots"] == 2
    assert body["missing_symbols_found"] == 2
    assert body["records_written"] == 2
    assert body["records_skipped_existing"] == 1
    assert {(item["symbol"], item["trading_date"]) for item in closing_table.written_items} == {
        ("NUCO", "2026-08-10"),
        ("NUCO", "2026-08-11"),
    }
    assert next(item for item in closing_table.written_items if item["trading_date"] == "2026-08-10")["source_captured_at"] == "2026-08-10T14:45:00-05:00"


def test_handler_preview_mode_finds_missing_records_without_writing() -> None:
    snapshots_by_date = {
        "2026-08-10": [
            {
                "symbol": "NUCO",
                "asset_name": "Nu Holdings",
                "currency": "COP",
                "captured_at": "2026-08-10T14:45:00-05:00",
                "snapshot_checksum": "nuco-close",
                "last_price": 110,
                "daily_change_amount": 11,
                "daily_change_percent": 12,
                "previous_close": 99,
                "best_bid_price": 109,
                "best_ask_price": 111,
                "high_price": 112,
                "low_price": 98,
                "traded_value": 1500,
                "traded_volume": 15,
            }
        ]
    }
    daily_handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable(snapshots_by_date)
    closing_table = FakeDailyClosingSnapshotsTable([])
    daily_handler.DAILY_CLOSING_SNAPSHOTS_TABLE = closing_table
    daily_handler._now_bogota = lambda: datetime.fromisoformat("2026-08-10T16:00:00-05:00")
    daily_handler._load_snapshots_for_trading_date = lambda trading_date: list(snapshots_by_date.get(trading_date, []))

    response = daily_handler.handler(
        {
            "apply": False,
            "trading_date_from": "2026-08-10",
            "trading_date_to": "2026-08-10",
        },
        None,
    )
    body = json.loads(response["body"])

    assert body["missing_symbols_found"] == 1
    assert body["records_written"] == 0
    assert closing_table.written_items == []
