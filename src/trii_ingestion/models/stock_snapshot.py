from pydantic import BaseModel, ConfigDict, Field


class OrderBookLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1)
    quantity: int = Field(ge=0)
    price: float = Field(ge=0)


class StockSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_name: str
    currency: str = "COP"
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
