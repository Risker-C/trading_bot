from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class Trend(BaseModel):
    symbol: str
    timeframe: str
    direction: Literal["bullish", "bearish", "neutral"]
    change_percent: float = 0
    momentum: float = 0
    volatility: float = 0
    average_price: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    sample_size: int = 0
    updated_at: datetime
