from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

import boto3


CURRENT_SNAPSHOTS_TABLE_NAME = "trii-prod-current-snapshots"
SESSION_VECTORS_TABLE_NAME = "trii-prod-session-vectors"

TABLE_CONFIGS: dict[str, dict[str, Any]] = {
    "current-snapshots": {
        "table_name": CURRENT_SNAPSHOTS_TABLE_NAME,
        "retention_seconds": 48 * 60 * 60,
        "timestamp_field": "captured_at",
        "projection_fields": ["symbol", "captured_at", "expires_at"],
        "key_fields": ["symbol", "captured_at"],
    },
    "session-vectors": {
        "table_name": SESSION_VECTORS_TABLE_NAME,
        "retention_seconds": 24 * 60 * 60,
        "timestamp_field": "latest_captured_at",
        "projection_fields": ["symbol", "record_type", "latest_captured_at", "to_captured_at", "expires_at"],
        "key_fields": ["symbol", "record_type"],
    },
}

DYNAMODB_RESOURCE = None


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _compute_expires_at(base_timestamp: str, retention_seconds: int) -> int:
    timestamp = _parse_timestamp(base_timestamp)
    return int(timestamp.timestamp()) + retention_seconds


def _scan_projection(table, projection_fields: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    expression_attribute_names = {f"#field{index}": field for index, field in enumerate(projection_fields)}
    scan_kwargs = {
        "ProjectionExpression": ", ".join(expression_attribute_names.keys()),
        "ExpressionAttributeNames": expression_attribute_names,
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


def _refresh_table_ttls(
    *,
    table_name: str,
    retention_seconds: int,
    timestamp_field: str,
    projection_fields: list[str],
    key_fields: list[str],
    apply: bool,
) -> dict[str, Any]:
    table = _get_dynamodb_resource().Table(table_name)
    print(
        json.dumps(
            {
                "table_name": table_name,
                "step": "scan_started",
                "apply": apply,
                "retention_hours": retention_seconds // 3600,
            }
        ),
        file=sys.stderr,
    )
    items = _scan_projection(table, projection_fields)
    print(
        json.dumps(
            {
                "table_name": table_name,
                "step": "scan_completed",
                "apply": apply,
                "scanned_count": len(items),
            }
        ),
        file=sys.stderr,
    )

    scanned_count = 0
    invalid_count = 0
    would_change_count = 0
    unchanged_count = 0
    updated_count = 0
    invalid_keys: list[dict[str, str]] = []

    for item in items:
        scanned_count += 1
        key = {field_name: str(item.get(field_name) or "").strip() for field_name in key_fields}
        base_timestamp = str(item.get(timestamp_field) or "").strip()
        if timestamp_field == "latest_captured_at" and "#segment#" in str(item.get("record_type") or ""):
            base_timestamp = str(item.get("to_captured_at") or "").strip()
        if any(not field_value for field_value in key.values()) or not base_timestamp:
            invalid_count += 1
            if len(invalid_keys) < 20:
                invalid_keys.append({**key, timestamp_field: base_timestamp})
            continue

        desired_expires_at = _compute_expires_at(base_timestamp, retention_seconds)
        current_expires_at = item.get("expires_at")
        try:
            current_expires_at_int = int(current_expires_at) if current_expires_at is not None else None
        except (TypeError, ValueError):
            current_expires_at_int = None

        if current_expires_at_int == desired_expires_at:
            unchanged_count += 1
            continue
        else:
            would_change_count += 1

        if not apply:
            continue

        table.update_item(
            Key=key,
            UpdateExpression="SET expires_at = :expires_at",
            ExpressionAttributeValues={
                ":expires_at": desired_expires_at,
            },
        )
        updated_count += 1

        if updated_count % 10000 == 0:
            print(
                json.dumps(
                    {
                        "table_name": table_name,
                        "step": "apply_progress",
                        "updated_count": updated_count,
                    }
                ),
                file=sys.stderr,
            )

    result = {
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
    print(
        json.dumps(
            {
                "table_name": table_name,
                "step": "table_completed",
                "apply": apply,
                "scanned_count": scanned_count,
                "would_change_count": would_change_count,
                "updated_count": updated_count,
                "invalid_count": invalid_count,
            }
        ),
        file=sys.stderr,
    )
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recalcula y sobreescribe expires_at para las tablas de snapshots."
    )
    parser.add_argument(
        "--table",
        dest="tables",
        action="append",
        choices=sorted(TABLE_CONFIGS.keys()),
        help="Tabla logica a procesar. Si se omite, procesa todas.",
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
            timestamp_field=str(TABLE_CONFIGS[table_name]["timestamp_field"]),
            projection_fields=list(TABLE_CONFIGS[table_name]["projection_fields"]),
            key_fields=list(TABLE_CONFIGS[table_name]["key_fields"]),
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
