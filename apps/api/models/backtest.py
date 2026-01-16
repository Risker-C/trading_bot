"""
Backtest API models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict


class CreateSessionRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT:USDT")
    timeframe: str = Field(..., example="15m")
    start_ts: int = Field(..., description="Start timestamp (Unix)")
    end_ts: int = Field(..., description="End timestamp (Unix)")
    initial_capital: float = Field(..., example=10000.0)
    strategy_name: str = Field(..., example="bollinger_trend")
    strategy_params: Optional[Dict] = Field(default_factory=dict)
    fee_rate: Optional[float] = Field(default=0.001)
    slippage_bps: Optional[float] = Field(default=5.0)
    leverage: Optional[float] = Field(default=1.0)


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: int


class SessionDetailResponse(BaseModel):
    session_id: str
    status: str
    symbol: str
    timeframe: str
    start_ts: int
    end_ts: int
    initial_capital: float
    strategy_name: str
    created_at: int
    updated_at: int
    error_message: Optional[str] = None


class MetricsResponse(BaseModel):
    total_trades: int
    win_rate: float
    total_pnl: float
    total_return: float
    max_drawdown: float
    sharpe: float
    profit_factor: float
    expectancy: float
    avg_win: float
    avg_loss: float
