from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LAMBDA_SRC = ROOT_DIR / "infra" / "prod" / "services" / "lambda" / "api-handler" / "src"
if str(LAMBDA_SRC) not in sys.path:
    sys.path.insert(0, str(LAMBDA_SRC))

os.environ.setdefault("CURRENT_SNAPSHOTS_TABLE", "test-current-snapshots")
os.environ.setdefault("SNAPSHOT_INGESTION_RAW_TABLE", "test-snapshot-raw")
os.environ.setdefault("SNAPSHOT_INGESTION_CHECKSUMS_TABLE", "test-snapshot-checksums")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("DAILY_CLOSING_SNAPSHOTS_TABLE", "test-daily-closing")
os.environ.setdefault("ZSCORE_OPPORTUNITIES_TABLE", "test-zscore-opportunities")
os.environ.setdefault("MARKET_AI_RECOMMENDATIONS_TABLE", "test-market-ai")
os.environ.setdefault("STOCK_ORDERS_TABLE", "test-stock-orders")
os.environ.setdefault("PARSED_INVOICES_TABLE", "test-parsed-invoices")
os.environ.setdefault("SOURCE_DOCUMENTS_BUCKET", "test-source-documents")
os.environ.setdefault("API_SHARED_TOKEN", "test-token")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

handler = importlib.import_module("handler")


class FakeZscoreOpportunitiesTable:
    def get_item(self, *, Key: dict) -> dict:
        if Key["snapshot_checksum"] != "checksum-1":
            return {}
        return {
            "Item": {
                "snapshot_checksum": "checksum-1",
                "symbol": "NUCO",
                "captured_at": "2026-08-21T10:56:08-05:00",
                "trading_date": "2026-08-21",
                "triggered_z_scores": {
                    "spread_bps": {"sample_value": 4.3, "z_score": -1.79},
                    "obi_l1": {"sample_value": 0.11, "z_score": 0.22},
                },
            }
        }

    def query(self, **kwargs) -> dict:
        if kwargs.get("IndexName") == "trading-date-index":
            return {
                "Items": [
                    {
                        "snapshot_checksum": "checksum-2",
                        "symbol": "ISA",
                        "captured_at": "2026-08-21T11:10:00-05:00",
                        "trading_date": "2026-08-21",
                    },
                    {
                        "snapshot_checksum": "checksum-1",
                        "symbol": "NUCO",
                        "captured_at": "2026-08-21T10:56:08-05:00",
                        "trading_date": "2026-08-21",
                    },
                ]
            }
        return {"Items": []}


class FakeDailyClosingSnapshotsTable:
    def get_item(self, *, Key: dict) -> dict:
        if Key != {"symbol": "NUCO", "trading_date": "2026-08-20"}:
            return {}
        return {
            "Item": {
                "symbol": "NUCO",
                "trading_date": "2026-08-20",
                "record_type": "daily_closing_snapshot",
                "last_price": 44000,
            }
        }

    def query(self, **kwargs) -> dict:
        return {"Items": []}


class FakeCurrentSnapshotsTable:
    def get_item(self, *, Key: dict) -> dict:
        return {}

    def query(self, **kwargs) -> dict:
        if kwargs.get("IndexName") == "captured-date-index":
            return {
                "Items": [
                    {
                        "symbol": "NUCO",
                        "captured_at": "2026-08-21T11:10:00-05:00",
                    },
                    {
                        "symbol": "ISA",
                        "captured_at": "2026-08-21T11:09:00-05:00",
                    },
                ]
            }
        return {
            "Items": [
                {
                    "symbol": "NUCO",
                    "captured_at": "2026-08-21T11:10:00-05:00",
                    "last_price": 44000,
                    "previous_close": 43000,
                    "traded_value": 1000000,
                    "traded_volume": 100,
                },
                {
                    "symbol": "NUCO",
                    "captured_at": "2026-08-21T11:05:00-05:00",
                    "last_price": 43900,
                    "previous_close": 43000,
                    "traded_value": 990000,
                    "traded_volume": 99,
                },
            ]
        }


class FakeHistoricStatsTable:
    def query(self, **kwargs) -> dict:
        return {
            "Items": [
                {
                    "pk": "NUCO",
                    "metric": "spread_bps",
                    "latest_value": 4.3,
                    "mean": 4.1,
                    "stddev": 0.2,
                    "sample_count": 24,
                }
            ]
        }


class FailingMarketAiRecommendationsTable:
    def query(self, **kwargs) -> dict:
        raise AssertionError("market_ai_recommendations should not be queried by analytics/snapshot")


class FakeCurrentSnapshotsCatalogTable:
    def __init__(self) -> None:
        self.catalog_probe_calls = 0

    def query(self, **kwargs) -> dict:
        if kwargs.get("IndexName") != "captured-date-index":
            return {"Items": []}

        limit = kwargs.get("Limit")
        if limit == 1:
            self.catalog_probe_calls += 1
            if self.catalog_probe_calls == 1:
                return {"Items": []}
            return {"Items": [{"symbol": "NUCO", "captured_at": "2026-08-20T15:00:00-05:00"}]}

        return {
            "Items": [
                {"symbol": "ISA", "captured_at": "2026-08-20T14:58:00-05:00"},
                {"symbol": "NUCO", "captured_at": "2026-08-20T15:00:00-05:00"},
                {"symbol": "NUCO", "captured_at": "2026-08-20T14:55:00-05:00"},
            ]
        }


def test_handler_returns_zscore_opportunities_for_trading_date() -> None:
    handler.ZSCORE_OPPORTUNITIES_TABLE = FakeZscoreOpportunitiesTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/zscore-opportunities",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"trading_date": "2026-08-21", "limit": "2"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["trading_date"] == "2026-08-21"
    assert payload["result"]["record_count"] == 2
    assert payload["result"]["records"][0]["symbol"] == "ISA"


def test_handler_returns_daily_closing_record_for_exact_symbol_and_date() -> None:
    handler.DAILY_CLOSING_SNAPSHOTS_TABLE = FakeDailyClosingSnapshotsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/daily-closing",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "trading_date": "2026-08-20"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["trading_date"] == "2026-08-20"
    assert payload["result"]["record_count"] == 1
    assert payload["result"]["records"][0]["last_price"] == 44000


def test_handler_snapshot_uses_only_current_snapshots_and_historic_stats() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    handler.HISTORIC_STATS_TABLE = FakeHistoricStatsTable()
    handler.MARKET_AI_RECOMMENDATIONS_TABLE = FailingMarketAiRecommendationsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/snapshot",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["record_count"] == 2
    assert "market_ai_recommendation" not in payload["result"]


def test_handler_catalog_uses_latest_available_snapshot_date() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsCatalogTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/catalog",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["trading_date"] == "2026-08-20"
    assert payload["result"]["symbol_count"] == 2
    assert payload["result"]["symbols"] == ["ISA", "NUCO"]
    assert payload["result"]["record_count"] == 3
