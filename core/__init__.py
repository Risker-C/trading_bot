"""
核心引擎模块

提供统一的交易引擎接口和分层架构。
"""

from .contracts import (
    StrategyEngineInterface,
    RiskEngineInterface,
    ExecutionEngineInterface,
    MonitoringEngineInterface,
)
from .engine import TradingEngine
from .adapters import (
    StrategyEngineAdapter,
    RiskEngineAdapter,
    ExecutionEngineAdapter,
    MonitoringEngineAdapter,
)

__all__ = [
    "StrategyEngineInterface",
    "RiskEngineInterface",
    "ExecutionEngineInterface",
    "MonitoringEngineInterface",
    "TradingEngine",
    "StrategyEngineAdapter",
    "RiskEngineAdapter",
    "ExecutionEngineAdapter",
    "MonitoringEngineAdapter",
]
