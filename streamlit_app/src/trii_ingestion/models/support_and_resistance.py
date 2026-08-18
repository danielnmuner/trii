from pydantic import BaseModel, ConfigDict, Field


class SupportResistanceLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    rank: int = Field(ge=1)
    price: float = Field(ge=0)
    change_percent: float


class SupportResistanceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    close_price: float = Field(ge=0)
    levels: list[SupportResistanceLevel]
    analysis: str


class SupportResistanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_name: str
    currency: str = "COP"
    daily: SupportResistanceWindow
    long_term: SupportResistanceWindow
