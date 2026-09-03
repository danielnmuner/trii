from __future__ import annotations

import json
import os
from datetime import datetime, time
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer
from zoneinfo import ZoneInfo


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")
SAMPLING_SECONDS = 30
SAMPLES_PER_SEGMENT = 156
SESSION_START_TIME = time(hour=8, minute=30)
SESSION_SAMPLE_COUNT = 780
STREAM_TTL_SECONDS = 24 * 60 * 60

DYNAMODB_RESOURCE = boto3.resource("dynamodb")
DESERIALIZER = TypeDeserializer()
SESSION_VECTORS_TABLE = DYNAMODB_RESOURCE.Table(os.environ["SESSION_VECTORS_TABLE"])


def _deserialize_item(raw_item: dict[str, Any]) -> dict[str, Any]:
    return {key: DESERIALIZER.deserialize(value) for key, value in raw_item.items()}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _safe_divide(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _parse_captured_at(raw_value: str) -> datetime:
    normalized = raw_value.strip().replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    return timestamp.astimezone(BOGOTA_TIMEZONE)


def _manifest_record_type(trading_date: str) -> str:
    return f"session_vector#{trading_date}"


def _segment_record_type(trading_date: str, segment_index: int) -> str:
    return f"{_manifest_record_type(trading_date)}#segment#{segment_index:03d}"


def _session_start(trading_date: str) -> datetime:
    base_date = datetime.fromisoformat(f"{trading_date}T00:00:00-05:00").date()
    return datetime.combine(base_date, SESSION_START_TIME, tzinfo=BOGOTA_TIMEZONE)


def _sample_index(captured_at: datetime) -> int | None:
    session_start = _session_start(captured_at.date().isoformat())
    delta_seconds = int((captured_at - session_start).total_seconds())
    if delta_seconds < 0:
        return None
    sample_index = delta_seconds // SAMPLING_SECONDS
    if sample_index < 0 or sample_index >= SESSION_SAMPLE_COUNT:
        return None
    return sample_index


def _ensure_length(values: list[Any], size: int) -> list[Any]:
    if len(values) >= size:
        return values
    return values + [None] * (size - len(values))


def _update_series(series: list[Any], offset: int, value: Decimal | None) -> list[Any]:
    updated = _ensure_length(list(series), offset + 1)
    updated[offset] = value
    return updated


def _load_item(symbol: str, record_type: str) -> dict[str, Any] | None:
    response = SESSION_VECTORS_TABLE.get_item(
        Key={
            "symbol": symbol,
            "record_type": record_type,
        }
    )
    return response.get("Item")


def _build_segment_item(
    existing_item: dict[str, Any] | None,
    *,
    symbol: str,
    trading_date: str,
    segment_index: int,
    sample_index: int,
    captured_at: str,
    microprice: Decimal | None,
    mid_price: Decimal | None,
    last_price: Decimal | None,
    vwap: Decimal | None,
    ttl_seconds: int,
) -> dict[str, Any]:
    record_type = _segment_record_type(trading_date, segment_index)
    segment_start_index = segment_index * SAMPLES_PER_SEGMENT
    offset = sample_index - segment_start_index

    microprice_series = _update_series(list(existing_item.get("microprice_series", [])) if existing_item else [], offset, microprice)
    mid_price_series = _update_series(list(existing_item.get("mid_price_series", [])) if existing_item else [], offset, mid_price)
    last_price_series = _update_series(list(existing_item.get("last_price_series", [])) if existing_item else [], offset, last_price)
    vwap_series = _update_series(list(existing_item.get("vwap_series", [])) if existing_item else [], offset, vwap)

    existing_from_sample_index = existing_item.get("from_sample_index") if existing_item else None
    existing_to_sample_index = existing_item.get("to_sample_index") if existing_item else None
    existing_from_captured_at = str(existing_item.get("from_captured_at") or "") if existing_item else ""
    existing_to_captured_at = str(existing_item.get("to_captured_at") or "") if existing_item else ""

    captured_timestamp = _parse_captured_at(captured_at)
    return {
        "symbol": symbol,
        "record_type": record_type,
        "trading_date": trading_date,
        "timezone": "America/Bogota",
        "segment_index": segment_index,
        "from_sample_index": sample_index
        if existing_from_sample_index is None
        else min(int(existing_from_sample_index), sample_index),
        "to_sample_index": sample_index
        if existing_to_sample_index is None
        else max(int(existing_to_sample_index), sample_index),
        "from_captured_at": captured_at
        if not existing_from_captured_at or captured_at < existing_from_captured_at
        else existing_from_captured_at,
        "to_captured_at": captured_at
        if not existing_to_captured_at or captured_at > existing_to_captured_at
        else existing_to_captured_at,
        "microprice_series": microprice_series,
        "mid_price_series": mid_price_series,
        "last_price_series": last_price_series,
        "vwap_series": vwap_series,
        "expires_at": int(captured_timestamp.timestamp()) + ttl_seconds,
    }


def _build_manifest_item(
    existing_item: dict[str, Any] | None,
    *,
    symbol: str,
    trading_date: str,
    sample_index: int,
    captured_at: str,
    segment_index: int,
    ttl_seconds: int,
) -> dict[str, Any]:
    existing_latest_sample_index = existing_item.get("latest_sample_index") if existing_item else None
    existing_latest_captured_at = str(existing_item.get("latest_captured_at") or "") if existing_item else ""
    existing_segment_count = int(existing_item.get("segment_count", 0) or 0) if existing_item else 0

    captured_timestamp = _parse_captured_at(captured_at)
    session_start = _session_start(trading_date)
    session_end = session_start.replace(hour=15, minute=0)

    return {
        "symbol": symbol,
        "record_type": _manifest_record_type(trading_date),
        "trading_date": trading_date,
        "timezone": "America/Bogota",
        "sampling_seconds": SAMPLING_SECONDS,
        "session_start": session_start.isoformat(),
        "session_end": session_end.isoformat(),
        "latest_sample_index": sample_index
        if existing_latest_sample_index is None
        else max(int(existing_latest_sample_index), sample_index),
        "latest_captured_at": captured_at
        if not existing_latest_captured_at or captured_at > existing_latest_captured_at
        else existing_latest_captured_at,
        "segment_count": max(existing_segment_count, segment_index + 1),
        "samples_per_segment": SAMPLES_PER_SEGMENT,
        "expires_at": int(captured_timestamp.timestamp()) + ttl_seconds,
    }


def _apply_snapshot(snapshot: dict[str, Any]) -> bool:
    symbol = str(snapshot.get("symbol") or "").strip().upper()
    captured_at_raw = str(snapshot.get("captured_at") or "").strip()
    if not symbol or not captured_at_raw:
        return False

    captured_at = _parse_captured_at(captured_at_raw)
    sample_index = _sample_index(captured_at)
    if sample_index is None:
        return False

    trading_date = captured_at.date().isoformat()
    segment_index = sample_index // SAMPLES_PER_SEGMENT
    manifest_record_type = _manifest_record_type(trading_date)
    segment_record_type = _segment_record_type(trading_date, segment_index)

    traded_value = _to_decimal(snapshot.get("traded_value"))
    traded_volume = _to_decimal(snapshot.get("traded_volume"))

    segment_item = _build_segment_item(
        _load_item(symbol, segment_record_type),
        symbol=symbol,
        trading_date=trading_date,
        segment_index=segment_index,
        sample_index=sample_index,
        captured_at=captured_at.isoformat(),
        microprice=_to_decimal(snapshot.get("microprice")),
        mid_price=_to_decimal(snapshot.get("mid_price")),
        last_price=_to_decimal(snapshot.get("last_price")),
        vwap=_safe_divide(traded_value, traded_volume),
        ttl_seconds=STREAM_TTL_SECONDS,
    )
    manifest_item = _build_manifest_item(
        _load_item(symbol, manifest_record_type),
        symbol=symbol,
        trading_date=trading_date,
        sample_index=sample_index,
        captured_at=captured_at.isoformat(),
        segment_index=segment_index,
        ttl_seconds=STREAM_TTL_SECONDS,
    )

    SESSION_VECTORS_TABLE.put_item(Item=segment_item)
    SESSION_VECTORS_TABLE.put_item(Item=manifest_item)
    return True


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    snapshots = []
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue
        new_image = record.get("dynamodb", {}).get("NewImage")
        if not new_image:
            continue
        snapshots.append(_deserialize_item(new_image))

    snapshots.sort(
        key=lambda item: (
            str(item.get("symbol") or "").strip().upper(),
            str(item.get("captured_at") or "").strip(),
        )
    )

    written_count = 0
    for snapshot in snapshots:
        if _apply_snapshot(snapshot):
            written_count += 1

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "mode": "stream",
                "processed_records": len(snapshots),
                "written_count": written_count,
            }
        ),
    }
