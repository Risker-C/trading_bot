"""
交易引擎实现

统一的交易引擎编排器，负责协调四层架构。
"""

from typing import Optional
import pandas as pd
from utils.logger_utils import get_logger

from .contracts import (
    StrategyEngineInterface,
    RiskEngineInterface,
    ExecutionEngineInterface,
    MonitoringEngineInterface,
)

logger = get_logger("trading_engine")


class TradingEngine:
    """交易引擎

    负责协调策略、风控、执行、监控四层架构。
    """

    def __init__(
        self,
        strategy_engine: StrategyEngineInterface,
        risk_engine: RiskEngineInterface,
        execution_engine: ExecutionEngineInterface,
        monitoring_engine: MonitoringEngineInterface,
    ):
        """初始化交易引擎

        Args:
            strategy_engine: 策略引擎
            risk_engine: 风控引擎
            execution_engine: 执行引擎
            monitoring_engine: 监控引擎
        """
        self.strategy_engine = strategy_engine
        self.risk_engine = risk_engine
        self.execution_engine = execution_engine
        self.monitoring_engine = monitoring_engine
        self.running = False

        logger.info("交易引擎初始化完成")

    def start(self) -> None:
        """启动交易引擎"""
        logger.info("交易引擎启动")
        self.running = True
        self.monitoring_engine.update_status({"event": "engine_started"})

    def stop(self) -> None:
        """停止交易引擎"""
        logger.info("交易引擎停止")
        self.running = False
        self.monitoring_engine.update_status({"event": "engine_stopped"})

    def run_cycle(self, df: pd.DataFrame) -> dict:
        """运行一个交易周期

        Args:
            df: K线数据

        Returns:
            周期执行结果
        """
        result = {
            "success": False,
            "action": None,
            "error": None,
        }

        try:
            # 1. 策略层：生成信号
            signal = self.strategy_engine.generate_signal(df)
            if signal is None:
                return result

            # 2. 风控层：检查是否可以开仓
            can_trade, reason = self.risk_engine.can_open_position()
            if not can_trade:
                logger.info(f"风控拒绝: {reason}")
                self.monitoring_engine.update_status({
                    "event": "risk_rejected",
                    "reason": reason,
                })
                return result

            # 3. 执行层：执行信号
            success = self.execution_engine.execute_signal(signal, df)
            if success:
                result["success"] = True
                result["action"] = "executed"
                self.monitoring_engine.update_status({
                    "event": "signal_executed",
                    "signal": signal,
                })

            return result

        except Exception as e:
            logger.error(f"交易周期异常: {e}", exc_info=True)
            result["error"] = str(e)
            self.monitoring_engine.update_status({
                "event": "cycle_error",
                "error": str(e),
            })
            return result

    def get_status(self) -> dict:
        """获取引擎状态

        Returns:
            状态信息
        """
        return {
            "running": self.running,
            "strategies": self.strategy_engine.get_active_strategies(),
            "monitoring": self.monitoring_engine.get_status(),
        }
