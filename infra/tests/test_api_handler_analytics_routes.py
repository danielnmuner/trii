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
os.environ.setdefault("SNAPSHOT_INGESTION_CHECKSUMS_TABLE", "test-snapshot-checksums")
os.environ.setdefault("HISTORIC_STATS_TABLE", "test-historic-stats")
os.environ.setdefault("DAILY_CLOSING_SNAPSHOTS_TABLE", "test-daily-closing")
os.environ.setdefault("SESSION_VECTORS_TABLE", "test-session-vectors")
os.environ.setdefault("ANALYTICS_CATALOG_TABLE", "test-analytics-catalog")
os.environ.setdefault("STOCK_ORDERS_TABLE", "test-stock-orders")
os.environ.setdefault("PARSED_INVOICES_TABLE", "test-parsed-invoices")
os.environ.setdefault("SOURCE_DOCUMENTS_BUCKET", "test-source-documents")
os.environ.setdefault("API_SHARED_TOKEN", "test-token")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

handler = importlib.import_module("handler")


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


class FakeSessionVectorsTable:
    def get_item(self, *, Key: dict) -> dict:
        assert Key["symbol"] == "NUCO"
        if Key["record_type"] == "session_vector#2026-08-21":
            return {
                "Item": {
                    "symbol": "NUCO",
                    "record_type": "session_vector#2026-08-21",
                    "trading_date": "2026-08-21",
                    "timezone": "America/Bogota",
                    "sampling_seconds": 30,
                    "session_start": "2026-08-21T08:30:00-05:00",
                    "session_end": "2026-08-21T15:00:00-05:00",
                    "latest_sample_index": 62,
                    "latest_captured_at": "2026-08-21T09:01:00-05:00",
                    "segment_count": 1,
                    "samples_per_segment": 156,
                }
            }
        return {}

    def query(self, **kwargs) -> dict:
        condition_values = getattr(kwargs["KeyConditionExpression"], "_values", ())
        if len(condition_values) > 1 and condition_values[1].__class__.__name__ == "Between":
            return {
                "Items": [
                    {
                        "symbol": "NUCO",
                        "record_type": "session_vector#2026-08-21#segment#001",
                        "trading_date": "2026-08-21",
                        "timezone": "America/Bogota",
                        "segment_index": 1,
                        "from_sample_index": 156,
                        "to_sample_index": 160,
                        "from_captured_at": "2026-08-21T09:48:00-05:00",
                        "to_captured_at": "2026-08-21T09:50:00-05:00",
                        "microprice_series": [2648.1, 2648.2],
                        "mid_price_series": [2648.0, 2648.1],
                        "last_price_series": [2647.8, 2648.0],
                        "vwap_series": [2646.2, 2646.3],
                    },
                ]
            }
        return {
            "Items": [
                {
                    "symbol": "NUCO",
                    "record_type": "session_vector#2026-08-21#segment#000",
                    "trading_date": "2026-08-21",
                    "timezone": "America/Bogota",
                    "segment_index": 0,
                    "from_sample_index": 0,
                    "to_sample_index": 62,
                    "from_captured_at": "2026-08-21T08:30:00-05:00",
                    "to_captured_at": "2026-08-21T09:01:00-05:00",
                    "microprice_series": [2645.4, 2646.0],
                    "mid_price_series": [2645.5, 2646.0],
                    "last_price_series": [2645.0, 2645.8],
                    "vwap_series": [2644.1, 2644.2],
                },
                {
                    "symbol": "NUCO",
                    "record_type": "session_vector#2026-08-21",
                    "trading_date": "2026-08-21",
                    "timezone": "America/Bogota",
                    "sampling_seconds": 30,
                    "session_start": "2026-08-21T08:30:00-05:00",
                    "session_end": "2026-08-21T15:00:00-05:00",
                    "latest_sample_index": 62,
                    "latest_captured_at": "2026-08-21T09:01:00-05:00",
                    "segment_count": 1,
                    "samples_per_segment": 156,
                },
            ]
        }


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


class FakeStockOrdersLookupTable:
    def get_item(self, *, Key: dict, ProjectionExpression: str) -> dict:
        assert ProjectionExpression == (
            "record_checksum, source_file_checksum, source_line_number, "
            "created_at, created_month, created_at_symbol, symbol, order_side, "
            "raw_status, normalized_status, requested_quantity, filled_quantity, "
            "pending_quantity, price_per_share, gross_amount, commission_amount, "
            "net_amount, currency, imported_at"
        )
        if Key["record_checksum"] != "checksum-1":
            return {}
        return {
            "Item": {
                "record_checksum": "checksum-1",
                "source_file_checksum": "source-1",
                "source_line_number": 4,
                "created_at": "2026-08-13T13:59:00-05:00",
                "created_month": "2026-08",
                "imported_at": "2026-08-21T11:58:09-05:00",
                "created_at_symbol": "2026-08-13T13:59:00-05:00#NUCO",
                "symbol": "NUCO",
                "order_side": "sell",
                "raw_status": "Cancelado",
                "normalized_status": "cancelled",
                "requested_quantity": 0,
                "filled_quantity": 0,
                "pending_quantity": 0,
                "price_per_share": 43700,
                "gross_amount": 8303000,
                "commission_amount": 0,
                "net_amount": 8303000,
                "currency": "COP",
            }
        }

    def query(self, **kwargs) -> dict:
        assert kwargs["ProjectionExpression"] == (
            "record_checksum, source_file_checksum, source_line_number, "
            "created_at, created_month, created_at_symbol, symbol, order_side, "
            "raw_status, normalized_status, requested_quantity, filled_quantity, "
            "pending_quantity, price_per_share, gross_amount, commission_amount, "
            "net_amount, currency, imported_at"
        )
        if kwargs.get("IndexName") == "symbol-created-at-index":
            return {
                "Items": [
                    {
                        "record_checksum": "checksum-1",
                        "source_file_checksum": "source-1",
                        "source_line_number": 4,
                        "created_at": "2026-08-13T13:59:00-05:00",
                        "created_month": "2026-08",
                        "imported_at": "2026-08-21T11:58:09-05:00",
                        "created_at_symbol": "2026-08-13T13:59:00-05:00#NUCO",
                        "symbol": "NUCO",
                        "order_side": "sell",
                        "raw_status": "Cancelado",
                        "normalized_status": "cancelled",
                        "requested_quantity": 0,
                        "filled_quantity": 0,
                        "pending_quantity": 0,
                        "price_per_share": 43700,
                        "gross_amount": 8303000,
                        "commission_amount": 0,
                        "net_amount": 8303000,
                        "currency": "COP",
                    },
                    {
                        "record_checksum": "checksum-2",
                        "source_file_checksum": "source-2",
                        "source_line_number": 9,
                        "created_at": "2026-08-12T10:05:00-05:00",
                        "created_month": "2026-08",
                        "imported_at": "2026-08-20T09:40:00-05:00",
                        "created_at_symbol": "2026-08-12T10:05:00-05:00#NUCO",
                        "symbol": "NUCO",
                        "order_side": "buy",
                        "raw_status": "Aprobado",
                        "normalized_status": "approved",
                        "requested_quantity": 10,
                        "filled_quantity": 10,
                        "pending_quantity": 0,
                        "price_per_share": 43000,
                        "gross_amount": 430000,
                        "commission_amount": 0,
                        "net_amount": 430000,
                        "currency": "COP",
                    },
                ]
            }
        if kwargs.get("IndexName") == "created-month-index":
            return {
                "Items": [
                    {
                        "record_checksum": "checksum-1",
                        "source_file_checksum": "source-1",
                        "source_line_number": 4,
                        "created_at": "2026-08-13T13:59:00-05:00",
                        "created_month": "2026-08",
                        "imported_at": "2026-08-21T11:58:09-05:00",
                        "created_at_symbol": "2026-08-13T13:59:00-05:00#NUCO",
                        "symbol": "NUCO",
                        "order_side": "sell",
                        "raw_status": "Cancelado",
                        "normalized_status": "cancelled",
                        "requested_quantity": 0,
                        "filled_quantity": 0,
                        "pending_quantity": 0,
                        "price_per_share": 43700,
                        "gross_amount": 8303000,
                        "commission_amount": 0,
                        "net_amount": 8303000,
                        "currency": "COP",
                    }
                ]
            }
        return {"Items": []}


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
                },
                {
                    "pk": "NUCO",
                    "sk": "seasonality_profile",
                    "record_type": "seasonality_profile",
                    "bucket_granularity_minutes": 30,
                    "timezone": "America/Bogota",
                    "weekly_profile": {
                        "1": {
                            "weekday_label": "monday",
                            "days_processed": 3,
                            "hours": {
                                "09:00": {
                                    "accumulated_volume": 1200,
                                }
                            },
                        }
                    },
                },
            ]
        }


class FailingHistoricStatsTable:
    def query(self, **kwargs) -> dict:
        raise AssertionError("historic_stats should not be queried by analytics/snapshot")


class FailingCurrentSnapshotsTable:
    def get_item(self, *, Key: dict) -> dict:
        raise AssertionError("current_snapshots should not be queried by analytics/historic-stats")

    def query(self, **kwargs) -> dict:
        raise AssertionError("current_snapshots should not be queried by analytics/historic-stats")


class FakeAnalyticsCatalogTable:
    def get_item(self, *, Key: dict) -> dict:
        assert Key == {"pk": "analytics_catalog"}
        return {
            "Item": {
                "pk": "analytics_catalog",
                "record_type": "analytics_catalog",
                "trading_date": "2026-08-20",
                "to_timestamp": "2026-08-20T15:00:00-05:00",
                "symbol_count": 2,
                "record_count": 2,
                "catalog_version": 5,
                "updated_at": "2026-08-20T15:00:10-05:00",
                "symbols": ["ISA", "NUCO"],
                "records": [
                    {
                        "symbol": "ISA",
                        "current_snapshot_key": {
                            "symbol": "ISA",
                            "captured_at": "2026-08-20T14:58:00-05:00",
                        },
                    },
                    {
                        "symbol": "NUCO",
                        "current_snapshot_key": {
                            "symbol": "NUCO",
                            "captured_at": "2026-08-20T15:00:00-05:00",
                        },
                    },
                ],
            }
        }


def test_handler_returns_session_vector_manifest_and_segments() -> None:
    handler.SESSION_VECTORS_TABLE = FakeSessionVectorsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/session-vector",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "trading_date": "2026-08-21"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["trading_date"] == "2026-08-21"
    assert payload["result"]["segment_count"] == 1
    assert payload["result"]["manifest"]["latest_sample_index"] == 62
    assert payload["result"]["segments"][0]["segment_index"] == 0


def test_handler_returns_session_vector_head() -> None:
    handler.SESSION_VECTORS_TABLE = FakeSessionVectorsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/session-vector/head",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "trading_date": "2026-08-21"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["found"] is True
    assert payload["result"]["manifest"]["record_type"] == "session_vector#2026-08-21"
    assert payload["result"]["manifest"]["latest_captured_at"] == "2026-08-21T09:01:00-05:00"


def test_handler_returns_session_vector_segments_from_segment_index() -> None:
    handler.SESSION_VECTORS_TABLE = FakeSessionVectorsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/session-vector/segments",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {
                "symbol": "nuco",
                "trading_date": "2026-08-21",
                "from_segment": "1",
            },
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["from_segment"] == 1
    assert payload["result"]["segment_count"] == 1
    assert payload["result"]["segments"][0]["segment_index"] == 1


def test_handler_falls_back_to_latest_available_session_vector_on_or_before_requested_date() -> None:
    handler.SESSION_VECTORS_TABLE = FakeSessionVectorsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/session-vector/head",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "trading_date": "2026-08-22"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["found"] is True
    assert payload["result"]["trading_date"] == "2026-08-21"
    assert payload["result"]["manifest"]["record_type"] == "session_vector#2026-08-21"


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


def test_handler_orders_requires_exactly_one_indexed_filter() -> None:
    response = handler.handler(
        {
            "routeKey": "GET /orders",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 400
    assert payload["status"] == "error"
    assert "exactamente uno" in payload["message"]


def test_handler_orders_can_lookup_by_symbol_with_full_projection() -> None:
    handler.STOCK_ORDERS_TABLE = FakeStockOrdersLookupTable()

    response = handler.handler(
        {
            "routeKey": "GET /orders",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "limit": "2"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["lookup_mode"] == "symbol"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["record_count"] == 2
    assert payload["result"]["records"][0] == {
        "record_checksum": "checksum-1",
        "source_file_checksum": "source-1",
        "source_line_number": 4,
        "created_at": "2026-08-13T13:59:00-05:00",
        "created_month": "2026-08",
        "imported_at": "2026-08-21T11:58:09-05:00",
        "created_at_symbol": "2026-08-13T13:59:00-05:00#NUCO",
        "symbol": "NUCO",
        "order_side": "sell",
        "raw_status": "Cancelado",
        "normalized_status": "cancelled",
        "requested_quantity": 0,
        "filled_quantity": 0,
        "pending_quantity": 0,
        "price_per_share": 43700,
        "gross_amount": 8303000,
        "commission_amount": 0,
        "net_amount": 8303000,
        "currency": "COP",
    }


def test_handler_orders_can_lookup_by_record_checksum() -> None:
    handler.STOCK_ORDERS_TABLE = FakeStockOrdersLookupTable()

    response = handler.handler(
        {
            "routeKey": "GET /orders",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"record_checksum": "checksum-1"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["lookup_mode"] == "record_checksum"
    assert payload["result"]["record_count"] == 1
    assert payload["result"]["records"][0]["imported_at"] == "2026-08-21T11:58:09-05:00"
    assert payload["result"]["records"][0]["commission_amount"] == 0
    assert payload["result"]["records"][0]["normalized_status"] == "cancelled"


def test_handler_snapshot_uses_only_current_snapshots_and_historic_stats() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()
    handler.HISTORIC_STATS_TABLE = FailingHistoricStatsTable()

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
    assert "current_stats" not in payload["result"]
    assert "previous_stats" not in payload["result"]
    assert "market_ai_recommendation" not in payload["result"]


def test_handler_snapshot_accepts_optional_limit() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FakeCurrentSnapshotsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/snapshot",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "limit": "5"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["record_count"] == 2


def test_handler_historic_stats_uses_only_historic_stats_and_accepts_iam_auth() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FailingCurrentSnapshotsTable()
    handler.HISTORIC_STATS_TABLE = FakeHistoricStatsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/historic-stats",
            "requestContext": {
                "authorizer": {
                    "iam": {
                        "userArn": "arn:aws:iam::311923415472:user/test-user",
                    }
                }
            },
            "queryStringParameters": {"symbol": "nuco"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["record_count"] == 2
    assert payload["result"]["records"][0]["metric"] == "spread_bps"
    assert payload["result"]["records"][1]["record_type"] == "seasonality_profile"


def test_handler_historic_stats_can_return_seasonality_profile_only() -> None:
    handler.CURRENT_SNAPSHOTS_TABLE = FailingCurrentSnapshotsTable()
    handler.HISTORIC_STATS_TABLE = FakeHistoricStatsTable()

    response = handler.handler(
        {
            "routeKey": "GET /analytics/historic-stats",
            "headers": {"X-Api-Token": "test-token"},
            "queryStringParameters": {"symbol": "nuco", "metric": "seasonality_profile"},
        },
        None,
    )

    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert payload["status"] == "ok"
    assert payload["result"]["symbol"] == "NUCO"
    assert payload["result"]["metric"] == "seasonality_profile"
    assert payload["result"]["record_count"] == 1
    assert payload["result"]["records"][0]["record_type"] == "seasonality_profile"


def test_handler_catalog_uses_latest_available_snapshot_date() -> None:
    handler.ANALYTICS_CATALOG_TABLE = FakeAnalyticsCatalogTable()

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
    assert payload["result"]["record_count"] == 2
    assert payload["result"]["records"][0]["current_snapshot_key"]["symbol"] == "ISA"
    assert payload["result"]["catalog"]["pk"] == "analytics_catalog"
    assert payload["result"]["catalog"]["record_type"] == "analytics_catalog"
    assert payload["result"]["catalog"]["catalog_version"] == 5
