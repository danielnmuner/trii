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


def test_refresh_table_ttls_apply_supports_session_vectors_manifest_and_segments() -> None:
    fake_table = FakeTable(
        [
            {
                "Items": [
                    {
                        "symbol": "ECOPETROL",
                        "record_type": "session_vector#2026-08-30",
                        "latest_captured_at": "2026-08-30T11:56:00-05:00",
                        "expires_at": 1,
                    },
                    {
                        "symbol": "ECOPETROL",
                        "record_type": "session_vector#2026-08-30#segment#000",
                        "to_captured_at": "2026-08-30T09:47:30-05:00",
                        "expires_at": 2,
                    },
                ]
            }
        ]
    )
    refresh_snapshot_ttls.DYNAMODB_RESOURCE = FakeDynamoResource(
        {"trii-prod-session-vectors": fake_table}
    )

    result = refresh_snapshot_ttls._refresh_table_ttls(
        table_name="trii-prod-session-vectors",
        retention_seconds=120 * 60 * 60,
        timestamp_field="latest_captured_at",
        projection_fields=["symbol", "record_type", "latest_captured_at", "to_captured_at", "expires_at"],
        key_fields=["symbol", "record_type"],
        apply=True,
    )

    assert result["scanned_count"] == 2
    assert result["updated_count"] == 2
    assert fake_table.update_calls == [
        {
            "Key": {"symbol": "ECOPETROL", "record_type": "session_vector#2026-08-30"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788540960},
        },
        {
            "Key": {"symbol": "ECOPETROL", "record_type": "session_vector#2026-08-30#segment#000"},
            "UpdateExpression": "SET expires_at = :expires_at",
            "ExpressionAttributeValues": {":expires_at": 1788533250},
        },
    ]
