from __future__ import annotations

from datetime import datetime
from math import exp
from typing import Any

from trii_ingestion.services.analytics import (
    BOGOTA_TIMEZONE,
    build_historic_z_score_context,
    now_in_bogota,
)


MIN_TARGET_NET_PROFIT_COP = 100_000.0
TARGET_NET_PROFIT_COP = 150_000.0
MAX_TARGET_NET_PROFIT_COP = 200_000.0
MAX_INVESTMENT_COP = 20_000_000.0
MIN_INVESTMENT_COP = 5_000_000.0
INVESTMENT_STEP_COP = 5_000_000.0
TRII_PRO_COMMISSION_RATE = 0.0014875
TRII_PRO_MIN_COMMISSION_COP = 7_437.5

MIN_ACTIVE_SAMPLE_COUNT = 60
MAX_ACTIONABLE_LAG_SECONDS = 180
MAX_ACTIONABLE_SPREAD_BPS = 150.0
MAX_ENTRY_DISLOCATION_BPS = 120.0
MAX_REALISTIC_ENTRY_GAP_BPS = 90.0
MIN_ACTIONABLE_PROBABILITY_PCT = 58.0
CAPITAL_OPTIONS_COP = (5_000_000.0, 10_000_000.0, 15_000_000.0, 20_000_000.0)
TARGET_REFERENCE_PROFITS_COP = (
    MIN_TARGET_NET_PROFIT_COP,
    TARGET_NET_PROFIT_COP,
    MAX_TARGET_NET_PROFIT_COP,
)
TARGET_PROFIT_TOLERANCE_COP = 1.0

METRIC_CONTEXT_KEYS = (
    "spread_bps",
    "obi_l1",
    "obi_top_5",
    "depth_weighted_microprice_deviation",
    "book_pressure_ratio",
)


def estimate_trade_commission(notional_cop: float | None) -> float:
    if notional_cop is None or notional_cop <= 0:
        return 0.0
    return max(TRII_PRO_MIN_COMMISSION_COP, float(notional_cop) * TRII_PRO_COMMISSION_RATE)


def build_trade_simulation(
    payload: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_record = records[0] if records else {}
    previous_record = records[1] if len(records) > 1 else {}
    symbol = str(payload.get("symbol") or latest_record.get("symbol") or "").strip().upper()
    current_stats = payload.get("current_stats", {})

    metric_contexts = _build_metric_contexts(current_stats)
    sample_count = _resolve_sample_count(metric_contexts)

    spread_bps = _safe_float(latest_record.get("spread_bps"))
    obi_l1 = _safe_float(latest_record.get("obi_l1"))
    obi_top_5 = _safe_float(latest_record.get("obi_top_5"))
    book_pressure_ratio = _safe_float(latest_record.get("book_pressure_ratio"))
    delta_micro = _safe_float(latest_record.get("depth_weighted_microprice_deviation"))
    microprice = _safe_float(latest_record.get("microprice"))
    last_price = _safe_float(latest_record.get("last_price"))
    mid_price = _safe_float(latest_record.get("mid_price"))
    low_price = _safe_float(latest_record.get("low_price"))
    high_price = _safe_float(latest_record.get("high_price"))
    previous_close = _safe_float(latest_record.get("previous_close"))
    traded_value = _safe_float(latest_record.get("traded_value"))
    traded_volume = _safe_float(latest_record.get("traded_volume"))
    bid_depth_total_5 = _safe_float(latest_record.get("bid_depth_total_5"))
    ask_depth_total_5 = _safe_float(latest_record.get("ask_depth_total_5"))
    daily_change_percent = _safe_float(latest_record.get("daily_change_percent"))
    best_bid_price = _safe_float(latest_record.get("best_bid_price"))
    best_ask_price = _safe_float(latest_record.get("best_ask_price"))

    previous_last_price = _safe_float(previous_record.get("last_price"))
    previous_traded_volume = _safe_float(previous_record.get("traded_volume"))
    previous_traded_value = _safe_float(previous_record.get("traded_value"))

    vwap_cumulative = _compute_cumulative_vwap(traded_value, traded_volume)
    previous_vwap_cumulative = _compute_cumulative_vwap(previous_traded_value, previous_traded_volume)
    delta_vwap = None if last_price is None or vwap_cumulative is None else last_price - vwap_cumulative
    delta_vwap_bps = _to_bps(delta_vwap, vwap_cumulative)
    range_position = _compute_range_position(last_price, low_price, high_price)

    latest_captured_at = _parse_timestamp(latest_record.get("captured_at"))
    lag_seconds = None
    if latest_captured_at is not None:
        lag_seconds = max(int((now_in_bogota() - latest_captured_at).total_seconds()), 0)

    price_delta = None if last_price is None or previous_last_price is None else last_price - previous_last_price
    volume_delta = None if traded_volume is None or previous_traded_volume is None else traded_volume - previous_traded_volume
    daily_change_pct = None if daily_change_percent is None else daily_change_percent / 100.0

    z_spread = metric_contexts["spread_bps"]["z_score"]
    z_obi_l1 = metric_contexts["obi_l1"]["z_score"]
    z_obi_top_5 = metric_contexts["obi_top_5"]["z_score"]
    z_micro = metric_contexts["depth_weighted_microprice_deviation"]["z_score"]
    z_book_pressure = metric_contexts["book_pressure_ratio"]["z_score"]

    fair_price = _compute_fair_price(
        last_price=last_price,
        mid_price=mid_price,
        microprice=microprice,
        vwap_cumulative=vwap_cumulative,
    )

    probability_up_pct, probability_down_pct = _build_direction_probabilities(
        delta_vwap_bps=delta_vwap_bps,
        range_position=range_position,
        daily_change_pct=daily_change_pct,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        z_micro=z_micro,
        z_book_pressure=z_book_pressure,
        bid_depth_total_5=bid_depth_total_5,
        ask_depth_total_5=ask_depth_total_5,
        delta_micro=delta_micro,
        price_delta=price_delta,
        volume_delta=volume_delta,
        sample_count=sample_count,
        lag_seconds=lag_seconds,
        spread_bps=spread_bps,
    )

    common_inputs = {
        "sample_count": sample_count,
        "spread_bps": spread_bps,
        "z_spread": z_spread,
        "z_obi_l1": z_obi_l1,
        "z_obi_top_5": z_obi_top_5,
        "z_micro": z_micro,
        "z_book_pressure": z_book_pressure,
        "delta_micro": delta_micro,
        "delta_vwap": delta_vwap,
        "delta_vwap_bps": delta_vwap_bps,
        "range_position": range_position,
        "last_price": last_price,
        "mid_price": mid_price,
        "microprice": microprice,
        "vwap_cumulative": vwap_cumulative,
        "previous_vwap_cumulative": previous_vwap_cumulative,
        "high_price": high_price,
        "low_price": low_price,
        "previous_close": previous_close,
        "fair_price": fair_price,
        "best_bid_price": best_bid_price,
        "best_ask_price": best_ask_price,
        "best_bid_quantity": _safe_float(latest_record.get("best_bid_quantity")),
        "best_ask_quantity": _safe_float(latest_record.get("best_ask_quantity")),
        "lag_seconds": lag_seconds,
    }

    buy_plan = _build_limit_plan(
        side="buy",
        probability_pct=probability_up_pct,
        common_inputs=common_inputs,
    )
    sell_plan = _build_limit_plan(
        side="sell",
        probability_pct=probability_down_pct,
        common_inputs=common_inputs,
    )

    dominant_side = _select_dominant_side(buy_plan, sell_plan, probability_up_pct, probability_down_pct)
    dominant_plan = (
        buy_plan
        if dominant_side == "buy"
        else sell_plan
        if dominant_side == "sell"
        else None
    )

    return {
        "symbol": symbol,
        "sample_count": sample_count,
        "probability_up_pct": probability_up_pct,
        "probability_down_pct": probability_down_pct,
        "dominant_side": dominant_side,
        "dominant_probability_pct": max(probability_up_pct, probability_down_pct),
        "buy_plan": buy_plan,
        "sell_plan": sell_plan,
        "suggested_investment_cop": (
            dominant_plan.get("reference_notional_cop")
            if dominant_plan is not None
            else None
        ),
        "expected_net_profit_cop": (
            dominant_plan.get("expected_net_profit_cop")
            if dominant_plan is not None
            else None
        ),
    }


def _build_metric_contexts(current_stats: dict[str, Any]) -> dict[str, dict[str, str | float | int | None]]:
    return {
        metric: build_historic_z_score_context(current_stats.get(metric))
        for metric in METRIC_CONTEXT_KEYS
    }


def _resolve_sample_count(metric_contexts: dict[str, dict[str, str | float | int | None]]) -> int:
    return max(int(context.get("sample_count") or 0) for context in metric_contexts.values())


def _select_dominant_side(
    buy_plan: dict[str, Any],
    sell_plan: dict[str, Any],
    probability_up_pct: float,
    probability_down_pct: float,
) -> str:
    buy_ready = bool(buy_plan.get("setup_ready"))
    sell_ready = bool(sell_plan.get("setup_ready"))
    if buy_ready and not sell_ready:
        return "buy"
    if sell_ready and not buy_ready:
        return "sell"
    if not buy_ready and not sell_ready:
        return "none"

    buy_profit = _safe_float(buy_plan.get("expected_net_profit_cop"))
    sell_profit = _safe_float(sell_plan.get("expected_net_profit_cop"))
    if buy_profit is not None and sell_profit is not None and buy_profit != sell_profit:
        return "buy" if buy_profit > sell_profit else "sell"

    return "buy" if probability_up_pct >= probability_down_pct else "sell"


def _build_direction_probabilities(
    *,
    delta_vwap_bps: float | None,
    range_position: float | None,
    daily_change_pct: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    z_micro: float | None,
    z_book_pressure: float | None,
    bid_depth_total_5: float | None,
    ask_depth_total_5: float | None,
    delta_micro: float | None,
    price_delta: float | None,
    volume_delta: float | None,
    sample_count: int,
    lag_seconds: int | None,
    spread_bps: float | None,
) -> tuple[float, float]:
    buy_score = 0.0
    sell_score = 0.0

    if delta_vwap_bps is not None:
        if delta_vwap_bps <= -20:
            buy_score += _clamp(abs(delta_vwap_bps) / 40.0, 0.0, 3.2)
        elif delta_vwap_bps >= 20:
            sell_score += _clamp(delta_vwap_bps / 40.0, 0.0, 3.2)

    if range_position is not None:
        if range_position <= 0.35:
            buy_score += _clamp((0.35 - range_position) / 0.15, 0.0, 2.2)
        elif range_position >= 0.65:
            sell_score += _clamp((range_position - 0.65) / 0.15, 0.0, 2.2)

    if daily_change_pct is not None:
        if daily_change_pct <= -1.0:
            buy_score += _clamp(abs(daily_change_pct) / 1.5, 0.0, 1.4)
        elif daily_change_pct >= 1.0:
            sell_score += _clamp(daily_change_pct / 1.5, 0.0, 1.4)

    buy_score += _positive_signal_weight(z_obi_l1, scale=1.2, cap=2.0)
    sell_score += _negative_signal_weight(z_obi_l1, scale=1.2, cap=2.0)
    buy_score += _positive_signal_weight(z_obi_top_5, scale=1.1, cap=2.4)
    sell_score += _negative_signal_weight(z_obi_top_5, scale=1.1, cap=2.4)
    buy_score += _positive_signal_weight(z_micro, scale=1.3, cap=1.6)
    sell_score += _negative_signal_weight(z_micro, scale=1.3, cap=1.6)
    buy_score += _positive_signal_weight(z_book_pressure, scale=1.4, cap=1.2)
    sell_score += _negative_signal_weight(z_book_pressure, scale=1.4, cap=1.2)

    if bid_depth_total_5 is not None and ask_depth_total_5 is not None:
        if bid_depth_total_5 > ask_depth_total_5:
            buy_score += 0.35
        elif ask_depth_total_5 > bid_depth_total_5:
            sell_score += 0.35

    if delta_micro is not None:
        if delta_micro > 0:
            buy_score += 0.40
        elif delta_micro < 0:
            sell_score += 0.40

    if price_delta is not None and volume_delta is not None and volume_delta > 0:
        if price_delta > 0:
            buy_score += 0.45
        elif price_delta < 0:
            sell_score += 0.45

    quality_penalty = 0.0
    if sample_count < MIN_ACTIVE_SAMPLE_COUNT:
        quality_penalty += 1.6
    if lag_seconds is not None and lag_seconds > MAX_ACTIONABLE_LAG_SECONDS:
        quality_penalty += 2.6
    if spread_bps is not None and spread_bps > MAX_ACTIONABLE_SPREAD_BPS:
        quality_penalty += 2.0

    buy_score = max(buy_score - (quality_penalty * 0.35), 0.0)
    sell_score = max(sell_score - (quality_penalty * 0.35), 0.0)

    probability_up_pct = round(_clamp(_sigmoid(buy_score - sell_score) * 100.0, 5.0, 95.0), 1)
    probability_down_pct = round(100.0 - probability_up_pct, 1)
    return probability_up_pct, probability_down_pct


def _build_limit_plan(
    *,
    side: str,
    probability_pct: float,
    common_inputs: dict[str, float | int | None],
) -> dict[str, Any]:
    scenario_label = "Si no tienes acciones" if side == "buy" else "Si ya tienes acciones"
    order_label = "Compra limite" if side == "buy" else "Venta limite"
    exit_label = "Venta objetivo" if side == "buy" else "Recompra objetivo"
    last_price = _safe_float(common_inputs.get("last_price"))
    mid_price = _safe_float(common_inputs.get("mid_price"))
    microprice = _safe_float(common_inputs.get("microprice"))
    vwap_cumulative = _safe_float(common_inputs.get("vwap_cumulative"))
    spread_bps = _safe_float(common_inputs.get("spread_bps"))
    delta_vwap_bps = _safe_float(common_inputs.get("delta_vwap_bps"))
    range_position = _safe_float(common_inputs.get("range_position"))
    z_obi_l1 = _safe_float(common_inputs.get("z_obi_l1"))
    z_obi_top_5 = _safe_float(common_inputs.get("z_obi_top_5"))
    delta_micro = _safe_float(common_inputs.get("delta_micro"))
    z_spread = _safe_float(common_inputs.get("z_spread"))

    limit_price = _select_limit_price(
        side=side,
        best_bid_price=_safe_float(common_inputs.get("best_bid_price")),
        best_ask_price=_safe_float(common_inputs.get("best_ask_price")),
        best_bid_quantity=_safe_float(common_inputs.get("best_bid_quantity")),
        best_ask_quantity=_safe_float(common_inputs.get("best_ask_quantity")),
        last_price=last_price,
        mid_price=mid_price,
        microprice=microprice,
        vwap_cumulative=vwap_cumulative,
        probability_pct=probability_pct,
        z_spread=z_spread,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        delta_micro=delta_micro,
    )
    if limit_price is None or limit_price <= 0:
        return _build_empty_plan(
            side=side,
            scenario_label=scenario_label,
            order_label=order_label,
            exit_label=exit_label,
        )

    entry_dislocation_bps = _estimate_entry_dislocation_bps(
        side=side,
        entry_price=limit_price,
        fair_price=_safe_float(common_inputs.get("fair_price")),
    )
    expected_move_bps = _estimate_expected_move_bps(
        side=side,
        probability_pct=probability_pct,
        delta_vwap_bps=delta_vwap_bps,
        range_position=range_position,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        z_micro=_safe_float(common_inputs.get("z_micro")),
        z_book_pressure=_safe_float(common_inputs.get("z_book_pressure")),
        spread_bps=spread_bps,
        entry_dislocation_bps=entry_dislocation_bps,
    )
    opportunity_room_bps = _estimate_opportunity_room_bps(
        side=side,
        entry_price=limit_price,
        last_price=last_price,
        mid_price=mid_price,
        microprice=microprice,
        vwap_cumulative=vwap_cumulative,
        previous_close=_safe_float(common_inputs.get("previous_close")),
        high_price=_safe_float(common_inputs.get("high_price")),
        low_price=_safe_float(common_inputs.get("low_price")),
    )
    max_room_target_price = _estimate_target_price(
        side=side,
        entry_price=limit_price,
        expected_move_bps=expected_move_bps,
        opportunity_room_bps=opportunity_room_bps,
    )
    expected_loss_rate = _estimate_loss_rate(
        expected_move_bps=expected_move_bps,
        spread_bps=_safe_float(common_inputs.get("spread_bps")),
    )
    capital_ladder = _build_capital_ladder(
        side=side,
        entry_price=limit_price,
        max_room_target_price=max_room_target_price,
        loss_rate=expected_loss_rate,
    )
    candidate = _select_capital_candidate(capital_ladder)
    best_effort_candidate = _select_best_effort_candidate(capital_ladder)

    lag_seconds = int(common_inputs.get("lag_seconds") or 0) if common_inputs.get("lag_seconds") is not None else None
    sample_count = int(common_inputs.get("sample_count") or 0)
    entry_gap_bps = _estimate_entry_gap_bps(
        entry_price=limit_price,
        last_price=last_price,
    )
    blockers = _collect_plan_blockers(
        side=side,
        probability_pct=probability_pct,
        sample_count=sample_count,
        lag_seconds=lag_seconds,
        spread_bps=spread_bps,
        entry_dislocation_bps=entry_dislocation_bps,
        entry_gap_bps=entry_gap_bps,
        opportunity_room_bps=opportunity_room_bps,
        expected_net_profit_cop=_safe_float(candidate.get("expected_net_profit_cop")) if candidate else None,
        delta_vwap_bps=delta_vwap_bps,
        range_position=range_position,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        delta_micro=delta_micro,
    )
    setup_ready = len(blockers) == 0
    tone = _build_plan_tone(setup_ready=setup_ready, probability_pct=probability_pct)
    actionable_move_bps = None
    if opportunity_room_bps is not None:
        actionable_move_bps = min(expected_move_bps, opportunity_room_bps)

    return {
        "side": side,
        "scenario_label": scenario_label,
        "order_label": order_label,
        "exit_label": exit_label,
        "probability_pct": probability_pct,
        "limit_price": limit_price,
        "target_price": _safe_float(candidate.get("target_price")) if candidate else None,
        "max_room_target_price": max_room_target_price,
        "share_quantity": _coerce_int(candidate.get("share_quantity")) if candidate else None,
        "reference_capital_cop": _safe_float(candidate.get("capital_cop")) if candidate else None,
        "reference_notional_cop": _safe_float(candidate.get("entry_notional_cop")) if candidate else None,
        "expected_net_profit_cop": _safe_float(candidate.get("expected_net_profit_cop")) if candidate else None,
        "expected_net_loss_cop": _safe_float(candidate.get("expected_net_loss_cop")) if candidate else None,
        "max_feasible_net_profit_cop": (
            _safe_float(candidate.get("max_feasible_net_profit_cop"))
            if candidate
            else _safe_float(best_effort_candidate.get("max_feasible_net_profit_cop"))
            if best_effort_candidate
            else None
        ),
        "required_move_bps": _safe_float(candidate.get("required_move_bps")) if candidate else None,
        "room_bps": opportunity_room_bps,
        "expected_move_bps": actionable_move_bps,
        "expected_return_pct": (
            None
            if candidate is None or candidate.get("target_price") is None
            else _to_percent_from_prices(limit_price, float(candidate["target_price"]), side=side)
        ),
        "total_commission_cop": _safe_float(candidate.get("total_commission_cop")) if candidate else None,
        "entry_dislocation_bps": entry_dislocation_bps,
        "entry_gap_bps": entry_gap_bps,
        "setup_ready": setup_ready,
        "tone": tone,
        "blockers": blockers,
        "best_effort_capital_cop": _safe_float(best_effort_candidate.get("capital_cop")) if best_effort_candidate else None,
        "best_effort_notional_cop": _safe_float(best_effort_candidate.get("entry_notional_cop")) if best_effort_candidate else None,
        "best_effort_share_quantity": _coerce_int(best_effort_candidate.get("share_quantity")) if best_effort_candidate else None,
        "best_effort_target_price": _safe_float(best_effort_candidate.get("max_room_target_price")) if best_effort_candidate else None,
        "best_effort_move_bps": _safe_float(best_effort_candidate.get("max_feasible_move_bps")) if best_effort_candidate else None,
        "best_effort_total_commission_cop": _safe_float(best_effort_candidate.get("total_commission_cop")) if best_effort_candidate else None,
        "capital_ladder": [
            {
                "label": str(item["label"]),
                "net_profit_cop": _safe_float(item.get("net_profit_cop")),
                "tone": str(item["tone"]),
            }
            for item in capital_ladder
        ],
        "drivers": _build_plan_drivers(
            side=side,
            probability_pct=probability_pct,
            lag_seconds=lag_seconds,
            spread_bps=spread_bps,
            entry_dislocation_bps=entry_dislocation_bps,
            entry_gap_bps=entry_gap_bps,
            opportunity_room_bps=opportunity_room_bps,
            delta_micro=delta_micro,
            delta_vwap=_safe_float(common_inputs.get("delta_vwap")),
            z_spread=z_spread,
            z_obi_l1=z_obi_l1,
            z_obi_top_5=z_obi_top_5,
            sample_count=sample_count,
            best_bid_price=_safe_float(common_inputs.get("best_bid_price")),
            best_ask_price=_safe_float(common_inputs.get("best_ask_price")),
            last_price=last_price,
            mid_price=mid_price,
            microprice=microprice,
        ),
    }


def _build_empty_plan(
    *,
    side: str,
    scenario_label: str,
    order_label: str,
    exit_label: str,
) -> dict[str, Any]:
    return {
        "side": side,
        "scenario_label": scenario_label,
        "order_label": order_label,
        "exit_label": exit_label,
        "probability_pct": 0.0,
        "limit_price": None,
        "target_price": None,
        "max_room_target_price": None,
        "share_quantity": None,
        "reference_capital_cop": None,
        "reference_notional_cop": None,
        "expected_net_profit_cop": None,
        "expected_net_loss_cop": None,
        "max_feasible_net_profit_cop": None,
        "required_move_bps": None,
        "room_bps": None,
        "expected_move_bps": None,
        "expected_return_pct": None,
        "total_commission_cop": None,
        "entry_dislocation_bps": None,
        "setup_ready": False,
        "tone": "red",
        "capital_ladder": [],
        "drivers": [_build_metric_driver("Libro", "Sin Cruce", "red")],
    }


def _select_limit_price(
    *,
    side: str,
    best_bid_price: float | None,
    best_ask_price: float | None,
    best_bid_quantity: float | None,
    best_ask_quantity: float | None,
    last_price: float | None,
    mid_price: float | None,
    microprice: float | None,
    vwap_cumulative: float | None,
    probability_pct: float,
    z_spread: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    delta_micro: float | None,
) -> float | None:
    if best_bid_price in (None, 0.0) and best_ask_price in (None, 0.0):
        return None
    if best_bid_price in (None, 0.0):
        return best_ask_price
    if best_ask_price in (None, 0.0):
        return best_bid_price
    if best_ask_price <= best_bid_price:
        return best_ask_price if side == "buy" else best_bid_price

    spread_cop = best_ask_price - best_bid_price
    book_mid_price = best_bid_price + (spread_cop / 2)
    reference_price = _build_reference_price(
        last_price=last_price,
        mid_price=mid_price,
        microprice=microprice,
        vwap_cumulative=vwap_cumulative,
        book_mid_price=book_mid_price,
    )

    urgency_component = _clamp((probability_pct - 50.0) / 35.0, 0.0, 1.0)
    spread_penalty = _clamp(max(z_spread or 0.0, 0.0) / 4.0, 0.0, 0.18)
    pressure_component = _build_limit_pressure_component(
        side=side,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        delta_micro=delta_micro,
    )
    queue_component = _build_limit_queue_component(
        side=side,
        best_bid_quantity=best_bid_quantity,
        best_ask_quantity=best_ask_quantity,
    )

    base_offset_ratio = _clamp(0.025 + ((1.0 - urgency_component) * 0.02) + spread_penalty, 0.015, 0.085)
    base_offset_cop = spread_cop * base_offset_ratio
    pressure_shift_cop = spread_cop * pressure_component
    queue_shift_cop = spread_cop * queue_component

    if side == "buy":
        candidate_price = reference_price - base_offset_cop + pressure_shift_cop + queue_shift_cop
        candidate_price = min(candidate_price, best_ask_price)
        return round(_clamp(candidate_price, best_bid_price, best_ask_price), 0)

    candidate_price = reference_price + base_offset_cop + pressure_shift_cop + queue_shift_cop
    candidate_price = max(candidate_price, best_bid_price)
    return round(_clamp(candidate_price, best_bid_price, best_ask_price), 0)


def _build_reference_price(
    *,
    last_price: float | None,
    mid_price: float | None,
    microprice: float | None,
    vwap_cumulative: float | None,
    book_mid_price: float,
) -> float:
    weighted_values: list[tuple[float, float]] = [(book_mid_price, 0.10)]
    if last_price is not None:
        weighted_values.append((last_price, 0.45))
    if mid_price is not None:
        weighted_values.append((mid_price, 0.18))
    if microprice is not None:
        weighted_values.append((microprice, 0.17))
    if vwap_cumulative is not None:
        weighted_values.append((vwap_cumulative, 0.10))
    numerator = sum(value * weight for value, weight in weighted_values)
    denominator = sum(weight for _, weight in weighted_values)
    return numerator / denominator


def _build_limit_pressure_component(
    *,
    side: str,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    delta_micro: float | None,
) -> float:
    directional_pressure = (
        (z_obi_l1 or 0.0) * 0.020
        + (z_obi_top_5 or 0.0) * 0.024
        + (delta_micro or 0.0) * 0.00005
    )
    if side == "sell":
        directional_pressure *= -1
    return _clamp(directional_pressure, -0.045, 0.045)


def _build_limit_queue_component(
    *,
    side: str,
    best_bid_quantity: float | None,
    best_ask_quantity: float | None,
) -> float:
    if (
        best_bid_quantity is None
        or best_ask_quantity is None
        or (best_bid_quantity + best_ask_quantity) <= 0
    ):
        return 0.0

    queue_imbalance = (
        (best_bid_quantity - best_ask_quantity)
        / (best_bid_quantity + best_ask_quantity)
    )
    if side == "sell":
        queue_imbalance *= -1
    return _clamp(queue_imbalance * 0.055, -0.05, 0.05)


def _compute_fair_price(
    *,
    last_price: float | None,
    mid_price: float | None,
    microprice: float | None,
    vwap_cumulative: float | None,
) -> float | None:
    weighted_values: list[tuple[float, float]] = []
    if last_price is not None:
        weighted_values.append((last_price, 0.35))
    if mid_price is not None:
        weighted_values.append((mid_price, 0.30))
    if microprice is not None:
        weighted_values.append((microprice, 0.25))
    if vwap_cumulative is not None:
        weighted_values.append((vwap_cumulative, 0.10))
    if not weighted_values:
        return None
    numerator = sum(value * weight for value, weight in weighted_values)
    denominator = sum(weight for _, weight in weighted_values)
    return numerator / denominator


def _estimate_entry_dislocation_bps(
    *,
    side: str,
    entry_price: float | None,
    fair_price: float | None,
) -> float | None:
    if entry_price in (None, 0.0) or fair_price in (None, 0.0):
        return None
    if side == "buy":
        return max(((entry_price - fair_price) / fair_price) * 10_000, 0.0)
    return max(((fair_price - entry_price) / fair_price) * 10_000, 0.0)


def _estimate_entry_gap_bps(
    *,
    entry_price: float | None,
    last_price: float | None,
) -> float | None:
    if entry_price in (None, 0.0) or last_price in (None, 0.0):
        return None
    return abs(((entry_price - last_price) / last_price) * 10_000)


def _estimate_expected_move_bps(
    *,
    side: str,
    probability_pct: float,
    delta_vwap_bps: float | None,
    range_position: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    z_micro: float | None,
    z_book_pressure: float | None,
    spread_bps: float | None,
    entry_dislocation_bps: float | None,
) -> float:
    score = max(probability_pct - 50.0, 0.0) * 1.6

    if side == "buy":
        if delta_vwap_bps is not None and delta_vwap_bps < 0:
            score += min(abs(delta_vwap_bps) * 0.45, 85.0)
        if range_position is not None and range_position < 0.50:
            score += min((0.50 - range_position) * 120.0, 55.0)
        score += min(max(z_obi_l1 or 0.0, 0.0) * 14.0, 32.0)
        score += min(max(z_obi_top_5 or 0.0, 0.0) * 18.0, 42.0)
        score += min(max(z_micro or 0.0, 0.0) * 10.0, 25.0)
        score += min(max(z_book_pressure or 0.0, 0.0) * 8.0, 18.0)
    else:
        if delta_vwap_bps is not None and delta_vwap_bps > 0:
            score += min(delta_vwap_bps * 0.45, 85.0)
        if range_position is not None and range_position > 0.50:
            score += min((range_position - 0.50) * 120.0, 55.0)
        score += min(max(-(z_obi_l1 or 0.0), 0.0) * 14.0, 32.0)
        score += min(max(-(z_obi_top_5 or 0.0), 0.0) * 18.0, 42.0)
        score += min(max(-(z_micro or 0.0), 0.0) * 10.0, 25.0)
        score += min(max(-(z_book_pressure or 0.0), 0.0) * 8.0, 18.0)

    if spread_bps is not None:
        score -= min(max(spread_bps - 40.0, 0.0) * 0.35, 70.0)
    if entry_dislocation_bps is not None:
        score -= min(entry_dislocation_bps * 0.40, 90.0)

    return _clamp(score, 0.0, 240.0)


def _estimate_opportunity_room_bps(
    *,
    side: str,
    entry_price: float,
    last_price: float | None,
    mid_price: float | None,
    microprice: float | None,
    vwap_cumulative: float | None,
    previous_close: float | None,
    high_price: float | None,
    low_price: float | None,
) -> float | None:
    if entry_price <= 0:
        return None

    if side == "buy":
        references = [last_price, mid_price, microprice, vwap_cumulative, previous_close, high_price]
        rooms = [
            ((reference - entry_price) / entry_price) * 10_000
            for reference in references
            if reference is not None and reference > entry_price
        ]
    else:
        references = [last_price, mid_price, microprice, vwap_cumulative, previous_close, low_price]
        rooms = [
            ((entry_price - reference) / entry_price) * 10_000
            for reference in references
            if reference is not None and reference < entry_price
        ]

    if not rooms:
        return None
    return max(rooms)


def _estimate_target_price(
    *,
    side: str,
    entry_price: float,
    expected_move_bps: float,
    opportunity_room_bps: float | None,
) -> float | None:
    if opportunity_room_bps is None or opportunity_room_bps <= 0:
        return None
    actionable_move_bps = min(expected_move_bps, opportunity_room_bps)
    if actionable_move_bps <= 0:
        return None
    move_rate = actionable_move_bps / 10_000
    if side == "buy":
        return entry_price * (1 + move_rate)
    return entry_price * (1 - move_rate)


def _estimate_loss_rate(*, expected_move_bps: float, spread_bps: float | None) -> float:
    favorable_rate = max(expected_move_bps / 10_000, 0.0)
    spread_component = 0.0 if spread_bps is None else max(spread_bps / 10_000, 0.0) * 0.45
    return _clamp((favorable_rate * 0.50) + spread_component, 0.0035, 0.0150)


def _build_capital_ladder(
    *,
    side: str,
    entry_price: float,
    max_room_target_price: float | None,
    loss_rate: float,
) -> list[dict[str, float | str | None]]:
    if max_room_target_price is None:
        return []

    ladder: list[dict[str, float | str | None]] = []
    for capital_cop in CAPITAL_OPTIONS_COP:
        share_quantity = int(capital_cop // entry_price)
        if share_quantity <= 0:
            continue
        max_room_candidate = _simulate_limit_round_trip(
            side=side,
            entry_price=entry_price,
            target_price=max_room_target_price,
            quantity=share_quantity,
            loss_rate=loss_rate,
        )

        selected_candidate: dict[str, float] | None = None
        for target_profit_cop in TARGET_REFERENCE_PROFITS_COP:
            target_price = _price_for_net_target(
                side=side,
                entry_price=entry_price,
                quantity=share_quantity,
                target_net_profit_cop=target_profit_cop,
            )
            if not _is_within_room(
                side=side,
                target_price=target_price,
                max_room_target_price=max_room_target_price,
            ):
                continue
            selected_candidate = _simulate_limit_round_trip(
                side=side,
                entry_price=entry_price,
                target_price=target_price,
                quantity=share_quantity,
                loss_rate=loss_rate,
            )
            break

        max_feasible_profit = float(max_room_candidate["expected_net_profit_cop"])
        resolved_candidate = selected_candidate
        if resolved_candidate is None and max_feasible_profit >= MIN_TARGET_NET_PROFIT_COP:
            resolved_candidate = max_room_candidate

        if selected_candidate is not None:
            tone = "green"
        elif max_feasible_profit >= MIN_TARGET_NET_PROFIT_COP:
            tone = "gray"
        else:
            tone = "red"

        ladder.append(
            {
                "label": f"{int(capital_cop / 1_000_000)}M",
                "tone": tone,
                "capital_cop": capital_cop,
                "share_quantity": float(share_quantity),
                "entry_notional_cop": float(max_room_candidate["entry_notional_cop"]),
                "target_price": (
                    float(resolved_candidate["target_price"])
                    if resolved_candidate is not None
                    else None
                ),
                "expected_net_profit_cop": (
                    float(resolved_candidate["expected_net_profit_cop"])
                    if resolved_candidate is not None
                    else None
                ),
                "expected_net_loss_cop": (
                    float(resolved_candidate["expected_net_loss_cop"])
                    if resolved_candidate is not None
                    else float(max_room_candidate["expected_net_loss_cop"])
                ),
                "total_commission_cop": float(max_room_candidate["total_commission_cop"]),
                "required_move_bps": (
                    _to_bps_from_prices(entry_price, float(resolved_candidate["target_price"]), side=side)
                    if resolved_candidate is not None
                    else None
                ),
                "max_feasible_net_profit_cop": max_feasible_profit,
                "max_feasible_move_bps": _to_bps_from_prices(entry_price, max_room_target_price, side=side),
                "max_room_target_price": max_room_target_price,
            }
        )

    return ladder


def _select_capital_candidate(
    capital_ladder: list[dict[str, float | str | None]],
) -> dict[str, float | str | None] | None:
    if not capital_ladder:
        return None

    in_target_range = [
        candidate
        for candidate in capital_ladder
        if candidate.get("expected_net_profit_cop") is not None
        and (MIN_TARGET_NET_PROFIT_COP - TARGET_PROFIT_TOLERANCE_COP)
        <= float(candidate["expected_net_profit_cop"])
        <= MAX_TARGET_NET_PROFIT_COP
    ]
    if in_target_range:
        return min(
            in_target_range,
            key=lambda candidate: abs(float(candidate["expected_net_profit_cop"]) - TARGET_NET_PROFIT_COP),
        )

    feasible_room_candidates = [
        candidate
        for candidate in capital_ladder
        if float(candidate.get("max_feasible_net_profit_cop") or 0.0)
        >= (MIN_TARGET_NET_PROFIT_COP - TARGET_PROFIT_TOLERANCE_COP)
    ]
    if feasible_room_candidates:
        return min(
            feasible_room_candidates,
            key=lambda candidate: abs(float(candidate["max_feasible_net_profit_cop"]) - TARGET_NET_PROFIT_COP),
        )

    return None


def _select_best_effort_candidate(
    capital_ladder: list[dict[str, float | str | None]],
) -> dict[str, float | str | None] | None:
    if not capital_ladder:
        return None
    return max(
        capital_ladder,
        key=lambda candidate: float(candidate.get("max_feasible_net_profit_cop") or 0.0),
    )


def _simulate_limit_round_trip(
    *,
    side: str,
    entry_price: float,
    target_price: float,
    quantity: int,
    loss_rate: float,
) -> dict[str, float]:
    entry_notional = entry_price * quantity
    target_notional = target_price * quantity

    if side == "buy":
        buy_commission = estimate_trade_commission(entry_notional)
        sell_commission = estimate_trade_commission(target_notional)
        adverse_price = entry_price * (1 - loss_rate)
        adverse_notional = adverse_price * quantity
    else:
        sell_commission = estimate_trade_commission(entry_notional)
        buy_commission = estimate_trade_commission(target_notional)
        adverse_price = entry_price * (1 + loss_rate)
        adverse_notional = adverse_price * quantity

    total_commission = buy_commission + sell_commission
    expected_gross_profit = abs(target_notional - entry_notional)
    expected_net_profit = expected_gross_profit - total_commission
    expected_gross_loss = abs(adverse_notional - entry_notional)
    expected_net_loss = expected_gross_loss + total_commission

    return {
        "entry_notional_cop": entry_notional,
        "target_price": target_price,
        "expected_net_profit_cop": expected_net_profit,
        "expected_net_loss_cop": expected_net_loss,
        "total_commission_cop": total_commission,
    }


def _price_for_net_target(
    *,
    side: str,
    entry_price: float,
    quantity: int,
    target_net_profit_cop: float,
) -> float:
    entry_notional = entry_price * quantity
    entry_commission = estimate_trade_commission(entry_notional)
    if quantity <= 0:
        return entry_price

    per_share_buffer = (target_net_profit_cop + (2 * entry_commission)) / quantity
    target_price = entry_price + per_share_buffer if side == "buy" else max(entry_price - per_share_buffer, 0.0)

    for _ in range(3):
        exit_notional = target_price * quantity
        exit_commission = estimate_trade_commission(exit_notional)
        required_move_per_share = (target_net_profit_cop + entry_commission + exit_commission) / quantity
        if side == "buy":
            target_price = entry_price + required_move_per_share
        else:
            target_price = max(entry_price - required_move_per_share, 0.0)

    return target_price


def _is_within_room(
    *,
    side: str,
    target_price: float,
    max_room_target_price: float,
) -> bool:
    if side == "buy":
        return target_price <= max_room_target_price
    return target_price >= max_room_target_price


def _to_bps_from_prices(entry_price: float, target_price: float, *, side: str) -> float | None:
    if entry_price <= 0 or target_price <= 0:
        return None
    if side == "buy":
        return ((target_price - entry_price) / entry_price) * 10_000
    return ((entry_price - target_price) / entry_price) * 10_000


def _collect_plan_blockers(
    *,
    side: str,
    probability_pct: float,
    sample_count: int,
    lag_seconds: int | None,
    spread_bps: float | None,
    entry_dislocation_bps: float | None,
    entry_gap_bps: float | None,
    opportunity_room_bps: float | None,
    expected_net_profit_cop: float | None,
    delta_vwap_bps: float | None,
    range_position: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    delta_micro: float | None,
) -> list[str]:
    blockers: list[str] = []
    if sample_count < MIN_ACTIVE_SAMPLE_COUNT:
        blockers.append("Muestra")
    if lag_seconds is not None and lag_seconds > MAX_ACTIONABLE_LAG_SECONDS:
        blockers.append("Lag")
    if spread_bps is not None and spread_bps > MAX_ACTIONABLE_SPREAD_BPS:
        blockers.append("Spread")
    if entry_dislocation_bps is not None and entry_dislocation_bps > MAX_ENTRY_DISLOCATION_BPS:
        blockers.append("Entry")
    if entry_gap_bps is not None and entry_gap_bps > MAX_REALISTIC_ENTRY_GAP_BPS:
        blockers.append("Gap")
    if opportunity_room_bps in (None, 0.0):
        blockers.append("Room")
    if expected_net_profit_cop is None or expected_net_profit_cop < (MIN_TARGET_NET_PROFIT_COP - TARGET_PROFIT_TOLERANCE_COP):
        blockers.append("Profit")
    if probability_pct < MIN_ACTIONABLE_PROBABILITY_PCT:
        blockers.append("Prob")
    if not _has_directional_alignment(
        side=side,
        delta_vwap_bps=delta_vwap_bps,
        range_position=range_position,
        z_obi_l1=z_obi_l1,
        z_obi_top_5=z_obi_top_5,
        delta_micro=delta_micro,
    ):
        blockers.append("Direccion")
    return blockers


def _has_directional_alignment(
    *,
    side: str,
    delta_vwap_bps: float | None,
    range_position: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    delta_micro: float | None,
) -> bool:
    positive_signals = 0
    negative_signals = 0

    if delta_vwap_bps is not None:
        if delta_vwap_bps <= -10.0:
            positive_signals += 1
        elif delta_vwap_bps >= 10.0:
            negative_signals += 1

    if range_position is not None:
        if range_position <= 0.45:
            positive_signals += 1
        elif range_position >= 0.55:
            negative_signals += 1

    book_signal = max(z_obi_l1 or 0.0, z_obi_top_5 or 0.0)
    if book_signal >= 0.35:
        positive_signals += 1
    if min(z_obi_l1 or 0.0, z_obi_top_5 or 0.0) <= -0.35:
        negative_signals += 1

    if delta_micro is not None:
        if delta_micro > 0:
            positive_signals += 1
        elif delta_micro < 0:
            negative_signals += 1

    if side == "buy":
        return positive_signals >= 2 and negative_signals <= 2
    return negative_signals >= 2 and positive_signals <= 2


def _build_plan_tone(*, setup_ready: bool, probability_pct: float) -> str:
    if setup_ready:
        return "green"
    if probability_pct >= MIN_ACTIONABLE_PROBABILITY_PCT:
        return "gray"
    return "red"


def _build_plan_drivers(
    *,
    side: str,
    probability_pct: float,
    lag_seconds: int | None,
    spread_bps: float | None,
    entry_dislocation_bps: float | None,
    entry_gap_bps: float | None,
    opportunity_room_bps: float | None,
    delta_micro: float | None,
    delta_vwap: float | None,
    z_spread: float | None,
    z_obi_l1: float | None,
    z_obi_top_5: float | None,
    sample_count: int,
    best_bid_price: float | None,
    best_ask_price: float | None,
    last_price: float | None,
    mid_price: float | None,
    microprice: float | None,
) -> list[dict[str, str]]:
    drivers = [
        _build_metric_driver("Prob", f"{probability_pct:,.1f}%", _probability_tone(probability_pct)),
        _build_metric_driver("Z Spread", _format_sigma_value(z_spread), _spread_tone_from_z(z_spread)),
        _build_metric_driver("Z OBI1", _format_sigma_value(z_obi_l1), _directional_tone(z_obi_l1, side=side)),
        _build_metric_driver("Z OBI5", _format_sigma_value(z_obi_top_5), _directional_tone(z_obi_top_5, side=side)),
        _build_metric_driver("Delta Micro", _format_plain_number(delta_micro), _directional_tone(delta_micro, side=side)),
        _build_metric_driver(
            "Delta VWAP",
            _format_plain_number(delta_vwap),
            _directional_tone(-delta_vwap if side == "buy" and delta_vwap is not None else delta_vwap, side="buy"),
        ),
        _build_metric_driver("Entry-Fair", _format_bps(entry_dislocation_bps), _entry_dislocation_tone(entry_dislocation_bps)),
        _build_metric_driver("Entry-Last", _format_bps(entry_gap_bps), _entry_gap_tone(entry_gap_bps)),
        _build_metric_driver("Room", _format_bps(opportunity_room_bps), _room_tone(opportunity_room_bps)),
        _build_metric_driver("Bid", _format_price_integer(best_bid_price), "gray"),
        _build_metric_driver("Ask", _format_price_integer(best_ask_price), "gray"),
        _build_metric_driver("Last", _format_price_integer(last_price), "gray"),
        _build_metric_driver("Mid", _format_price_integer(mid_price), "gray"),
        _build_metric_driver("Micro", _format_price_integer(microprice), "gray"),
        _build_metric_driver("Lag", _format_elapsed_seconds(lag_seconds), _lag_tone(lag_seconds)),
        _build_metric_driver("Samples", f"{sample_count:,}", _sample_tone(sample_count)),
    ]
    return drivers


def _build_metric_driver(label: str, value: str, tone: str) -> dict[str, str]:
    return {"label": label, "value": value, "tone": tone}


def _probability_tone(probability_pct: float) -> str:
    if probability_pct >= 67.0:
        return "green"
    if probability_pct >= MIN_ACTIONABLE_PROBABILITY_PCT:
        return "gray"
    return "red"


def _spread_tone_from_z(z_score: float | None) -> str:
    if z_score is None:
        return "gray"
    if z_score >= 2.0:
        return "red"
    if z_score <= -2.0:
        return "green"
    return "gray"


def _directional_tone(value: float | None, *, side: str) -> str:
    if value is None:
        return "gray"
    if side == "buy":
        if value > 0:
            return "green"
        if value < 0:
            return "red"
        return "gray"
    if value < 0:
        return "green"
    if value > 0:
        return "red"
    return "gray"


def _entry_dislocation_tone(value: float | None) -> str:
    if value is None:
        return "gray"
    if value > MAX_ENTRY_DISLOCATION_BPS:
        return "red"
    if value <= 35.0:
        return "green"
    return "gray"


def _entry_gap_tone(value: float | None) -> str:
    if value is None:
        return "gray"
    if value > MAX_REALISTIC_ENTRY_GAP_BPS:
        return "red"
    if value <= 35.0:
        return "green"
    return "gray"


def _room_tone(value: float | None) -> str:
    if value is None or value <= 0:
        return "red"
    if value >= 120.0:
        return "green"
    return "gray"


def _lag_tone(value: int | None) -> str:
    if value is None:
        return "gray"
    if value > MAX_ACTIONABLE_LAG_SECONDS:
        return "red"
    return "green"


def _sample_tone(value: int) -> str:
    if value < MIN_ACTIVE_SAMPLE_COUNT:
        return "red"
    if value < 180:
        return "gray"
    return "green"


def _compute_cumulative_vwap(traded_value: float | None, traded_volume: float | None) -> float | None:
    if traded_value is None or traded_volume in (None, 0):
        return None
    return traded_value / traded_volume


def _compute_range_position(
    last_price: float | None,
    low_price: float | None,
    high_price: float | None,
) -> float | None:
    if last_price is None or low_price is None or high_price is None:
        return None
    if high_price <= low_price:
        return None
    return _clamp((last_price - low_price) / (high_price - low_price), 0.0, 1.0)


def _positive_signal_weight(value: float | None, *, scale: float, cap: float) -> float:
    if value is None or value <= 0:
        return 0.0
    return _clamp(value / scale, 0.0, cap)


def _negative_signal_weight(value: float | None, *, scale: float, cap: float) -> float:
    if value is None or value >= 0:
        return 0.0
    return _clamp(abs(value) / scale, 0.0, cap)


def _to_bps(delta_value: float | None, base_value: float | None) -> float | None:
    if delta_value is None or base_value in (None, 0.0):
        return None
    return (delta_value / base_value) * 10_000


def _to_percent_from_prices(entry_price: float, target_price: float, *, side: str) -> float | None:
    if entry_price <= 0 or target_price <= 0:
        return None
    if side == "buy":
        return ((target_price - entry_price) / entry_price) * 100.0
    return ((entry_price - target_price) / entry_price) * 100.0


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _parse_timestamp(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=BOGOTA_TIMEZONE)
    return parsed.astimezone(BOGOTA_TIMEZONE)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _format_sigma_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}{chr(963)}"


def _format_plain_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def _format_bps(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.1f}bps"


def _format_price_integer(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{round(value):,}"


def _format_elapsed_seconds(total_seconds: int | None) -> str:
    if total_seconds is None:
        return "n/a"
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds:02d}s"
