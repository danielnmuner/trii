from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo


DYNAMODB_RESOURCE = boto3.resource("dynamodb")
CURRENT_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["CURRENT_SNAPSHOTS_TABLE"])
DAILY_CLOSING_SNAPSHOTS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["DAILY_CLOSING_SNAPSHOTS_TABLE"])
BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
MARKET_CLOSE_TIME = time(hour=15, minute=0)
DEFAULT_TIMEZONE_NAME = "America/Bogota"


def _next_monday(value: date) -> date:
    days_until_monday = (7 - value.weekday()) % 7
    if days_until_monday == 0:
        return value
    return value + timedelta(days=days_until_monday)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _colombian_holidays(year: int) -> set[date]:
    easter = _easter_sunday(year)
    fixed_holidays = {
        date(year, 1, 1),
        date(year, 5, 1),
        date(year, 7, 20),
        date(year, 8, 7),
        date(year, 12, 8),
        date(year, 12, 25),
    }
    emiliani_holidays = {
        _next_monday(date(year, 1, 6)),
        _next_monday(date(year, 3, 19)),
        _next_monday(date(year, 6, 29)),
        _next_monday(date(year, 8, 15)),
        _next_monday(date(year, 10, 12)),
        _next_monday(date(year, 11, 1)),
        _next_monday(date(year, 11, 11)),
    }
    easter_related_holidays = {
        easter - timedelta(days=3),
        easter - timedelta(days=2),
        _next_monday(easter + timedelta(days=43)),
        _next_monday(easter + timedelta(days=64)),
        _next_monday(easter + timedelta(days=71)),
    }
    return fixed_holidays | emiliani_holidays | easter_related_holidays


def _is_colombian_business_day(value: date) -> bool:
    if value.weekday() >= 5:
        return False
    return value not in _colombian_holidays(value.year)


def _normalize_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_timestamp_to_bogota(raw_value: Any) -> str:
    normalized = str(raw_value).strip()
    if not normalized:
        raise ValueError("Snapshot captured_at is required.")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BOGOTA_TIMEZONE)
    return parsed.astimezone(BOGOTA_TIMEZONE).isoformat()


def _parse_iso_date(raw_value: str) -> date:
    return date.fromisoformat(str(raw_value).strip())


def _now_bogota() -> datetime:
    return datetime.now(BOGOTA_TIMEZONE)


def _default_end_date(now_bogota: datetime) -> date:
    if now_bogota.timetz().replace(tzinfo=None) >= MARKET_CLOSE_TIME:
        return now_bogota.date()
    return now_bogota.date() - timedelta(days=1)


def _iter_dates(start_date: date, end_date: date) -> list[date]:
    total_days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(total_days + 1)]


def _scan_existing_daily_closings() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {
        "ProjectionExpression": "symbol, trading_date",
    }
    while True:
        response = DAILY_CLOSING_SNAPSHOTS_TABLE.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _discover_earliest_snapshot_date() -> date | None:
    earliest: date | None = None
    scan_kwargs: dict[str, Any] = {
        "ProjectionExpression": "captured_date",
    }
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.scan(**scan_kwargs)
        for item in response.get("Items", []):
            raw_date = str(item.get("captured_date") or "").strip()
            if not raw_date:
                continue
            parsed_date = _parse_iso_date(raw_date)
            if earliest is None or parsed_date < earliest:
                earliest = parsed_date
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return earliest


def _resolve_start_date(
    requested_from: str | None,
    existing_items: list[dict[str, Any]],
) -> date | None:
    if requested_from:
        return _parse_iso_date(requested_from)

    if existing_items:
        return min(_parse_iso_date(item["trading_date"]) for item in existing_items)

    return _discover_earliest_snapshot_date()


def _group_existing_symbols_by_date(
    existing_items: list[dict[str, Any]],
    *,
    start_date: date,
    end_date: date,
) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for item in existing_items:
        trading_date = str(item.get("trading_date") or "").strip()
        symbol = str(item.get("symbol") or "").strip().upper()
        if not trading_date or not symbol:
            continue
        parsed_date = _parse_iso_date(trading_date)
        if parsed_date < start_date or parsed_date > end_date:
            continue
        grouped.setdefault(trading_date, set()).add(symbol)
    return grouped


def _load_snapshots_for_trading_date(trading_date: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": "captured-date-index",
        "KeyConditionExpression": Key("captured_date").eq(trading_date),
    }
    while True:
        response = CURRENT_SNAPSHOTS_TABLE.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break
        query_kwargs["ExclusiveStartKey"] = last_evaluated_key
    return items


def _select_latest_snapshot_per_symbol(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        symbol = str(snapshot.get("symbol") or "").strip().upper()
        captured_at = str(snapshot.get("captured_at") or "").strip()
        if not symbol or not captured_at:
            continue
        current_latest = latest_by_symbol.get(symbol)
        if current_latest is None or captured_at > str(current_latest.get("captured_at") or ""):
            latest_by_symbol[symbol] = snapshot
    return latest_by_symbol


def _build_daily_closing_item(
    trading_date: str,
    snapshot: dict[str, Any],
    *,
    stored_at: datetime,
) -> dict[str, Any]:
    symbol = str(snapshot["symbol"]).strip().upper()
    return {
        "symbol": symbol,
        "trading_date": trading_date,
        "record_type": "daily_closing_snapshot",
        "asset_name": str(snapshot.get("asset_name") or ""),
        "currency": str(snapshot.get("currency") or "COP"),
        "timezone": DEFAULT_TIMEZONE_NAME,
        "source_captured_at": _normalize_timestamp_to_bogota(snapshot["captured_at"]),
        "source_snapshot_checksum": str(snapshot.get("snapshot_checksum") or "").strip(),
        "stored_at": stored_at.isoformat(),
        "last_price": _normalize_decimal(snapshot.get("last_price")),
        "daily_change_amount": _normalize_decimal(snapshot.get("daily_change_amount")),
        "daily_change_percent": _normalize_decimal(snapshot.get("daily_change_percent")),
        "previous_close": _normalize_decimal(snapshot.get("previous_close")),
        "best_bid_price": _normalize_decimal(snapshot.get("best_bid_price")),
        "best_ask_price": _normalize_decimal(snapshot.get("best_ask_price")),
        "high_price": _normalize_decimal(snapshot.get("high_price")),
        "low_price": _normalize_decimal(snapshot.get("low_price")),
        "traded_value": _normalize_decimal(snapshot.get("traded_value")),
        "traded_volume": _normalize_decimal(snapshot.get("traded_volume")),
    }


def _store_daily_closing_item(item: dict[str, Any]) -> bool:
    try:
        DAILY_CLOSING_SNAPSHOTS_TABLE.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(symbol) AND attribute_not_exists(trading_date)",
        )
        return True
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return False
        raise


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    apply_changes = bool(event.get("apply", True))
    requested_from = event.get("trading_date_from")
    requested_to = event.get("trading_date_to")

    now_bogota = _now_bogota()
    end_date = _parse_iso_date(requested_to) if requested_to else _default_end_date(now_bogota)
    existing_items = _scan_existing_daily_closings()
    start_date = _resolve_start_date(requested_from, existing_items)

    if start_date is None or start_date > end_date:
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "apply": apply_changes,
                    "trading_date_from": None if start_date is None else start_date.isoformat(),
                    "trading_date_to": end_date.isoformat(),
                    "dates_considered": 0,
                    "dates_with_snapshots": 0,
                    "dates_without_snapshots": 0,
                    "missing_symbols_found": 0,
                    "records_written": 0,
                    "records_skipped_existing": 0,
                }
            ),
        }

    existing_symbols_by_date = _group_existing_symbols_by_date(
        existing_items,
        start_date=start_date,
        end_date=end_date,
    )

    dates_considered = 0
    dates_with_snapshots = 0
    dates_without_snapshots = 0
    missing_symbols_found = 0
    records_written = 0
    records_skipped_existing = 0

    for target_date in _iter_dates(start_date, end_date):
        dates_considered += 1
        if not _is_colombian_business_day(target_date):
            dates_without_snapshots += 1
            continue
        trading_date = target_date.isoformat()
        snapshots = _load_snapshots_for_trading_date(trading_date)
        if not snapshots:
            dates_without_snapshots += 1
            continue

        dates_with_snapshots += 1
        latest_by_symbol = _select_latest_snapshot_per_symbol(snapshots)
        existing_symbols = existing_symbols_by_date.get(trading_date, set())
        stored_at = _now_bogota()

        for symbol, snapshot in sorted(latest_by_symbol.items()):
            if symbol in existing_symbols:
                records_skipped_existing += 1
                continue

            missing_symbols_found += 1
            if not apply_changes:
                continue

            stored = _store_daily_closing_item(
                _build_daily_closing_item(trading_date, snapshot, stored_at=stored_at)
            )
            if stored:
                records_written += 1
            else:
                records_skipped_existing += 1

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "apply": apply_changes,
                "timezone": DEFAULT_TIMEZONE_NAME,
                "trading_date_from": start_date.isoformat(),
                "trading_date_to": end_date.isoformat(),
                "dates_considered": dates_considered,
                "dates_with_snapshots": dates_with_snapshots,
                "dates_without_snapshots": dates_without_snapshots,
                "missing_symbols_found": missing_symbols_found,
                "records_written": records_written,
                "records_skipped_existing": records_skipped_existing,
            }
        ),
    }
