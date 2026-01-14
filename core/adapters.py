"""
适配器类

将现有模块包装成符合新接口的实现，实现向后兼容。
"""

from typing import Optional, List, Dict, Any
import pandas as pd

from .contracts import (
    StrategyEngineInterface,
    RiskEngineInterface,
    ExecutionEngineInterface,
    MonitoringEngineInterface,
)
from strategies.strategies import analyze_all_strategies, get_consensus_signal, TradeSignal
from risk.risk_manager import RiskManager
from utils.logger_utils import get_logger

logger = get_logger("adapters")


class StrategyEngineAdapter(StrategyEngineInterface):
    """策略引擎适配器

    包装现有的策略系统，使其符合 StrategyEngineInterface。
    """

    def __init__(self, strategies: List[str]):
        """初始化策略引擎适配器

        Args:
            strategies: 启用的策略列表
        """
        self.strategies = strategies
        logger.info(f"策略引擎适配器初始化，启用策略: {strategies}")

    def initialize(self, strategies: List[str]) -> None:
        """初始化策略引擎"""
        self.strategies = strategies
        logger.info(f"策略引擎重新初始化: {strategies}")

    def generate_signal(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        """生成交易信号"""
        try:
            # 使用现有的策略分析系统
            signal = get_consensus_signal(df, self.strategies)
            return signal
        except Exception as e:
            logger.error(f"生成信号失败: {e}", exc_info=True)
            return None

    def get_active_strategies(self) -> List[str]:
        """获取当前激活的策略列表"""
        return self.strategies


class RiskEngineAdapter(RiskEngineInterface):
    """风控引擎适配器

    包装现有的 RiskManager，使其符合 RiskEngineInterface。
    """

    def __init__(self, risk_manager: RiskManager):
        """初始化风控引擎适配器

        Args:
            risk_manager: 现有的 RiskManager 实例
        """
        self.risk_manager = risk_manager
        logger.info("风控引擎适配器初始化")

    def can_open_position(self) -> tuple[bool, str]:
        """检查是否可以开仓"""
        return self.risk_manager.can_open_position()

    def calculate_position_size(
        self,
        balance: float,
        price: float,
        df: pd.DataFrame,
        signal_strength: float = 1.0
    ) -> float:
        """计算仓位大小"""
        return self.risk_manager.calculate_position_size(
            balance, price, df, signal_strength
        )

    def check_stop_loss(self, df: pd.DataFrame) -> bool:
        """检查是否触发止损"""
        return self.risk_manager.check_stop_loss(df)

    def update_equity(self, balance: float) -> None:
        """更新权益"""
        self.risk_manager.update_equity(balance)


class ExecutionEngineAdapter(ExecutionEngineInterface):
    """执行引擎适配器

    包装现有的 trader，使其符合 ExecutionEngineInterface。
    """

    def __init__(self, trader):
        """初始化执行引擎适配器

        Args:
            trader: 现有的 trader 实例（BitgetTrader 或 LegacyAdapter）
        """
        self.trader = trader
        logger.info("执行引擎适配器初始化")

    def execute_signal(self, signal: TradeSignal, df: pd.DataFrame) -> bool:
        """执行交易信号"""
        return self.trader.execute_signal(signal, df)

    def open_long(self, amount: float, df: pd.DataFrame) -> bool:
        """开多仓"""
        return self.trader.open_long(amount, df)

    def open_short(self, amount: float, df: pd.DataFrame) -> bool:
        """开空仓"""
        return self.trader.open_short(amount, df)

    def close_position(self, reason: str = "") -> bool:
        """平仓"""
        return self.trader.close_position(reason)

    def get_balance(self) -> float:
        """获取账户余额"""
        return self.trader.get_balance()

    def sync_position(self) -> None:
        """同步持仓信息"""
        self.trader.sync_position()


class MonitoringEngineAdapter(MonitoringEngineInterface):
    """监控引擎适配器

    包装现有的监控系统，使其符合 MonitoringEngineInterface。
    """

    def __init__(self, status_monitor=None):
        """初始化监控引擎适配器

        Args:
            status_monitor: 现有的 status_monitor 实例（可选）
        """
        self.status_monitor = status_monitor
        self.status = {"running": False, "events": []}
        logger.info("监控引擎适配器初始化")

    def update_status(self, event: Dict[str, Any]) -> None:
        """更新状态"""
        self.status["events"].append(event)
        logger.debug(f"状态更新: {event}")

    def log_trade(self, trade_data: Dict[str, Any]) -> None:
        """记录交易"""
        logger.info(f"交易记录: {trade_data}")

    def send_notification(self, message: str, level: str = "info") -> None:
        """发送通知"""
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self.status
