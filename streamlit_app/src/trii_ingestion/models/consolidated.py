from pydantic import BaseModel, ConfigDict, Field

from trii_ingestion.models.stock_snapshot import OrderBookLevel
from trii_ingestion.models.support_and_resistance import SupportResistanceWindow
from trii_ingestion.models.technical import TechnicalIndicator


class ConsolidatedStockSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_price: float = Field(ge=0)
    daily_change_amount: float
    daily_change_percent: float
    daily_change_direction: str
    previous_close: float = Field(ge=0)
    best_bid_price: float = Field(ge=0)
    best_bid_quantity: int = Field(ge=0)
    best_ask_price: float = Field(ge=0)
    best_ask_quantity: int = Field(ge=0)
    spread: float
    mid_price: float = Field(ge=0)
    high_price: float = Field(ge=0)
    low_price: float = Field(ge=0)
    traded_value: float = Field(ge=0)
    traded_volume: int = Field(ge=0)
    bid_levels: list[OrderBookLevel]
    ask_levels: list[OrderBookLevel]


class ConsolidatedTechnicalSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buy_signals: int = Field(ge=0)
    hold_signals: int = Field(ge=0)
    sell_signals: int = Field(ge=0)
    indicators: list[TechnicalIndicator]


class ConsolidatedSupportResistanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily: SupportResistanceWindow
    long_term: SupportResistanceWindow


class ConsolidatedSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_name: str
    currency: str
    captured_at: str
    timezone: str
    stock_snapshot: ConsolidatedStockSnapshot
    technical_oscillators: ConsolidatedTechnicalSnapshot
    technical_moving_averages: ConsolidatedTechnicalSnapshot
    support_and_resistance: ConsolidatedSupportResistanceSnapshot
