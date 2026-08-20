from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from trii_ingestion.services.analytics import (
    build_analytics_summary,
    build_depth_history_rows,
    build_historic_z_score_context,
    format_timestamp_label,
    get_time_window_labels,
)


BOGOTA = ZoneInfo("America/Bogota")


def _sample_records() -> list[dict]:
    return [
        {
            "symbol": "PFAVAL",
            "captured_at": "2026-08-17T20:30:00-05:00",
            "bid_levels": [
                {"level": 1, "quantity": 33636, "price": 822},
                {"level": 2, "quantity": 142000, "price": 820},
                {"level": 3, "quantity": 10140, "price": 803},
                {"level": 4, "quantity": 20000, "price": 794},
                {"level": 5, "quantity": 96896, "price": 791},
            ],
            "ask_levels": [
                {"level": 1, "quantity": 40000, "price": 855},
                {"level": 2, "quantity": 72631, "price": 860},
                {"level": 3, "quantity": 2630, "price": 863},
                {"level": 4, "quantity": 33100, "price": 864},
                {"level": 5, "quantity": 36439, "price": 865},
            ],
        },
        {
            "symbol": "BOGOTA",
            "captured_at": "2026-08-17T16:30:00-05:00",
            "bid_levels": [],
            "ask_levels": [],
        },
        {
            "symbol": "PFAVAL",
            "captured_at": "2026-08-17T14:00:00-05:00",
            "bid_levels": [],
            "ask_levels": [],
        },
    ]


def test_time_window_labels_include_expected_default_options() -> None:
    assert get_time_window_labels() == ["1h", "3h", "6h", "1d", "3d", "7d"]


def test_format_timestamp_label_supports_date_only_values() -> None:
    assert format_timestamp_label("2026-08-11") == "11-08-2026 00:00"


def test_format_timestamp_label_supports_iso_datetimes() -> None:
    assert format_timestamp_label("2026-08-17T21:14:31.456064-05:00") == "17-08-2026 21:14"


def test_build_analytics_summary_uses_real_record_bounds_when_available() -> None:
    summary = build_analytics_summary(
        [
            {"symbol": "PFAVAL", "captured_at": "2026-08-17T20:30:00-05:00"},
            {"symbol": "PFAVAL", "captured_at": "2026-08-17T14:00:00-05:00"},
        ],
        window_label="6h",
        current_time=datetime(2026, 8, 17, 21, 14, tzinfo=BOGOTA),
    )

    assert summary == {
        "record_count": 2,
        "from_timestamp": "17-08-2026 14:00:00",
        "to_timestamp": "17-08-2026 20:30:00",
    }


def test_build_analytics_summary_falls_back_to_selected_window_when_records_are_missing_timestamps() -> None:
    summary = build_analytics_summary(
        [{"symbol": "PFAVAL"}],
        window_label="6h",
        current_time=datetime(2026, 8, 17, 21, 14, tzinfo=BOGOTA),
    )

    assert summary == {
        "record_count": 1,
        "from_timestamp": "17-08-2026 15:14:00",
        "to_timestamp": "17-08-2026 21:14:00",
    }


def test_build_depth_history_rows_extracts_five_levels_per_side() -> None:
    rows = build_depth_history_rows(_sample_records()[:1])

    assert len(rows) == 10
    assert rows[0] == {
        "captured_at": "2026-08-17T20:30:00-05:00",
        "side": "Bid",
        "level": 1,
        "level_label": "Nivel 1",
        "price": 822.0,
        "quantity": 33636.0,
    }
    assert rows[-1] == {
        "captured_at": "2026-08-17T20:30:00-05:00",
        "side": "Ask",
        "level": 5,
        "level_label": "Nivel 5",
        "price": 865.0,
        "quantity": 36439.0,
    }


def test_build_depth_history_rows_ignores_non_list_depth_payloads() -> None:
    rows = build_depth_history_rows(
        [
            {
                "symbol": "PFAVAL",
                "captured_at": "2026-08-17T20:30:00-05:00",
                "bid_levels": '[{"level":1,"quantity":33636,"price":822}]',
                "ask_levels": '[{"level":1,"quantity":40000,"price":855}]',
            }
        ]
    )

    assert rows == []


def test_build_historic_z_score_context_uses_stat_item_values() -> None:
    context = build_historic_z_score_context(
        {
            "latest_value": 0.84,
            "mean": 0.10,
            "stddev": 0.20,
            "sample_count": 24,
        }
    )

    assert context["sample_count"] == 24
    assert context["signal_label"] == "Anomaly"
    assert context["z_score"] is not None
    assert round(float(context["z_score"]), 2) == 3.70


def test_build_historic_z_score_context_keeps_sample_count_without_signal_when_sigma_missing() -> None:
    context = build_historic_z_score_context(
        {
            "latest_value": 0.24,
            "mean": 0.24,
            "stddev": 0,
            "sample_count": 8,
        }
    )

    assert context["sample_count"] == 8
    assert context["signal_label"] is None
    assert context["z_score"] is None
