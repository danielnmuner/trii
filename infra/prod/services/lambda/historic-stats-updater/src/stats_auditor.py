from __future__ import annotations

from decimal import Decimal
from typing import Any

from snapshot_metrics import to_decimal


AUDITED_STAT_KEYS = (
    "sample_count",
    "mean",
    "m2",
    "stddev",
    "min_value",
    "max_value",
    "latest_value",
)
DEFAULT_DECIMAL_TOLERANCE = Decimal("0.000000000000000000000001")


def recompute_statistics(values: list[Decimal]) -> dict[str, Decimal | int]:
    if not values:
        raise ValueError("At least one value is required to recompute historic stats.")

    sample_count = len(values)
    mean = sum(values, Decimal("0")) / Decimal(sample_count)

    if sample_count > 1:
        m2 = sum((value - mean) ** 2 for value in values)
        stddev = (m2 / Decimal(sample_count - 1)).sqrt()
    else:
        m2 = Decimal("0")
        stddev = Decimal("0")

    return {
        "sample_count": sample_count,
        "mean": mean,
        "m2": m2,
        "stddev": stddev,
        "min_value": min(values),
        "max_value": max(values),
        "latest_value": values[-1],
    }


def audit_stat_item(
    actual_item: dict[str, Any],
    values: list[Decimal],
    *,
    tolerance: Decimal = DEFAULT_DECIMAL_TOLERANCE,
) -> dict[str, Any]:
    expected = recompute_statistics(values)
    mismatches: list[dict[str, Any]] = []

    for key in AUDITED_STAT_KEYS:
        actual_value = actual_item.get(key)
        expected_value = expected[key]

        if key == "sample_count":
            normalized_actual = int(actual_value or 0)
            if normalized_actual != expected_value:
                mismatches.append(
                    {
                        "field": key,
                        "expected": expected_value,
                        "actual": normalized_actual,
                    }
                )
            continue

        normalized_actual = to_decimal(actual_value)
        if normalized_actual is None or abs(normalized_actual - expected_value) > tolerance:
            mismatches.append(
                {
                    "field": key,
                    "expected": str(expected_value),
                    "actual": None if normalized_actual is None else str(normalized_actual),
                }
            )

    return {
        "ok": not mismatches,
        "expected": {
            key: (value if isinstance(value, int) else str(value))
            for key, value in expected.items()
        },
        "mismatches": mismatches,
    }
