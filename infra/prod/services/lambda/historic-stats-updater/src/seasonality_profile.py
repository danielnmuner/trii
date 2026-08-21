from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any

from data_quality import market_session_bounds, parse_captured_at
from snapshot_metrics import to_decimal


SEASONALITY_PROFILE_KEY = "seasonality_profile"
SEASONALITY_PROFILE_SCOPE = "weekly_intraday_seasonality"
SEASONALITY_BUCKET_GRANULARITY_MINUTES = 30
BOGOTA_TIMEZONE_NAME = "America/Bogota"
WEEKDAY_LABELS = {
    "1": "monday",
    "2": "tuesday",
    "3": "wednesday",
    "4": "thursday",
    "5": "friday",
    "6": "saturday",
    "7": "sunday",
}


def _empty_welford_state() -> dict[str, Any]:
    return {
        "sample_count": 0,
        "mu": Decimal("0"),
        "m2": Decimal("0"),
        "variance": Decimal("0"),
        "sigma": Decimal("0"),
    }


def _update_welford_state(state: dict[str, Any] | None, value: Decimal) -> dict[str, Any]:
    previous = _empty_welford_state() if state is None else state
    previous_count = int(previous.get("sample_count", 0) or 0)
    previous_mu = to_decimal(previous.get("mu")) or Decimal("0")
    previous_m2 = to_decimal(previous.get("m2")) or Decimal("0")

    sample_count = previous_count + 1
    delta = value - previous_mu
    mu = previous_mu + (delta / Decimal(sample_count))
    delta_2 = value - mu
    m2 = previous_m2 + (delta * delta_2)
    variance = Decimal("0")
    sigma = Decimal("0")
    if sample_count > 1:
        variance = m2 / Decimal(sample_count - 1)
        sigma = variance.sqrt()

    return {
        "sample_count": sample_count,
        "mu": mu,
        "m2": m2,
        "variance": variance,
        "sigma": sigma,
    }


def _build_weekday_entry() -> dict[str, Any]:
    return {
        "weekday_label": "",
        "days_processed": 0,
        "accumulated_day_volume": Decimal("0"),
        "accumulated_day_value": Decimal("0"),
        "hours": {},
    }


def _build_hour_entry() -> dict[str, Any]:
    return {
        "accumulated_volume": Decimal("0"),
        "accumulated_value": Decimal("0"),
        "delta_samples": 0,
        "bucket_vwap": None,
        "volume_share_stats": _empty_welford_state(),
        "vwap_stats": _empty_welford_state(),
        "volume_rate_stats": _empty_welford_state(),
        "value_rate_stats": _empty_welford_state(),
    }


def _get_trading_date(snapshot: dict[str, Any]) -> str:
    captured_date = str(snapshot.get("captured_date") or "").strip()
    if captured_date:
        return captured_date
    return str(snapshot["captured_at"]).strip()[:10]


def _get_bucket_key(timestamp: datetime) -> str:
    bucket_minute = (
        timestamp.minute // SEASONALITY_BUCKET_GRANULARITY_MINUTES
    ) * SEASONALITY_BUCKET_GRANULARITY_MINUTES
    return f"{timestamp.hour:02d}:{bucket_minute:02d}"


def _build_pending_day(
    *,
    trading_date: str,
    weekday_key: str,
    captured_at: str,
) -> dict[str, Any]:
    return {
        "trading_date": trading_date,
        "weekday": weekday_key,
        "last_source_captured_at": captured_at,
        "total_day_volume": Decimal("0"),
        "total_day_value": Decimal("0"),
        "hours": {},
    }


def _ensure_profile_base(
    previous_item: dict[str, Any] | None,
    *,
    symbol: str,
    updated_at: datetime,
) -> dict[str, Any]:
    if previous_item is None:
        return {
            "pk": symbol,
            "sk": SEASONALITY_PROFILE_KEY,
            "symbol": symbol,
            "record_type": SEASONALITY_PROFILE_KEY,
            "bucket_granularity_minutes": SEASONALITY_BUCKET_GRANULARITY_MINUTES,
            "timezone": BOGOTA_TIMEZONE_NAME,
            "total_days_processed": 0,
            "total_snapshots_processed": 0,
            "last_source_captured_at": None,
            "last_updated_at": updated_at.isoformat(),
            "stats_scope": SEASONALITY_PROFILE_SCOPE,
            "stats_version": 1,
            "weekly_profile": {},
        }

    profile = deepcopy(previous_item)
    profile["last_updated_at"] = updated_at.isoformat()
    profile["stats_version"] = int(previous_item.get("stats_version", 0) or 0) + 1
    profile.setdefault("weekly_profile", {})
    return profile


def _update_accumulated_bucket(
    profile: dict[str, Any],
    *,
    weekday_key: str,
    bucket_key: str,
    delta_volume: Decimal,
    delta_value: Decimal,
    delta_seconds: Decimal,
) -> None:
    weekly_entry = profile["weekly_profile"].setdefault(weekday_key, _build_weekday_entry())
    weekly_entry["weekday_label"] = WEEKDAY_LABELS.get(weekday_key, "unknown")
    hour_entry = weekly_entry["hours"].setdefault(bucket_key, _build_hour_entry())
    hour_entry["accumulated_volume"] += delta_volume
    hour_entry["accumulated_value"] += delta_value
    hour_entry["delta_samples"] += 1
    if hour_entry["accumulated_volume"] > 0:
        hour_entry["bucket_vwap"] = (
            hour_entry["accumulated_value"] / hour_entry["accumulated_volume"]
        )
    hour_entry["volume_rate_stats"] = _update_welford_state(
        hour_entry.get("volume_rate_stats"),
        delta_volume / delta_seconds,
    )
    hour_entry["value_rate_stats"] = _update_welford_state(
        hour_entry.get("value_rate_stats"),
        delta_value / delta_seconds,
    )


def _accumulate_pending_day(
    profile: dict[str, Any],
    *,
    trading_date: str,
    weekday_key: str,
    bucket_key: str,
    captured_at: str,
    delta_volume: Decimal,
    delta_value: Decimal,
) -> None:
    pending_day = profile.get("pending_day")
    if pending_day is None or str(pending_day.get("trading_date")) != trading_date:
        pending_day = _build_pending_day(
            trading_date=trading_date,
            weekday_key=weekday_key,
            captured_at=captured_at,
        )
        profile["pending_day"] = pending_day

    pending_day["last_source_captured_at"] = captured_at
    pending_day["total_day_volume"] += delta_volume
    pending_day["total_day_value"] += delta_value
    pending_hour = pending_day["hours"].setdefault(
        bucket_key,
        {
            "bucket_volume": Decimal("0"),
            "bucket_value": Decimal("0"),
        },
    )
    pending_hour["bucket_volume"] += delta_volume
    pending_hour["bucket_value"] += delta_value


def _finalize_pending_day(profile: dict[str, Any]) -> bool:
    pending_day = profile.get("pending_day")
    if pending_day is None:
        return False

    total_day_volume = to_decimal(pending_day.get("total_day_volume"))
    total_day_value = to_decimal(pending_day.get("total_day_value"))
    weekday_key = str(pending_day.get("weekday") or "")
    if not weekday_key or total_day_volume is None or total_day_volume <= 0:
        profile.pop("pending_day", None)
        return False

    weekly_entry = profile["weekly_profile"].setdefault(weekday_key, _build_weekday_entry())
    weekly_entry["weekday_label"] = WEEKDAY_LABELS.get(weekday_key, "unknown")
    weekly_entry["days_processed"] += 1
    weekly_entry["accumulated_day_volume"] += total_day_volume
    if total_day_value is not None:
        weekly_entry["accumulated_day_value"] += total_day_value
    profile["total_days_processed"] = int(profile.get("total_days_processed", 0) or 0) + 1

    for bucket_key, bucket_payload in pending_day.get("hours", {}).items():
        bucket_volume = to_decimal(bucket_payload.get("bucket_volume"))
        bucket_value = to_decimal(bucket_payload.get("bucket_value"))
        if bucket_volume is None or bucket_value is None or bucket_volume <= 0:
            continue
        hour_entry = weekly_entry["hours"].setdefault(bucket_key, _build_hour_entry())
        hour_entry["volume_share_stats"] = _update_welford_state(
            hour_entry.get("volume_share_stats"),
            bucket_volume / total_day_volume,
        )
        hour_entry["vwap_stats"] = _update_welford_state(
            hour_entry.get("vwap_stats"),
            bucket_value / bucket_volume,
        )

    profile.pop("pending_day", None)
    return True


def build_seasonality_profile_item(
    previous_item: dict[str, Any] | None,
    *,
    snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    updated_at: datetime,
) -> dict[str, Any] | None:
    symbol = str(snapshot.get("symbol") or "").strip().upper()
    captured_at = str(snapshot.get("captured_at") or "").strip()
    snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
    if not symbol or not captured_at or not snapshot_checksum:
        return None

    profile = _ensure_profile_base(previous_item, symbol=symbol, updated_at=updated_at)
    profile["last_source_captured_at"] = captured_at
    profile["total_snapshots_processed"] = int(profile.get("total_snapshots_processed", 0) or 0) + 1

    current_timestamp = parse_captured_at(captured_at)
    current_trading_date = _get_trading_date(snapshot)

    pending_day = profile.get("pending_day")
    if pending_day is not None and str(pending_day.get("trading_date")) != current_trading_date:
        _finalize_pending_day(profile)

    if previous_snapshot is None:
        return profile

    previous_captured_at = str(previous_snapshot.get("captured_at") or "").strip()
    if not previous_captured_at:
        return profile

    previous_timestamp = parse_captured_at(previous_captured_at)
    if _get_trading_date(previous_snapshot) != current_trading_date:
        return profile

    current_volume = to_decimal(snapshot.get("traded_volume"))
    current_value = to_decimal(snapshot.get("traded_value"))
    previous_volume = to_decimal(previous_snapshot.get("traded_volume"))
    previous_value = to_decimal(previous_snapshot.get("traded_value"))
    if (
        current_volume is None
        or current_value is None
        or previous_volume is None
        or previous_value is None
    ):
        return profile

    delta_volume = current_volume - previous_volume
    delta_value = current_value - previous_value
    if delta_volume <= 0 or delta_value <= 0:
        return profile

    delta_seconds = Decimal(str((current_timestamp - previous_timestamp).total_seconds()))
    if delta_seconds <= 0:
        return profile

    weekday_key = str(current_timestamp.isoweekday())
    bucket_key = _get_bucket_key(current_timestamp)
    _update_accumulated_bucket(
        profile,
        weekday_key=weekday_key,
        bucket_key=bucket_key,
        delta_volume=delta_volume,
        delta_value=delta_value,
        delta_seconds=delta_seconds,
    )
    _accumulate_pending_day(
        profile,
        trading_date=current_trading_date,
        weekday_key=weekday_key,
        bucket_key=bucket_key,
        captured_at=captured_at,
        delta_volume=delta_volume,
        delta_value=delta_value,
    )

    _session_start, session_end = market_session_bounds(current_timestamp.date())
    if current_timestamp >= session_end:
        _finalize_pending_day(profile)

    return profile
