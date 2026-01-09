from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Trade(BaseModel):
    id: int
    order_id: Optional[str] = None
    symbol: str
    side: Optional[str] = None
    action: Optional[str] = None
    amount: float = 0
    price: float = 0
    value_usdt: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    strategy: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None
    filled_price: Optional[float] = None
    filled_time: Optional[datetime] = None
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    batch_number: Optional[int] = None
    remaining_amount: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TradeSummary(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    total_pnl: float = 0
    avg_pnl: float = 0
    max_profit: float = 0
    max_loss: float = 0
    profit_factor: float = 0


class TradeHistoryResponse(BaseModel):
    today_pnl: float = 0
    today_trades: List[Trade] = Field(default_factory=list)
    recent_trades: List[Trade] = Field(default_factory=list)
    summary: TradeSummary = Field(default_factory=TradeSummary)
