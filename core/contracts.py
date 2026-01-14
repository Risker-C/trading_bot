"""
核心引擎接口定义

定义交易系统的四层架构接口：
- StrategyEngineInterface: 策略层
- RiskEngineInterface: 风控层
- ExecutionEngineInterface: 执行层
- MonitoringEngineInterface: 监控层
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import pandas as pd


class TradeSignal:
    """交易信号数据类"""
    pass  # 使用现有的 TradeSignal 类


class StrategyEngineInterface(ABC):
    """策略引擎接口

    职责：策略加载、信号生成、共识计算
    """

    @abstractmethod
    def initialize(self, strategies: List[str]) -> None:
        """初始化策略引擎

        Args:
            strategies: 启用的策略列表
        """
        pass

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        """生成交易信号

        Args:
            df: K线数据

        Returns:
            交易信号，如果没有信号则返回 None
        """
        pass

    @abstractmethod
    def get_active_strategies(self) -> List[str]:
        """获取当前激活的策略列表"""
        pass


class RiskEngineInterface(ABC):
    """风控引擎接口

    职责：仓位管理、止损止盈、回撤控制
    """

    @abstractmethod
    def can_open_position(self) -> tuple[bool, str]:
        """检查是否可以开仓

        Returns:
            (是否可以开仓, 原因说明)
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        balance: float,
        price: float,
        df: pd.DataFrame,
        signal_strength: float = 1.0
    ) -> float:
        """计算仓位大小

        Args:
            balance: 账户余额
            price: 当前价格
            df: K线数据
            signal_strength: 信号强度

        Returns:
            仓位大小（张数）
        """
        pass

    @abstractmethod
    def check_stop_loss(self, df: pd.DataFrame) -> bool:
        """检查是否触发止损

        Args:
            df: K线数据

        Returns:
            是否触发止损
        """
        pass

    @abstractmethod
    def update_equity(self, balance: float) -> None:
        """更新权益

        Args:
            balance: 当前余额
        """
        pass


class ExecutionEngineInterface(ABC):
    """执行引擎接口

    职责：订单执行、交易所交互、流动性验证
    """

    @abstractmethod
    def execute_signal(self, signal: TradeSignal, df: pd.DataFrame) -> bool:
        """执行交易信号

        Args:
            signal: 交易信号
            df: K线数据

        Returns:
            是否执行成功
        """
        pass

    @abstractmethod
    def open_long(self, amount: float, df: pd.DataFrame) -> bool:
        """开多仓

        Args:
            amount: 仓位大小
            df: K线数据

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def open_short(self, amount: float, df: pd.DataFrame) -> bool:
        """开空仓

        Args:
            amount: 仓位大小
            df: K线数据

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def close_position(self, reason: str = "") -> bool:
        """平仓

        Args:
            reason: 平仓原因

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def get_balance(self) -> float:
        """获取账户余额"""
        pass

    @abstractmethod
    def sync_position(self) -> None:
        """同步持仓信息"""
        pass


class MonitoringEngineInterface(ABC):
    """监控引擎接口

    职责：状态监控、日志记录、通知推送
    """

    @abstractmethod
    def update_status(self, event: Dict[str, Any]) -> None:
        """更新状态

        Args:
            event: 事件数据
        """
        pass

    @abstractmethod
    def log_trade(self, trade_data: Dict[str, Any]) -> None:
        """记录交易

        Args:
            trade_data: 交易数据
        """
        pass

    @abstractmethod
    def send_notification(self, message: str, level: str = "info") -> None:
        """发送通知

        Args:
            message: 通知消息
            level: 通知级别 (info/warning/error)
        """
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        pass
