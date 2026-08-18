from pydantic import BaseModel, ConfigDict, Field

from trii_ingestion.models.types import Signal


class TechnicalIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: float
    raw_signal: str
    signal: Signal
    commentary: str


class TechnicalIndicatorsSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_name: str
    currency: str = "COP"
    buy_signals: int = Field(ge=0)
    hold_signals: int = Field(ge=0)
    sell_signals: int = Field(ge=0)
    indicators: list[TechnicalIndicator]
