"""
Backtest API models
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any


class StrategyWeight(BaseModel):
    """策略权重配置"""
    name: str = Field(..., description="策略名称", example="macd_cross")
    weight: float = Field(..., description="权重 (0-1 或 0-100)", example=0.6)
    params: Optional[Dict[str, Any]] = Field(default=None, description="策略参数")


class CreateSessionRequest(BaseModel):
    symbol: str = Field(..., example="BTC/USDT:USDT")
    timeframe: str = Field(..., example="15m")
    start_ts: int = Field(..., description="Start timestamp (Unix)")
    end_ts: int = Field(..., description="End timestamp (Unix)")
    initial_capital: float = Field(..., example=10000.0)
    strategy_name: str = Field(..., example="bollinger_trend")
    strategy_params: Optional[Dict] = Field(default_factory=dict)
    strategies: Optional[List[StrategyWeight]] = Field(default=None, description="多策略配置（优先级高于 strategy_name）")
    weighted_threshold: Optional[float] = Field(default=0.30, description="加权信号阈值")
    fee_rate: Optional[float] = Field(default=0.001)
    slippage_bps: Optional[float] = Field(default=5.0)
    leverage: Optional[float] = Field(default=1.0)

    @field_validator('strategies')
    @classmethod
    def validate_weights(cls, v):
        """验证权重总和为 1.0 或 100"""
        if v:
            if len(v) == 0:
                raise ValueError("策略列表不能为空")

            total = sum(s.weight for s in v)

            # 支持 0-1 或 0-100 两种格式
            is_valid_decimal = abs(total - 1.0) < 0.01  # 容差 ±0.01
            is_valid_percentage = abs(total - 100) < 0.1  # 容差 ±0.1

            if not (is_valid_decimal or is_valid_percentage):
                raise ValueError(
                    f"权重总和必须为 1.0 或 100，当前为 {total:.2f}。"
                    f"请检查各策略权重配置。"
                )

        return v


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
