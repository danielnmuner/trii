from enum import Enum


class SectionType(str, Enum):
    STOCK_SNAPSHOT = "stock_snapshot"
    TECHNICAL_OSCILLATORS = "technical_oscillators"
    TECHNICAL_MOVING_AVERAGES = "technical_moving_averages"
    SUPPORT_AND_RESISTANCE = "support_and_resistance"


class Signal(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
