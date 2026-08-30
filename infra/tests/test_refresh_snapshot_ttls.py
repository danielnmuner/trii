from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_FILE = ROOT_DIR / "infra" / "scripts" / "refresh_snapshot_ttls.py"

spec = importlib.util.spec_from_file_location("refresh_snapshot_ttls", SCRIPT_FILE)
assert spec is not None and spec.loader is not None
refresh_snapshot_ttls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh_snapshot_ttls)


class FakeTable:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.scan_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self._page_index = 0

    def scan(self, **kwargs):
        self.scan_calls.append(dict(kwargs))
        page = dict(self.pages[self._page_index])
        self._page_index += 1
        return page

    def update_item(self, **kwargs):
        self.update_calls.append(dict(kwargs))
        return {}


class FakeDynamoResource:
    def __init__(self, tables: dict[str, FakeTable]) -> None:
        self.tables = tables

    def Table(self, table_name: str) -> FakeTable:
        return self.tables[table_name]


def test_compute_expires_at_uses_captured_at_timestamp() -> None:
    expires_at = refresh_snapshot_ttls._compute_expires_at("2026-08-30T10:00:00-05:00", 24 * 60 * 60)
    assert expires_at == 1788188400


def test_refresh_table_ttls_preview_reports_changes_without_writing() -> None:
    fake_table = FakeTable(
        [
            {
                "Items": [
                    {
                        "symbol": "ISA",
                        "captured_at": "2026-08-30T10:00:00-05:00",
                        "expires_at": 1788188400,
                    },
                    {
                        "symbol": "CIB",
                        "captured_at": "2026-08-30T10:10:00-05:00",
                        "expires_at": 0,
                    },
                ],
                "LastEvaluatedKey": {"symbol": "CIB", "captured_at": "2026-08-30T10:10:00-05:00"},
            },
            {
                "Items": [
                    {
                        "symbol": "",
                        "captured_at": "",
                    }
                ]
            },
        ]
    )
    refresh_snapshot_ttls.DYNAMODB_RESOURCE = FakeDynamoResource(
        {"trii-prod-current-snapshots": fake_table}
    )

    result = refresh_snapshot_ttls._refresh_table_ttls(
        table_name="trii-prod-current-snapshots",
        retention_seconds=24 * 60 * 60,
        timestamp_field="captured_at",
        projection_fields=["symbol", "captured_at", "expires_at"],
        key_fields=["symbol", "captured_at"],
        apply=False,
    )

    assert result["scanned_count"] == 3
    assert result["invalid_count"] == 1
    assert result["would_change_count"] == 1
    assert result["unchanged_count"] == 1
    assert result["updated_count"] == 0
    assert fake_table.update_calls == []
    assert len(fake_table.scan_calls) == 2


def test_refresh_table_ttls_apply_overwrites_every_valid_item() -> None:
    fake_table = FakeTable(
        [
            {
                "Items": [
                    {
                        "symbol": "ISA",
                        "captured_at": "2026-08-30T10:00:00-05:00",
                        "expires_at": 1,
                    },
                    {
                        "symbol": "CIB",
                        "captured_at": "2026-08-30T10:10:00-05:00",
                        "expires_at": 2,
                    },
                ]
            }
        ]
    )
    refresh_snapshot_ttls.DYNAMODB_RESOURCE = FakeDynamoResource(
        {"trii-prod-snapshot-ingestion-raw": fake_table}
    )

    result = refresh_snapshot_ttls._refresh_table_ttls(
        table_name="trii-prod-snapshot-ingestion-raw",
        retention_seconds=24 * 60 * 60,
        timestamp_field="captured_at",
        projection_fields=["symbol", "captured_at", "expires_at"],
        key_fields=["symbol", "captured_at"],
        apply=True,
    )

    assert result["scanned_count"] == 2
    assert result["updated_count"] == 2
    assert fake_table.update_calls == [
        {
            "Key": {"symbol": "ISA", "captured_at": "2026-08-30T10:00:00-05:00"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788188400},
        },
        {
            "Key": {"symbol": "CIB", "captured_at": "2026-08-30T10:10:00-05:00"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788189000},
        },
    ]


def test_refresh_table_ttls_apply_supports_checksum_key_tables() -> None:
    fake_table = FakeTable(
        [
            {
                "Items": [
                    {
                        "snapshot_checksum": "checksum-1",
                        "accepted_at": "2026-08-30T11:00:00-05:00",
                        "expires_at": 1,
                    },
                    {
                        "snapshot_checksum": "checksum-2",
                        "accepted_at": "2026-08-30T11:10:00-05:00",
                        "expires_at": 2,
                    },
                ]
            }
        ]
    )
    refresh_snapshot_ttls.DYNAMODB_RESOURCE = FakeDynamoResource(
        {"trii-prod-snapshot-ingestion-checksums": fake_table}
    )

    result = refresh_snapshot_ttls._refresh_table_ttls(
        table_name="trii-prod-snapshot-ingestion-checksums",
        retention_seconds=24 * 60 * 60,
        timestamp_field="accepted_at",
        projection_fields=["snapshot_checksum", "accepted_at", "expires_at"],
        key_fields=["snapshot_checksum"],
        apply=True,
    )

    assert result["scanned_count"] == 2
    assert result["updated_count"] == 2
    assert fake_table.update_calls == [
        {
            "Key": {"snapshot_checksum": "checksum-1"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788192000},
        },
        {
            "Key": {"snapshot_checksum": "checksum-2"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788192600},
        },
    ]
