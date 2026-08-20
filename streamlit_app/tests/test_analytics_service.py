from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from trii_ingestion.services.analytics import (
    build_analytics_summary,
    build_depth_history_rows,
    build_z_score_context,
    compute_latest_z_score,
    extract_symbols,
    filter_records,
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


def test_extract_symbols_deduplicates_and_sorts_alphabetically() -> None:
    assert extract_symbols(_sample_records()) == ["BOGOTA", "PFAVAL"]


def test_filter_records_applies_symbol_and_time_window() -> None:
    filtered = filter_records(
        _sample_records(),
        symbol="PFAVAL",
        window_label="6h",
        current_time=datetime(2026, 8, 17, 21, 0, tzinfo=BOGOTA),
    )

    assert [record["captured_at"] for record in filtered] == ["2026-08-17T20:30:00-05:00"]


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
        "from_timestamp": "17-08-2026 14:00",
        "to_timestamp": "17-08-2026 20:30",
    }


def test_build_analytics_summary_falls_back_to_selected_window_when_records_are_missing_timestamps() -> None:
    summary = build_analytics_summary(
        [{"symbol": "PFAVAL"}],
        window_label="6h",
        current_time=datetime(2026, 8, 17, 21, 14, tzinfo=BOGOTA),
    )

    assert summary == {
        "record_count": 1,
        "from_timestamp": "17-08-2026 15:14",
        "to_timestamp": "17-08-2026 21:14",
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


def test_build_depth_history_rows_supports_json_string_levels() -> None:
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

    assert len(rows) == 2
    assert rows[0]["level"] == 1
    assert rows[0]["price"] == 822.0
    assert rows[1]["quantity"] == 40000.0


def test_build_depth_history_rows_supports_dynamo_json_levels() -> None:
    rows = build_depth_history_rows(
        [
            {
                "symbol": "PFAVAL",
                "captured_at": "2026-08-17T20:30:00-05:00",
                "bid_levels": {
                    "L": [
                        {
                            "M": {
                                "level": {"N": "1"},
                                "quantity": {"N": "33636"},
                                "price": {"N": "822"},
                            }
                        }
                    ]
                },
                "ask_levels": {
                    "L": [
                        {
                            "M": {
                                "level": {"N": "1"},
                                "quantity": {"N": "40000"},
                                "price": {"N": "855"},
                            }
                        }
                    ]
                },
            }
        ]
    )

    assert len(rows) == 2
    assert rows[0]["price"] == 822.0
    assert rows[1]["price"] == 855.0


def test_compute_latest_z_score_uses_available_window_series() -> None:
    records = [
        {"obi_l1": 0.8},
        {"obi_l1": 0.4},
        {"obi_l1": 0.0},
        {"obi_l1": -0.4},
    ]

    z_score = compute_latest_z_score(records, "obi_l1")

    assert z_score is not None
    assert round(z_score, 2) == 1.34


def test_compute_latest_z_score_returns_none_when_sigma_is_zero() -> None:
    records = [
        {"obi_top_5": 0.2},
        {"obi_top_5": 0.2},
    ]

    assert compute_latest_z_score(records, "obi_top_5") is None


def test_build_z_score_context_marks_strong_and_anomalous_intraday_samples() -> None:
    records = [
        {
            "captured_at": f"2026-08-18T08:{minute:02d}:00-05:00",
            "obi_l1": 4.0 if minute == 59 else 0.0,
        }
        for minute in range(30, 60)
    ]

    context = build_z_score_context(
        records[::-1],
        "obi_l1",
        current_time=datetime(2026, 8, 18, 8, 59, tzinfo=BOGOTA),
    )

    assert context["sample_label"] == "Representative"
    assert context["sample_size"] == 30
    assert context["anomaly_label"] == "Anomaly"
    assert context["z_score"] is not None
    assert context["coverage_ratio"] == 1.0


def test_build_z_score_context_marks_thin_and_normal_samples_when_window_is_sparse() -> None:
    records = [
        {
            "captured_at": timestamp,
            "obi_top_5": value,
        }
        for timestamp, value in [
            ("2026-08-18T08:30:00-05:00", 0.20),
            ("2026-08-18T08:40:00-05:00", 0.10),
            ("2026-08-18T08:50:00-05:00", 0.15),
            ("2026-08-18T09:00:00-05:00", 0.05),
        ]
    ]

    context = build_z_score_context(
        records[::-1],
        "obi_top_5",
        current_time=datetime(2026, 8, 18, 9, 0, tzinfo=BOGOTA),
    )

    assert context["sample_label"] == "Thin"
    assert context["sample_size"] == 4
    assert context["anomaly_label"] == "Normal"
    assert context["z_score"] is not None


def test_build_z_score_context_hides_signal_when_sigma_is_zero() -> None:
    records = [
        {
            "captured_at": timestamp,
            "obi_top_5": 0.46,
        }
        for timestamp in [
            "2026-08-19T12:41:00-05:00",
            "2026-08-19T12:42:00-05:00",
            "2026-08-19T12:43:00-05:00",
            "2026-08-19T12:44:00-05:00",
            "2026-08-19T12:45:00-05:00",
            "2026-08-19T12:46:00-05:00",
            "2026-08-19T12:47:00-05:00",
        ]
    ]

    context = build_z_score_context(
        records[::-1],
        "obi_top_5",
        current_time=datetime(2026, 8, 19, 12, 47, tzinfo=BOGOTA),
    )

    assert context["sample_label"] == "Representative"
    assert context["sample_size"] == 7
    assert context["anomaly_label"] is None
    assert context["z_score"] is None
