from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_FILE = ROOT_DIR / "infra" / "scripts" / "dynamodb_usage_audit.py"

spec = importlib.util.spec_from_file_location("dynamodb_usage_audit", SCRIPT_FILE)
assert spec is not None and spec.loader is not None
dynamodb_usage_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamodb_usage_audit)


class FakeDynamoClient:
    def list_tables(self, **kwargs):
        assert kwargs == {}
        return {
            "TableNames": [
                "other-table",
                "trii-prod-current-snapshots",
                "trii-prod-historic-stats",
            ]
        }

    def describe_table(self, *, TableName: str):
        descriptions = {
            "trii-prod-current-snapshots": {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 62,
                    "TableSizeBytes": 2048,
                    "StreamSpecification": {"StreamEnabled": True},
                    "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
                    "GlobalSecondaryIndexes": [
                        {"IndexName": "captured-date-index"},
                    ],
                }
            },
            "trii-prod-historic-stats": {
                "Table": {
                    "TableStatus": "ACTIVE",
                    "ItemCount": 1000,
                    "TableSizeBytes": 4096,
                    "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
                    "GlobalSecondaryIndexes": [],
                }
            },
        }
        return descriptions[TableName]


class FakeCloudWatchClient:
    def get_metric_statistics(
        self,
        *,
        Namespace: str,
        MetricName: str,
        Dimensions: list[dict[str, str]],
        StartTime: datetime,
        EndTime: datetime,
        Period: int,
        Statistics: list[str],
    ):
        assert Namespace == "AWS/DynamoDB"
        assert Period == dynamodb_usage_audit.METRIC_PERIOD_SECONDS
        assert Statistics == ["Sum"]
        assert StartTime.tzinfo == UTC
        assert EndTime.tzinfo == UTC

        table_name = next(item["Value"] for item in Dimensions if item["Name"] == "TableName")
        index_name = next((item["Value"] for item in Dimensions if item["Name"] == "GlobalSecondaryIndexName"), None)

        totals = {
            ("trii-prod-current-snapshots", None, "ConsumedWriteCapacityUnits"): 100.0,
            ("trii-prod-current-snapshots", None, "ConsumedReadCapacityUnits"): 25.0,
            ("trii-prod-current-snapshots", None, "WriteThrottleEvents"): 0.0,
            ("trii-prod-current-snapshots", None, "ReadThrottleEvents"): 0.0,
            ("trii-prod-current-snapshots", None, "ConditionalCheckFailedRequests"): 3.0,
            ("trii-prod-current-snapshots", None, "TransactionConflict"): 0.0,
            ("trii-prod-current-snapshots", None, "UserErrors"): 0.0,
            ("trii-prod-current-snapshots", None, "SystemErrors"): 0.0,
            ("trii-prod-current-snapshots", "captured-date-index", "ConsumedWriteCapacityUnits"): 100.0,
            ("trii-prod-current-snapshots", "captured-date-index", "ConsumedReadCapacityUnits"): 5.0,
            ("trii-prod-historic-stats", None, "ConsumedWriteCapacityUnits"): 900.0,
            ("trii-prod-historic-stats", None, "ConsumedReadCapacityUnits"): 50.0,
            ("trii-prod-historic-stats", None, "WriteThrottleEvents"): 1.0,
            ("trii-prod-historic-stats", None, "ReadThrottleEvents"): 0.0,
            ("trii-prod-historic-stats", None, "ConditionalCheckFailedRequests"): 0.0,
            ("trii-prod-historic-stats", None, "TransactionConflict"): 2.0,
            ("trii-prod-historic-stats", None, "UserErrors"): 0.0,
            ("trii-prod-historic-stats", None, "SystemErrors"): 0.0,
        }
        total = totals.get((table_name, index_name, MetricName), 0.0)
        return {"Datapoints": [{"Sum": total}]}


class FakeCostExplorerClient:
    def get_cost_and_usage(self, **kwargs):
        assert kwargs["Filter"]["Dimensions"]["Values"] == ["Amazon DynamoDB"]
        return {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["USE1-DDB-WriteUnits"],
                            "Metrics": {
                                "UnblendedCost": {"Amount": "4.92"},
                                "UsageQuantity": {"Amount": "7879833"},
                            },
                        },
                        {
                            "Keys": ["USE1-DDB-ReadUnits"],
                            "Metrics": {
                                "UnblendedCost": {"Amount": "0.49"},
                                "UsageQuantity": {"Amount": "3949752.5"},
                            },
                        },
                    ]
                }
            ]
        }


def test_list_prefixed_tables_filters_and_sorts() -> None:
    dynamodb_usage_audit.DYNAMODB_CLIENT = FakeDynamoClient()

    tables = dynamodb_usage_audit._list_prefixed_tables("trii-prod-")

    assert tables == [
        "trii-prod-current-snapshots",
        "trii-prod-historic-stats",
    ]


def test_build_summary_reports_top_table_and_costs() -> None:
    dynamodb_usage_audit.DYNAMODB_CLIENT = FakeDynamoClient()
    dynamodb_usage_audit.CLOUDWATCH_CLIENT = FakeCloudWatchClient()
    dynamodb_usage_audit.COST_EXPLORER_CLIENT = FakeCostExplorerClient()
    dynamodb_usage_audit._utc_now = lambda: datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    summary = dynamodb_usage_audit._build_summary(
        table_prefix="trii-prod-",
        lookback_days=4,
        include_cost_explorer=True,
    )

    assert summary["table_count"] == 2
    assert summary["tables"][0]["table_name"] == "trii-prod-historic-stats"
    assert summary["tables"][0]["approx_total_write_units_with_indexes"] == 900.0
    assert summary["tables"][1]["table_name"] == "trii-prod-current-snapshots"
    assert summary["tables"][1]["approx_total_write_units_with_indexes"] == 200.0
    assert summary["totals"]["approx_total_write_units_with_indexes"] == 1100.0
    assert summary["cost_explorer"]["groups"][0]["usage_type"] == "USE1-DDB-WriteUnits"


def test_build_markdown_report_includes_top_table_rows() -> None:
    summary = {
        "window_start_utc": "2026-09-01T12:00:00+00:00",
        "window_end_utc": "2026-09-05T12:00:00+00:00",
        "lookback_days": 4,
        "table_prefix": "trii-prod-",
        "table_count": 1,
        "totals": {
            "approx_total_write_units_with_indexes": 123.0,
            "approx_total_read_units_with_indexes": 45.0,
        },
        "tables": [
            {
                "table_name": "trii-prod-historic-stats",
                "approx_total_write_units_with_indexes": 123.0,
                "approx_total_read_units_with_indexes": 45.0,
                "write_read_ratio": 2.7333333333333334,
                "global_secondary_indexes": [],
            }
        ],
        "cost_explorer": {
            "groups": [
                {
                    "usage_type": "USE1-DDB-WriteUnits",
                    "unblended_cost_usd": 4.92,
                    "usage_quantity": 7879833.0,
                }
            ]
        },
    }

    markdown = dynamodb_usage_audit._build_markdown_report(summary)

    assert "DynamoDB usage audit" in markdown
    assert "trii-prod-historic-stats" in markdown
    assert "USE1-DDB-WriteUnits" in markdown
