from __future__ import annotations

import importlib.util
import json
import os
from decimal import Decimal
from pathlib import Path


LAMBDA_SRC = (
    Path(__file__).resolve().parents[1]
    / "prod"
    / "services"
    / "lambda"
    / "zscore-opportunities-sampler"
    / "src"
)

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("STOCK_ORDERS_TABLE", "test-stock-orders")
os.environ.setdefault("ZSCORE_OPPORTUNITIES_TABLE", "test-zscore-opportunities")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

_handler_spec = importlib.util.spec_from_file_location(
    "zscore_opportunities_sampler_handler",
    LAMBDA_SRC / "handler.py",
)
assert _handler_spec is not None and _handler_spec.loader is not None
sampler = importlib.util.module_from_spec(_handler_spec)
_handler_spec.loader.exec_module(sampler)


class FakeCurrentSnapshotsTable:
    def scan(self, **kwargs) -> dict:
        assert kwargs["ProjectionExpression"] == "captured_date"
        return {
            "Items": [
                {"captured_date": "2026-08-20"},
                {"captured_date": "2026-08-21"},
                {"captured_date": "2026-08-21"},
            ]
        }

    def query(self, **kwargs) -> dict:
        if kwargs.get("Limit") == 1:
            return {"Items": [{"symbol": "NUCO", "captured_at": "2026-08-21T11:10:00-05:00"}]}
        assert kwargs["IndexName"] == "captured-date-index"
        trading_date = str(kwargs["KeyConditionExpression"]._values[1])
        if trading_date == "2026-08-20":
            return {
                "Items": [
                    {
                        "symbol": "NUCO",
                        "captured_at": "2026-08-20T09:00:00-05:00",
                        "captured_date": "2026-08-20",
                        "snapshot_checksum": "checksum-200900",
                        "last_price": 43800,
                        "daily_change_amount": 90,
                        "daily_change_percent": 0.20,
                        "previous_close": 43710,
                        "high_price": 43900,
                        "low_price": 43650,
                        "bid_levels": [{"price": 43790, "quantity": 100}],
                        "ask_levels": [{"price": 43810, "quantity": 95}],
                    },
                    {
                        "symbol": "NUCO",
                        "captured_at": "2026-08-20T09:07:00-05:00",
                        "captured_date": "2026-08-20",
                        "snapshot_checksum": "checksum-200907",
                        "last_price": 43820,
                        "daily_change_amount": 92,
                        "daily_change_percent": 0.21,
                        "previous_close": 43728,
                        "high_price": 43910,
                        "low_price": 43650,
                        "bid_levels": [{"price": 43810, "quantity": 120}],
                        "ask_levels": [{"price": 43830, "quantity": 96}],
                    },
                    {
                        "symbol": "NUCO",
                        "captured_at": "2026-08-20T09:12:00-05:00",
                        "captured_date": "2026-08-20",
                        "snapshot_checksum": "checksum-200912",
                        "last_price": 43840,
                        "daily_change_amount": 95,
                        "daily_change_percent": 0.22,
                        "previous_close": 43745,
                        "high_price": 43920,
                        "low_price": 43660,
                        "bid_levels": [{"price": 43830, "quantity": 130}],
                        "ask_levels": [{"price": 43850, "quantity": 98}],
                    },
                ]
            }
        return {
            "Items": [
                {
                    "symbol": "NUCO",
                    "captured_at": "2026-08-21T11:00:00-05:00",
                    "captured_date": "2026-08-21",
                    "snapshot_checksum": "checksum-old",
                    "last_price": 43900,
                    "daily_change_amount": 100,
                    "daily_change_percent": 0.25,
                    "previous_close": 43800,
                    "high_price": 44000,
                    "low_price": 43750,
                    "bid_levels": [{"price": 43890, "quantity": 100}],
                    "ask_levels": [{"price": 43910, "quantity": 90}],
                },
                {
                    "symbol": "NUCO",
                    "captured_at": "2026-08-21T11:10:00-05:00",
                    "captured_date": "2026-08-21",
                    "snapshot_checksum": "checksum-new",
                    "last_price": 44000,
                    "daily_change_amount": 120,
                    "daily_change_percent": 0.28,
                    "previous_close": 43880,
                    "high_price": 44100,
                    "low_price": 43750,
                    "bid_levels": [{"price": 43990, "quantity": 200}],
                    "ask_levels": [{"price": 44010, "quantity": 180}],
                },
                {
                    "symbol": "ISA",
                    "captured_at": "2026-08-21T11:08:00-05:00",
                    "captured_date": "2026-08-21",
                    "snapshot_checksum": "checksum-isa",
                },
            ]
        }


class FakeStockOrdersTable:
    def query(self, **kwargs) -> dict:
        assert kwargs["IndexName"] == "symbol-created-at-index"
        assert "lte" not in str(kwargs["KeyConditionExpression"]).lower()
        return {
            "Items": [
                {
                    "created_at": "2026-08-20T10:00:00-05:00",
                    "normalized_status": "approved",
                    "order_side": "buy",
                    "filled_quantity": 10,
                    "price_per_share": 43000,
                    "record_checksum": "buy-1",
                    "source_line_number": 4,
                },
                {
                    "created_at": "2026-08-20T10:05:00-05:00",
                    "normalized_status": "approved",
                    "order_side": "sell",
                    "filled_quantity": 3,
                    "price_per_share": 43500,
                    "record_checksum": "sell-1",
                    "source_line_number": 5,
                },
            ]
        }


class FakeZscoreOpportunitiesTable:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def put_item(self, *, Item: dict) -> None:
        self.items.append(Item)


class FakeDynamoDbClient:
    def batch_get_item(self, *, RequestItems: dict) -> dict:
        keys = RequestItems["test-historic-stats"]["Keys"]
        symbol = keys[0]["pk"]["S"]
        if symbol == "ISA":
            return {"Responses": {"test-historic-stats": []}}
        return {
            "Responses": {
                "test-historic-stats": [
                    {
                        "pk": {"S": "NUCO"},
                        "sk": {"S": "spread_bps"},
                        "latest_value": {"N": "50"},
                        "mean": {"N": "45"},
                        "stddev": {"N": "10"},
                        "sample_count": {"N": "12"},
                    },
                    {
                        "pk": {"S": "NUCO"},
                        "sk": {"S": "obi_l1"},
                        "latest_value": {"N": "0.50"},
                        "mean": {"N": "0.10"},
                        "stddev": {"N": "0.20"},
                        "sample_count": {"N": "10"},
                    },
                ]
            }
        }


def test_sampler_scheduled_mode_persists_latest_snapshot_without_threshold_gate() -> None:
    fake_table = FakeZscoreOpportunitiesTable()
    sampler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    sampler.STOCK_ORDERS_TABLE = FakeStockOrdersTable()
    sampler.ZSCORE_OPPORTUNITIES_TABLE = fake_table
    sampler.DYNAMODB_CLIENT = FakeDynamoDbClient()
    sampler._find_latest_trading_date = lambda: "2026-08-21"

    response = sampler.handler({"source": "aws.events"}, None)

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["invocation_mode"] == "schedule"
    assert payload["trading_date"] == "2026-08-21"
    assert payload["snapshots_read"] == 3
    assert payload["symbols_sampled"] == 1
    assert payload["records_written"] == 1
    assert payload["skipped_symbols"] == ["ISA"]
    assert payload["records"][0]["snapshot_checksum"] == "checksum-new"
    assert payload["records"][0]["zscore_metric_count"] == 2
    assert len(fake_table.items) == 1
    assert fake_table.items[0]["snapshot_checksum"] == "checksum-new"
    assert fake_table.items[0]["triggered_z_scores"]["spread_bps"]["z_score"] == Decimal("0.5")
    assert fake_table.items[0]["approved_position_summary"]["available_quantity"] == Decimal("7")


def test_sampler_manual_mode_supports_dry_run_for_backfill() -> None:
    fake_table = FakeZscoreOpportunitiesTable()
    sampler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    sampler.STOCK_ORDERS_TABLE = FakeStockOrdersTable()
    sampler.ZSCORE_OPPORTUNITIES_TABLE = fake_table
    sampler.DYNAMODB_CLIENT = FakeDynamoDbClient()

    response = sampler.handler(
        {
            "apply": False,
            "trading_date": "2026-08-21",
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["invocation_mode"] == "manual"
    assert payload["apply"] is False
    assert payload["records_written"] == 0
    assert payload["symbols_sampled"] == 1
    assert len(payload["records"]) == 1
    assert fake_table.items == []


def test_sampler_manual_mode_skips_colombian_holiday() -> None:
    fake_table = FakeZscoreOpportunitiesTable()
    sampler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    sampler.STOCK_ORDERS_TABLE = FakeStockOrdersTable()
    sampler.ZSCORE_OPPORTUNITIES_TABLE = fake_table
    sampler.DYNAMODB_CLIENT = FakeDynamoDbClient()

    response = sampler.handler(
        {
            "apply": True,
            "trading_date": "2026-07-20",
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["timezone"] == "America/Bogota"
    assert payload["records_written"] == 0
    assert payload["updated"] is False
    assert payload["skipped_reason"] == "non_business_day_colombia"
    assert fake_table.items == []


def test_sampler_manual_mode_skips_weekend() -> None:
    fake_table = FakeZscoreOpportunitiesTable()
    sampler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    sampler.STOCK_ORDERS_TABLE = FakeStockOrdersTable()
    sampler.ZSCORE_OPPORTUNITIES_TABLE = fake_table
    sampler.DYNAMODB_CLIENT = FakeDynamoDbClient()

    response = sampler.handler(
        {
            "apply": True,
            "trading_date": "2026-08-22",
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["timezone"] == "America/Bogota"
    assert payload["records_written"] == 0
    assert payload["updated"] is False
    assert payload["skipped_reason"] == "non_business_day_colombia"
    assert fake_table.items == []


def test_sampler_manual_mode_backfills_all_business_days_from_snapshot_min_date() -> None:
    fake_table = FakeZscoreOpportunitiesTable()
    sampler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    sampler.STOCK_ORDERS_TABLE = FakeStockOrdersTable()
    sampler.ZSCORE_OPPORTUNITIES_TABLE = fake_table
    sampler.DYNAMODB_CLIENT = FakeDynamoDbClient()

    response = sampler.handler(
        {
            "apply": False,
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["invocation_mode"] == "manual"
    assert payload["backfill_mode"] is True
    assert payload["trading_date"] is None
    assert payload["trading_date_count"] == 2
    assert payload["trading_date_from"] == "2026-08-20"
    assert payload["trading_date_to"] == "2026-08-21"
    assert payload["snapshots_read"] == 6
    assert payload["symbols_sampled"] == 4
    assert payload["records_written"] == 0
    assert [record["snapshot_checksum"] for record in payload["records"]] == [
        "checksum-200907",
        "checksum-200912",
        "checksum-old",
        "checksum-new",
    ]
    assert fake_table.items == []
