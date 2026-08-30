from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

import boto3


RAW_SNAPSHOT_TABLE_NAME = "trii-prod-snapshot-ingestion-raw"
CURRENT_SNAPSHOTS_TABLE_NAME = "trii-prod-current-snapshots"

TABLE_CONFIGS: dict[str, dict[str, Any]] = {
    "snapshot-ingestion-raw": {
        "table_name": RAW_SNAPSHOT_TABLE_NAME,
        "retention_seconds": 24 * 60 * 60,
    },
    "current-snapshots": {
        "table_name": CURRENT_SNAPSHOTS_TABLE_NAME,
        "retention_seconds": 48 * 60 * 60,
    },
}

DYNAMODB_RESOURCE = None


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _compute_expires_at(captured_at: str, retention_seconds: int) -> int:
    captured_timestamp = _parse_timestamp(captured_at)
    return int(captured_timestamp.timestamp()) + retention_seconds


def _scan_projection(table) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs = {
        "ProjectionExpression": "#symbol, captured_at, expires_at",
        "ExpressionAttributeNames": {"#symbol": "symbol"},
    }
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"], **scan_kwargs)
        items.extend(response.get("Items", []))
    return items


def _get_dynamodb_resource():
    global DYNAMODB_RESOURCE
    if DYNAMODB_RESOURCE is None:
        DYNAMODB_RESOURCE = boto3.resource("dynamodb")
    return DYNAMODB_RESOURCE


def _refresh_table_ttls(*, table_name: str, retention_seconds: int, apply: bool) -> dict[str, Any]:
    table = _get_dynamodb_resource().Table(table_name)
    items = _scan_projection(table)

    scanned_count = 0
    invalid_count = 0
    would_change_count = 0
    unchanged_count = 0
    updated_count = 0
    invalid_keys: list[dict[str, str]] = []

    for item in items:
        scanned_count += 1
        symbol = str(item.get("symbol") or "").strip()
        captured_at = str(item.get("captured_at") or "").strip()
        if not symbol or not captured_at:
            invalid_count += 1
            if len(invalid_keys) < 20:
                invalid_keys.append(
                    {
                        "symbol": symbol,
                        "captured_at": captured_at,
                    }
                )
            continue

        desired_expires_at = _compute_expires_at(captured_at, retention_seconds)
        current_expires_at = item.get("expires_at")
        try:
            current_expires_at_int = int(current_expires_at) if current_expires_at is not None else None
        except (TypeError, ValueError):
            current_expires_at_int = None

        if current_expires_at_int == desired_expires_at:
            unchanged_count += 1
        else:
            would_change_count += 1

        if not apply:
            continue

        table.update_item(
            Key={
                "symbol": symbol,
                "captured_at": captured_at,
            },
            UpdateExpression="SET expires_at = :expires_at",
            ExpressionAttributeValues={
                ":expires_at": desired_expires_at,
            },
        )
        updated_count += 1

    return {
        "table_name": table_name,
        "retention_hours": retention_seconds // 3600,
        "apply": apply,
        "scanned_count": scanned_count,
        "invalid_count": invalid_count,
        "would_change_count": would_change_count,
        "unchanged_count": unchanged_count,
        "updated_count": updated_count,
        "invalid_keys": invalid_keys,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recalcula y sobreescribe expires_at para las tablas de snapshots."
    )
    parser.add_argument(
        "--table",
        dest="tables",
        action="append",
        choices=sorted(TABLE_CONFIGS.keys()),
        help="Tabla logica a procesar. Si se omite, procesa ambas.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica cambios reales. Sin este flag corre en preview.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    table_names = args.tables or list(TABLE_CONFIGS.keys())

    results = [
        _refresh_table_ttls(
            table_name=str(TABLE_CONFIGS[table_name]["table_name"]),
            retention_seconds=int(TABLE_CONFIGS[table_name]["retention_seconds"]),
            apply=bool(args.apply),
        )
        for table_name in table_names
    ]

    summary = {
        "apply": bool(args.apply),
        "table_count": len(results),
        "tables": results,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
