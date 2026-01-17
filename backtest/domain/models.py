"""
领域模型
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class BacktestRun:
    """回测运行"""
    id: str
    kline_dataset_id: str
    strategy_version_id: str
    param_set_id: Optional[str]
    filter_set: Optional[Dict[str, Any]]
    status: str
    created_at: int


@dataclass
class BacktestMetrics:
    """回测指标"""
    run_id: str
    total_trades: int
    win_rate: float
    total_pnl: float
    total_return: float
    max_drawdown: float
    sharpe: float
    sortino: float
    profit_factor: float
    expectancy: float
    avg_win: float
    avg_loss: float


@dataclass
class StrategyVersion:
    """策略版本"""
    id: str
    name: str
    version: str
    params_schema: Dict[str, Any]
    code_hash: str
    created_at: int


@dataclass
class ParameterSet:
    """参数集"""
    id: str
    strategy_version_id: str
    params: Dict[str, Any]
    source: str  # manual|grid|ga
    created_at: int
