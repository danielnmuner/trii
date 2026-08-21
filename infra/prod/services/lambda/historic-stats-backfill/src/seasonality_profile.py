from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

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


def _parse_timestamp(raw_value: str) -> datetime:
    normalized = raw_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


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


def _finalize_symbol_profile(
    symbol: str,
    profile: dict[str, Any],
    updated_at: datetime,
) -> dict[str, Any]:
    weekly_profile = profile["weekly_profile"]
    for weekday_payload in weekly_profile.values():
        for hour_payload in weekday_payload["hours"].values():
            accumulated_volume = to_decimal(hour_payload["accumulated_volume"])
            accumulated_value = to_decimal(hour_payload["accumulated_value"])
            if (
                accumulated_volume is not None
                and accumulated_value is not None
                and accumulated_volume > 0
            ):
                hour_payload["bucket_vwap"] = accumulated_value / accumulated_volume

    return {
        "pk": symbol,
        "sk": SEASONALITY_PROFILE_KEY,
        "symbol": symbol,
        "record_type": SEASONALITY_PROFILE_KEY,
        "bucket_granularity_minutes": SEASONALITY_BUCKET_GRANULARITY_MINUTES,
        "timezone": BOGOTA_TIMEZONE_NAME,
        "total_days_processed": profile["total_days_processed"],
        "total_snapshots_processed": profile["total_snapshots_processed"],
        "last_source_captured_at": profile["last_source_captured_at"],
        "last_updated_at": updated_at.isoformat(),
        "stats_scope": SEASONALITY_PROFILE_SCOPE,
        "stats_version": 1,
        "weekly_profile": weekly_profile,
    }


def build_seasonality_profile_items_from_snapshots(
    snapshots: list[dict[str, Any]],
    updated_at: datetime,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not snapshots:
        return {}

    ordered_snapshots = sorted(
        snapshots,
        key=lambda item: (str(item.get("symbol") or "").strip().upper(), str(item.get("captured_at") or "").strip()),
    )

    profiles: dict[str, dict[str, Any]] = {}
    valid_snapshot_counts: dict[str, int] = defaultdict(int)
    previous_snapshot_by_symbol: dict[str, dict[str, Any]] = {}

    for snapshot in ordered_snapshots:
        symbol = str(snapshot.get("symbol") or "").strip().upper()
        captured_at = str(snapshot.get("captured_at") or "").strip()
        snapshot_checksum = str(snapshot.get("snapshot_checksum") or "").strip()
        if not symbol or not captured_at or not snapshot_checksum:
            continue

        valid_snapshot_counts[symbol] += 1
        previous_snapshot = previous_snapshot_by_symbol.get(symbol)
        previous_snapshot_by_symbol[symbol] = snapshot

        if previous_snapshot is None:
            continue

        if _get_trading_date(previous_snapshot) != _get_trading_date(snapshot):
            continue

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
            continue

        delta_volume = current_volume - previous_volume
        delta_value = current_value - previous_value
        if delta_volume <= 0 or delta_value <= 0:
            continue

        previous_timestamp = _parse_timestamp(str(previous_snapshot["captured_at"]))
        timestamp = _parse_timestamp(captured_at)
        delta_seconds = Decimal(str((timestamp - previous_timestamp).total_seconds()))
        if delta_seconds <= 0:
            continue

        trading_date = _get_trading_date(snapshot)
        bucket_key = _get_bucket_key(timestamp)
        profile = profiles.setdefault(
            symbol,
            {
                "total_days_processed": 0,
                "total_snapshots_processed": 0,
                "last_source_captured_at": captured_at,
                "daily_buckets": {},
                "weekly_profile": {},
            },
        )
        profile["last_source_captured_at"] = captured_at
        daily_bucket = profile["daily_buckets"].setdefault(
            trading_date,
            {
                "weekday": str(timestamp.isoweekday()),
                "total_day_volume": Decimal("0"),
                "total_day_value": Decimal("0"),
                "hours": {},
            },
        )
        hour_bucket = daily_bucket["hours"].setdefault(
            bucket_key,
            {
                "bucket_volume": Decimal("0"),
                "bucket_value": Decimal("0"),
                "delta_samples": 0,
            },
        )

        daily_bucket["total_day_volume"] += delta_volume
        daily_bucket["total_day_value"] += delta_value
        hour_bucket["bucket_volume"] += delta_volume
        hour_bucket["bucket_value"] += delta_value
        hour_bucket["delta_samples"] += 1
        hour_bucket.setdefault("rate_samples", []).append(
            {
                "volume_rate": delta_volume / delta_seconds,
                "value_rate": delta_value / delta_seconds,
            }
        )

    rebuilt_items: dict[tuple[str, str], dict[str, Any]] = {}
    for symbol, profile in profiles.items():
        profile["total_snapshots_processed"] = valid_snapshot_counts.get(symbol, 0)
        for day_payload in profile.pop("daily_buckets").values():
            total_day_volume = to_decimal(day_payload.get("total_day_volume"))
            total_day_value = to_decimal(day_payload.get("total_day_value"))
            weekday_key = str(day_payload.get("weekday") or "")
            if not weekday_key or total_day_volume is None or total_day_volume <= 0:
                continue

            weekly_entry = profile["weekly_profile"].setdefault(weekday_key, _build_weekday_entry())
            weekly_entry["weekday_label"] = WEEKDAY_LABELS.get(weekday_key, "unknown")
            weekly_entry["days_processed"] += 1
            weekly_entry["accumulated_day_volume"] += total_day_volume
            if total_day_value is not None:
                weekly_entry["accumulated_day_value"] += total_day_value
            profile["total_days_processed"] += 1

            for bucket_key, bucket_payload in day_payload["hours"].items():
                bucket_volume = to_decimal(bucket_payload.get("bucket_volume"))
                bucket_value = to_decimal(bucket_payload.get("bucket_value"))
                if bucket_volume is None or bucket_value is None or bucket_volume <= 0:
                    continue

                hour_entry = weekly_entry["hours"].setdefault(bucket_key, _build_hour_entry())
                hour_entry["accumulated_volume"] += bucket_volume
                hour_entry["accumulated_value"] += bucket_value
                hour_entry["delta_samples"] += int(bucket_payload.get("delta_samples", 0) or 0)
                hour_entry["volume_share_stats"] = _update_welford_state(
                    hour_entry.get("volume_share_stats"),
                    bucket_volume / total_day_volume,
                )
                hour_entry["vwap_stats"] = _update_welford_state(
                    hour_entry.get("vwap_stats"),
                    bucket_value / bucket_volume,
                )
                for rate_sample in bucket_payload.get("rate_samples", []):
                    volume_rate = to_decimal(rate_sample.get("volume_rate"))
                    value_rate = to_decimal(rate_sample.get("value_rate"))
                    if volume_rate is not None:
                        hour_entry["volume_rate_stats"] = _update_welford_state(
                            hour_entry.get("volume_rate_stats"),
                            volume_rate,
                        )
                    if value_rate is not None:
                        hour_entry["value_rate_stats"] = _update_welford_state(
                            hour_entry.get("value_rate_stats"),
                            value_rate,
                        )

        if profile["total_days_processed"] == 0:
            continue
        rebuilt_items[(symbol, SEASONALITY_PROFILE_KEY)] = _finalize_symbol_profile(
            symbol,
            profile,
            updated_at,
        )

    return rebuilt_items
