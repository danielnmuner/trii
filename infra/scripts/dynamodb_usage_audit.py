from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3


DYNAMODB_CLIENT = None
CLOUDWATCH_CLIENT = None
COST_EXPLORER_CLIENT = None

DEFAULT_TABLE_PREFIX = "trii-prod-"
DEFAULT_LOOKBACK_DAYS = 4
METRIC_PERIOD_SECONDS = 3600
TABLE_METRICS = (
    "ConsumedWriteCapacityUnits",
    "ConsumedReadCapacityUnits",
    "WriteThrottleEvents",
    "ReadThrottleEvents",
    "ConditionalCheckFailedRequests",
    "TransactionConflict",
    "UserErrors",
    "SystemErrors",
)
TABLE_DESCRIPTION_CACHE: dict[str, dict[str, Any]] = {}


def _get_dynamodb_client():
    global DYNAMODB_CLIENT
    if DYNAMODB_CLIENT is None:
        DYNAMODB_CLIENT = boto3.client("dynamodb")
    return DYNAMODB_CLIENT


def _get_cloudwatch_client():
    global CLOUDWATCH_CLIENT
    if CLOUDWATCH_CLIENT is None:
        CLOUDWATCH_CLIENT = boto3.client("cloudwatch")
    return CLOUDWATCH_CLIENT


def _get_cost_explorer_client():
    global COST_EXPLORER_CLIENT
    if COST_EXPLORER_CLIENT is None:
        COST_EXPLORER_CLIENT = boto3.client("ce", region_name="us-east-1")
    return COST_EXPLORER_CLIENT


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_day_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _daily_windows(*, end_time: datetime, lookback_days: int) -> list[dict[str, Any]]:
    start_of_today = _utc_day_start(end_time)
    windows: list[dict[str, Any]] = []
    for days_ago in range(lookback_days - 1, -1, -1):
        day_start = start_of_today - timedelta(days=days_ago)
        day_end = min(day_start + timedelta(days=1), end_time)
        if day_end <= day_start:
            continue
        windows.append(
            {
                "date": day_start.date().isoformat(),
                "start_time": day_start,
                "end_time": day_end,
            }
        )
    return windows


def _metric_total(
    *,
    metric_name: str,
    dimensions: list[dict[str, str]],
    start_time: datetime,
    end_time: datetime,
) -> float:
    response = _get_cloudwatch_client().get_metric_statistics(
        Namespace="AWS/DynamoDB",
        MetricName=metric_name,
        Dimensions=dimensions,
        StartTime=start_time,
        EndTime=end_time,
        Period=METRIC_PERIOD_SECONDS,
        Statistics=["Sum"],
    )
    datapoints = response.get("Datapoints", [])
    return float(sum(float(point.get("Sum", 0.0) or 0.0) for point in datapoints))


def _list_prefixed_tables(table_prefix: str) -> list[str]:
    client = _get_dynamodb_client()
    table_names: list[str] = []
    last_evaluated_table_name: str | None = None

    while True:
        kwargs: dict[str, Any] = {}
        if last_evaluated_table_name is not None:
            kwargs["ExclusiveStartTableName"] = last_evaluated_table_name
        response = client.list_tables(**kwargs)
        table_names.extend(
            sorted(
                table_name
                for table_name in response.get("TableNames", [])
                if str(table_name).startswith(table_prefix)
            )
        )
        last_evaluated_table_name = response.get("LastEvaluatedTableName")
        if not last_evaluated_table_name:
            break

    return sorted(set(table_names))


def _describe_table(table_name: str) -> dict[str, Any]:
    cached = TABLE_DESCRIPTION_CACHE.get(table_name)
    if cached is not None:
        return dict(cached)
    response = _get_dynamodb_client().describe_table(TableName=table_name)
    description = dict(response["Table"])
    TABLE_DESCRIPTION_CACHE[table_name] = description
    return dict(description)


def _index_names(table_description: dict[str, Any]) -> list[str]:
    return [
        str(index.get("IndexName"))
        for index in table_description.get("GlobalSecondaryIndexes", [])
        if str(index.get("IndexName") or "").strip()
    ]


def _table_metric_summary(
    *,
    table_name: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, float]:
    dimensions = [{"Name": "TableName", "Value": table_name}]
    return {
        metric_name: _metric_total(
            metric_name=metric_name,
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
        )
        for metric_name in TABLE_METRICS
    }


def _index_metric_summary(
    *,
    table_name: str,
    index_name: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, float]:
    dimensions = [
        {"Name": "TableName", "Value": table_name},
        {"Name": "GlobalSecondaryIndexName", "Value": index_name},
    ]
    return {
        metric_name: _metric_total(
            metric_name=metric_name,
            dimensions=dimensions,
            start_time=start_time,
            end_time=end_time,
        )
        for metric_name in ("ConsumedWriteCapacityUnits", "ConsumedReadCapacityUnits")
    }


def _summarize_table(
    *,
    table_name: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    description = _describe_table(table_name)
    table_metrics = _table_metric_summary(
        table_name=table_name,
        start_time=start_time,
        end_time=end_time,
    )
    indexes = [
        {
            "index_name": index_name,
            "metrics": _index_metric_summary(
                table_name=table_name,
                index_name=index_name,
                start_time=start_time,
                end_time=end_time,
            ),
        }
        for index_name in _index_names(description)
    ]

    write_units = float(table_metrics["ConsumedWriteCapacityUnits"])
    read_units = float(table_metrics["ConsumedReadCapacityUnits"])
    approx_total_write_units_with_indexes = write_units + sum(
        float(index["metrics"]["ConsumedWriteCapacityUnits"]) for index in indexes
    )
    approx_total_read_units_with_indexes = read_units + sum(
        float(index["metrics"]["ConsumedReadCapacityUnits"]) for index in indexes
    )
    write_read_ratio = None
    if approx_total_read_units_with_indexes > 0:
        write_read_ratio = approx_total_write_units_with_indexes / approx_total_read_units_with_indexes

    return {
        "table_name": table_name,
        "billing_mode": str(description.get("BillingModeSummary", {}).get("BillingMode") or "PAY_PER_REQUEST"),
        "table_status": str(description.get("TableStatus") or ""),
        "item_count": int(description.get("ItemCount", 0) or 0),
        "table_size_bytes": int(description.get("TableSizeBytes", 0) or 0),
        "stream_enabled": description.get("StreamSpecification", {}).get("StreamEnabled") is True,
        "metrics": table_metrics,
        "global_secondary_indexes": indexes,
        "approx_total_write_units_with_indexes": approx_total_write_units_with_indexes,
        "approx_total_read_units_with_indexes": approx_total_read_units_with_indexes,
        "write_read_ratio": write_read_ratio,
    }


def _daily_table_summaries(
    *,
    table_names: list[str],
    daily_windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    daily_rows: list[dict[str, Any]] = []
    for window in daily_windows:
        tables = [
            _summarize_table(
                table_name=table_name,
                start_time=window["start_time"],
                end_time=window["end_time"],
            )
            for table_name in table_names
        ]
        tables.sort(
            key=lambda table: float(table["approx_total_write_units_with_indexes"]),
            reverse=True,
        )
        daily_rows.append(
            {
                "date": window["date"],
                "window_start_utc": window["start_time"].isoformat(),
                "window_end_utc": window["end_time"].isoformat(),
                "totals": {
                    "approx_total_write_units_with_indexes": sum(
                        float(table["approx_total_write_units_with_indexes"]) for table in tables
                    ),
                    "approx_total_read_units_with_indexes": sum(
                        float(table["approx_total_read_units_with_indexes"]) for table in tables
                    ),
                    "write_throttle_events": sum(
                        float(table["metrics"]["WriteThrottleEvents"]) for table in tables
                    ),
                    "read_throttle_events": sum(
                        float(table["metrics"]["ReadThrottleEvents"]) for table in tables
                    ),
                },
                "tables": tables,
            }
        )
    return daily_rows


def _cost_explorer_summary(*, start_date: str, end_date: str) -> dict[str, Any]:
    response = _get_cost_explorer_client().get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_date},
        Granularity="DAILY",
        Metrics=["UnblendedCost", "UsageQuantity"],
        Filter={
            "Dimensions": {
                "Key": "SERVICE",
                "Values": ["Amazon DynamoDB"],
            }
        },
        GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
    )

    groups: dict[str, dict[str, float]] = {}
    daily: list[dict[str, Any]] = []
    for day in response.get("ResultsByTime", []):
        day_groups: list[dict[str, Any]] = []
        for group in day.get("Groups", []):
            usage_type = str((group.get("Keys") or ["unknown"])[0])
            metrics = group.get("Metrics", {})
            cost_amount = float(metrics.get("UnblendedCost", {}).get("Amount", 0.0) or 0.0)
            usage_amount = float(metrics.get("UsageQuantity", {}).get("Amount", 0.0) or 0.0)
            day_groups.append(
                {
                    "usage_type": usage_type,
                    "unblended_cost_usd": cost_amount,
                    "usage_quantity": usage_amount,
                }
            )
            aggregate = groups.setdefault(
                usage_type,
                {"unblended_cost_usd": 0.0, "usage_quantity": 0.0},
            )
            aggregate["unblended_cost_usd"] += cost_amount
            aggregate["usage_quantity"] += usage_amount
        day_groups.sort(key=lambda group: group["unblended_cost_usd"], reverse=True)
        daily.append(
            {
                "date": str(day.get("TimePeriod", {}).get("Start") or ""),
                "is_estimated": bool(day.get("Estimated")),
                "groups": day_groups,
                "totals": {
                    "unblended_cost_usd": sum(group["unblended_cost_usd"] for group in day_groups),
                    "usage_quantity": sum(group["usage_quantity"] for group in day_groups),
                },
            }
        )

    ordered_groups = [
        {"usage_type": usage_type, **payload}
        for usage_type, payload in sorted(
            groups.items(),
            key=lambda entry: entry[1]["unblended_cost_usd"],
            reverse=True,
        )
    ]

    return {
        "start_date": start_date,
        "end_date_exclusive": end_date,
        "groups": ordered_groups,
        "daily": daily,
    }


def _build_markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "## DynamoDB usage audit",
        "",
        f"- Window UTC: `{summary['window_start_utc']}` -> `{summary['window_end_utc']}`",
        f"- Lookback days: `{summary['lookback_days']}`",
        f"- Table prefix: `{summary['table_prefix']}`",
        f"- Tables analyzed: `{summary['table_count']}`",
        f"- Approx total write units: `{summary['totals']['approx_total_write_units_with_indexes']:.2f}`",
        f"- Approx total read units: `{summary['totals']['approx_total_read_units_with_indexes']:.2f}`",
        "",
        "### Daily totals",
        "",
        "| Date UTC | Approx writes | Approx reads | Write throttle events | Read throttle events |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for day in summary.get("daily", []):
        lines.append(
            f"| {day['date']} | {day['totals']['approx_total_write_units_with_indexes']:.2f} | "
            f"{day['totals']['approx_total_read_units_with_indexes']:.2f} | "
            f"{day['totals']['write_throttle_events']:.2f} | "
            f"{day['totals']['read_throttle_events']:.2f} |"
        )

    lines.extend(
        [
            "",
        "### Top tables by writes",
        "",
        "| Table | Approx writes | Approx reads | Write/Read ratio | Indexes |",
        "| --- | ---: | ---: | ---: | ---: |",
        ]
    )

    for table in summary["tables"]:
        ratio = table["write_read_ratio"]
        ratio_display = "n/a" if ratio is None else f"{ratio:.2f}"
        lines.append(
            f"| {table['table_name']} | {table['approx_total_write_units_with_indexes']:.2f} | "
            f"{table['approx_total_read_units_with_indexes']:.2f} | {ratio_display} | "
            f"{len(table['global_secondary_indexes'])} |"
        )

    cost_explorer = summary.get("cost_explorer")
    if cost_explorer:
        lines.extend(
            [
                "",
                "### Cost Explorer daily totals",
                "",
                "| Date UTC | Cost USD | Usage quantity | Estimated |",
                "| --- | ---: | ---: | --- |",
            ]
        )
        for day in cost_explorer.get("daily", []):
            lines.append(
                f"| {day['date']} | {day['totals']['unblended_cost_usd']:.4f} | "
                f"{day['totals']['usage_quantity']:.2f} | {str(day['is_estimated']).lower()} |"
            )
        lines.extend(
            [
                "",
                "### Cost Explorer by usage type",
                "",
                "| Usage type | Cost USD | Usage quantity |",
                "| --- | ---: | ---: |",
            ]
        )
        for group in cost_explorer.get("groups", []):
            lines.append(
                f"| {group['usage_type']} | {group['unblended_cost_usd']:.4f} | {group['usage_quantity']:.2f} |"
            )

    return "\n".join(lines) + "\n"


def _build_summary(
    *,
    table_prefix: str,
    lookback_days: int,
    include_cost_explorer: bool,
) -> dict[str, Any]:
    end_time = _utc_now()
    start_time = end_time - timedelta(days=lookback_days)
    start_date = start_time.date().isoformat()
    end_date = (end_time.date() + timedelta(days=1)).isoformat()
    table_names = _list_prefixed_tables(table_prefix)
    daily_windows = _daily_windows(
        end_time=end_time,
        lookback_days=lookback_days,
    )

    tables = [
        _summarize_table(
            table_name=table_name,
            start_time=start_time,
            end_time=end_time,
        )
        for table_name in table_names
    ]
    tables.sort(
        key=lambda table: float(table["approx_total_write_units_with_indexes"]),
        reverse=True,
    )

    totals = {
        "approx_total_write_units_with_indexes": sum(
            float(table["approx_total_write_units_with_indexes"]) for table in tables
        ),
        "approx_total_read_units_with_indexes": sum(
            float(table["approx_total_read_units_with_indexes"]) for table in tables
        ),
        "write_throttle_events": sum(
            float(table["metrics"]["WriteThrottleEvents"]) for table in tables
        ),
        "read_throttle_events": sum(
            float(table["metrics"]["ReadThrottleEvents"]) for table in tables
        ),
    }

    summary = {
        "generated_at_utc": _utc_now().isoformat(),
        "window_start_utc": start_time.isoformat(),
        "window_end_utc": end_time.isoformat(),
        "start_date": start_date,
        "end_date_exclusive": end_date,
        "lookback_days": lookback_days,
        "table_prefix": table_prefix,
        "table_count": len(tables),
        "totals": totals,
        "daily": _daily_table_summaries(
            table_names=table_names,
            daily_windows=daily_windows,
        ),
        "tables": tables,
    }

    if include_cost_explorer:
        summary["cost_explorer"] = _cost_explorer_summary(
            start_date=start_date,
            end_date=end_date,
        )

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audita el consumo de DynamoDB por tabla usando CloudWatch y opcionalmente Cost Explorer."
    )
    parser.add_argument(
        "--table-prefix",
        default=DEFAULT_TABLE_PREFIX,
        help="Prefijo de tablas DynamoDB a incluir.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=DEFAULT_LOOKBACK_DAYS,
        help="Cantidad de dias hacia atras a auditar.",
    )
    parser.add_argument(
        "--skip-cost-explorer",
        action="store_true",
        help="Omite el resumen de Cost Explorer.",
    )
    parser.add_argument(
        "--markdown-output",
        help="Ruta opcional para escribir un resumen markdown.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.lookback_days <= 0:
        raise SystemExit("`--lookback-days` debe ser mayor que cero.")

    summary = _build_summary(
        table_prefix=str(args.table_prefix),
        lookback_days=int(args.lookback_days),
        include_cost_explorer=not bool(args.skip_cost_explorer),
    )

    if args.markdown_output:
        with open(args.markdown_output, "w", encoding="utf-8") as markdown_file:
            markdown_file.write(_build_markdown_report(summary))

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
