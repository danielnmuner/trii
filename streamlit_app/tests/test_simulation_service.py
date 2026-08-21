from __future__ import annotations

from datetime import timedelta

from trii_ingestion.services.analytics import now_in_bogota
from trii_ingestion.services.simulation import (
    MAX_INVESTMENT_COP,
    MIN_INVESTMENT_COP,
    build_trade_simulation,
    estimate_trade_commission,
)


def _build_payload(
    *,
    symbol: str = "NUCO",
    current_stats: dict | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "current_stats": current_stats or {},
    }


def _build_stat(latest_value: float, mean: float, stddev: float, sample_count: int = 180) -> dict:
    return {
        "latest_value": latest_value,
        "mean": mean,
        "stddev": stddev,
        "sample_count": sample_count,
    }


def _iso_seconds_ago(seconds: int) -> str:
    return (now_in_bogota() - timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def test_estimate_trade_commission_matches_trii_pro_threshold_examples() -> None:
    assert round(estimate_trade_commission(475_200), 4) == 7_437.5
    assert round(estimate_trade_commission(5_000_000), 4) == 7_437.5
    assert round(estimate_trade_commission(5_010_000), 2) == 7_452.38
    assert round(estimate_trade_commission(8_291_600), 3) == 12_333.755
    assert round(estimate_trade_commission(8_548_000), 2) == 12_715.15


def test_build_trade_simulation_returns_buy_and_sell_limit_plans() -> None:
    current_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(30),
        "spread_bps": 42.0,
        "obi_l1": 0.34,
        "obi_top_5": 0.18,
        "book_pressure_ratio": 1.14,
        "depth_weighted_microprice_deviation": 38.0,
        "last_price": 43_640,
        "mid_price": 43_700,
        "low_price": 43_600,
        "high_price": 45_180,
        "traded_value": 4_700_000_000,
        "traded_volume": 108_000,
        "bid_depth_total_5": 15_200,
        "ask_depth_total_5": 11_400,
        "daily_change_percent": -145,
        "best_bid_price": 43_620,
        "best_ask_price": 43_680,
        "best_bid_quantity": 6_100,
        "best_ask_quantity": 2_900,
    }
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(60),
        "last_price": 43_720,
        "traded_volume": 107_200,
        "traded_value": 4_660_000_000,
    }
    payload = _build_payload(
        current_stats={
            "spread_bps": _build_stat(42.0, 58.0, 12.0),
            "obi_l1": _build_stat(0.34, -0.10, 0.22),
            "obi_top_5": _build_stat(0.18, -0.16, 0.14),
            "depth_weighted_microprice_deviation": _build_stat(38.0, -32.0, 28.0),
            "book_pressure_ratio": _build_stat(1.14, 0.92, 0.12),
        },
    )

    result = build_trade_simulation(payload, [current_snapshot, previous_snapshot])

    assert result["dominant_side"] == "buy"
    assert result["probability_up_pct"] > result["probability_down_pct"]
    assert result["suggested_investment_cop"] <= MAX_INVESTMENT_COP

    buy_plan = result["buy_plan"]
    sell_plan = result["sell_plan"]

    assert buy_plan["side"] == "buy"
    assert buy_plan["scenario_label"] == "Si no tienes acciones"
    assert buy_plan["order_label"] == "Compra limite"
    assert current_snapshot["best_bid_price"] <= buy_plan["limit_price"] <= current_snapshot["best_ask_price"]
    assert buy_plan["reference_capital_cop"] >= MIN_INVESTMENT_COP
    assert buy_plan["entry_gap_bps"] < 5
    assert buy_plan["target_price"] > buy_plan["limit_price"]
    assert buy_plan["share_quantity"] > 0
    assert buy_plan["expected_net_profit_cop"] >= 99_999
    assert buy_plan["total_commission_cop"] > 0
    assert buy_plan["setup_ready"] is True
    assert buy_plan["blockers"] == []
    assert len(buy_plan["drivers"]) >= 4

    assert sell_plan["side"] == "sell"
    assert sell_plan["scenario_label"] == "Si ya tienes acciones"
    assert sell_plan["order_label"] == "Venta limite"
    assert current_snapshot["best_bid_price"] <= sell_plan["limit_price"] <= current_snapshot["best_ask_price"]
    assert sell_plan["setup_ready"] is False
    assert "Prob" in sell_plan["blockers"]
    assert "Direccion" in sell_plan["blockers"]


def test_build_trade_simulation_can_flip_to_sell_dominance() -> None:
    current_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(30),
        "spread_bps": 54.0,
        "obi_l1": -0.58,
        "obi_top_5": -0.31,
        "book_pressure_ratio": 0.71,
        "depth_weighted_microprice_deviation": -62.0,
        "last_price": 44_980,
        "mid_price": 44_910,
        "low_price": 43_480,
        "high_price": 45_180,
        "traded_value": 4_900_000_000,
        "traded_volume": 109_500,
        "bid_depth_total_5": 9_800,
        "ask_depth_total_5": 14_900,
        "daily_change_percent": 132,
        "best_bid_price": 44_900,
        "best_ask_price": 44_980,
        "best_bid_quantity": 1_600,
        "best_ask_quantity": 4_800,
    }
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(60),
        "last_price": 44_900,
        "traded_volume": 108_700,
        "traded_value": 4_870_000_000,
    }
    payload = _build_payload(
        current_stats={
            "spread_bps": _build_stat(54.0, 60.0, 10.0),
            "obi_l1": _build_stat(-0.58, -0.12, 0.18),
            "obi_top_5": _build_stat(-0.31, -0.16, 0.10),
            "depth_weighted_microprice_deviation": _build_stat(-62.0, -18.0, 24.0),
            "book_pressure_ratio": _build_stat(0.71, 0.94, 0.10),
        },
    )

    result = build_trade_simulation(payload, [current_snapshot, previous_snapshot])

    assert result["dominant_side"] == "sell"
    assert result["probability_down_pct"] > result["probability_up_pct"]
    assert result["sell_plan"]["tone"] in {"green", "gray", "red"}
    assert current_snapshot["best_bid_price"] <= result["sell_plan"]["limit_price"] <= current_snapshot["best_ask_price"]
    assert result["sell_plan"]["expected_move_bps"] > 0
    assert result["sell_plan"]["entry_gap_bps"] < 25
    assert result["sell_plan"]["setup_ready"] is True
    assert result["sell_plan"]["expected_net_profit_cop"] >= 99_999
    assert result["buy_plan"]["setup_ready"] is False


def test_build_trade_simulation_degrades_tone_when_feed_or_spread_is_bad() -> None:
    current_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(600),
        "spread_bps": 240.0,
        "obi_l1": -0.04,
        "obi_top_5": 0.01,
        "book_pressure_ratio": 1.01,
        "depth_weighted_microprice_deviation": 4.0,
        "last_price": 43_900,
        "mid_price": 43_890,
        "low_price": 43_480,
        "high_price": 45_180,
        "traded_value": 4_761_310_780,
        "traded_volume": 108_540,
        "bid_depth_total_5": 10_900,
        "ask_depth_total_5": 10_700,
        "daily_change_percent": -12,
        "best_bid_price": 43_880,
        "best_ask_price": 43_920,
        "best_bid_quantity": 500,
        "best_ask_quantity": 550,
    }
    previous_snapshot = {
        "symbol": "NUCO",
        "captured_at": _iso_seconds_ago(660),
        "last_price": 43_910,
        "traded_volume": 108_520,
        "traded_value": 4_760_000_000,
    }
    payload = _build_payload(
        current_stats={
            "spread_bps": _build_stat(240.0, 82.0, 18.0, sample_count=45),
            "obi_l1": _build_stat(-0.04, -0.03, 0.21, sample_count=45),
            "obi_top_5": _build_stat(0.01, 0.00, 0.16, sample_count=45),
            "depth_weighted_microprice_deviation": _build_stat(4.0, -2.0, 31.0, sample_count=45),
            "book_pressure_ratio": _build_stat(1.01, 0.99, 0.18, sample_count=45),
        },
    )

    result = build_trade_simulation(payload, [current_snapshot, previous_snapshot])

    assert result["sample_count"] == 45
    assert current_snapshot["best_bid_price"] <= result["buy_plan"]["limit_price"] <= current_snapshot["best_ask_price"]
    assert result["buy_plan"]["entry_gap_bps"] < 10
    assert result["buy_plan"]["tone"] == "red"
    assert result["sell_plan"]["tone"] == "red"
    assert "Lag" in result["buy_plan"]["blockers"]
    assert "Spread" in result["buy_plan"]["blockers"]
    assert "Profit" in result["buy_plan"]["blockers"]
    assert result["buy_plan"]["setup_ready"] is False
    assert result["sell_plan"]["setup_ready"] is False
    if result["buy_plan"]["best_effort_capital_cop"] is not None:
        assert result["buy_plan"]["best_effort_capital_cop"] <= MAX_INVESTMENT_COP
        assert result["buy_plan"]["best_effort_share_quantity"] > 0
