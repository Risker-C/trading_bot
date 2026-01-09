from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Position(BaseModel):
    symbol: str
    side: Optional[str] = None
    amount: float = 0
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    leverage: Optional[int] = None
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    updated_at: Optional[datetime] = Field(default=None)
