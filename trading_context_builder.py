"""
Trading Context Builder - 交易上下文构建器

负责从系统各个模块收集信息，构建完整的 TradingContext
"""

from datetime import datetime
from typing import Dict, Optional
import pandas as pd

from policy_layer import TradingContext, MarketRegime, RiskMode
from risk_manager import RiskManager
import config
from logger_utils import get_logger

logger = get_logger("context_builder")


class TradingContextBuilder:
    """交易上下文构建器"""

    def __init__(self, risk_manager: RiskManager):
        """
        初始化

        Args:
            risk_manager: 风险管理器实例
        """
        self.risk_manager = risk_manager

    def build_context(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict
    ) -> TradingContext:
        """
        构建完整的交易上下文

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标

        Returns:
            TradingContext 对象
        """
        context = TradingContext()

        # A. 历史交易状态
        context.recent_trades_count = self.risk_manager.metrics.total_trades
        context.win_rate = self.risk_manager.metrics.win_rate
        context.recent_pnl = self.risk_manager.metrics.total_pnl
        context.consecutive_losses = self.risk_manager.metrics.consecutive_losses
        context.consecutive_wins = self.risk_manager.metrics.consecutive_wins
        context.avg_win = self.risk_manager.metrics.avg_win
        context.avg_loss = self.risk_manager.metrics.avg_loss

        # B. 当前持仓状态
        if self.risk_manager.position:
            pos = self.risk_manager.position
            context.has_position = True
            context.position_side = pos.side
            context.position_amount = pos.amount
            context.entry_price = pos.entry_price
            context.current_price = current_price
            context.unrealized_pnl = pos.unrealized_pnl
            context.unrealized_pnl_pct = pos.unrealized_pnl_pct

            # 计算持仓时间
            if pos.entry_time:
                holding_time = datetime.now() - pos.entry_time
                context.holding_time_minutes = holding_time.total_seconds() / 60

            context.current_stop_loss = pos.stop_loss_price
            context.current_take_profit = pos.take_profit_price

        # C. 实时市场结构
        context.market_regime = self._detect_market_regime(indicators)
        context.trend_direction = self._get_trend_direction(indicators)
        context.volatility = self.risk_manager.metrics.volatility
        context.adx = self._get_indicator_value(indicators, 'adx', 0.0)
        context.volume_ratio = self._get_indicator_value(indicators, 'volume_ratio', 1.0)

        # D. 系统状态
        context.current_risk_mode = self._determine_risk_mode()
        context.daily_pnl = self.risk_manager.daily_pnl
        context.daily_trades = self.risk_manager.daily_trades

        context.current_price = current_price

        logger.debug(f"交易上下文构建完成: 制度={context.market_regime.value}, "
                    f"持仓={context.has_position}, 胜率={context.win_rate:.1%}")

        return context

    def _detect_market_regime(self, indicators: Dict) -> MarketRegime:
        """
        检测市场制度

        Args:
            indicators: 技术指标

        Returns:
            MarketRegime
        """
        adx = self._get_indicator_value(indicators, 'adx', 0.0)
        ema_short = self._get_indicator_value(indicators, 'ema_short', 0.0)
        ema_long = self._get_indicator_value(indicators, 'ema_long', 0.0)
        bb_percent = self._get_indicator_value(indicators, 'bb_percent_b', 0.5)

        # 强趋势市
        if adx > 25 and abs(ema_short - ema_long) / ema_long > 0.01:
            return MarketRegime.TREND

        # 震荡市
        if adx < 20 and 0.2 < bb_percent < 0.8:
            return MarketRegime.MEAN_REVERT

        # 混乱市
        if adx < 15:
            return MarketRegime.CHOP

        return MarketRegime.UNKNOWN

    def _get_trend_direction(self, indicators: Dict) -> int:
        """
        获取趋势方向

        Args:
            indicators: 技术指标

        Returns:
            1=上涨, -1=下跌, 0=震荡
        """
        ema_short = self._get_indicator_value(indicators, 'ema_short', 0.0)
        ema_long = self._get_indicator_value(indicators, 'ema_long', 0.0)
        macd = self._get_indicator_value(indicators, 'macd', 0.0)

        if ema_short > ema_long and macd > 0:
            return 1
        elif ema_short < ema_long and macd < 0:
            return -1
        else:
            return 0

    def _determine_risk_mode(self) -> RiskMode:
        """
        确定当前风控模式

        Returns:
            RiskMode
        """
        # 根据连续亏损/盈利判断
        defensive_threshold = getattr(config, 'POLICY_DEFENSIVE_LOSS_THRESHOLD', 3)
        aggressive_threshold = getattr(config, 'POLICY_AGGRESSIVE_WIN_THRESHOLD', 5)

        if self.risk_manager.metrics.consecutive_losses >= defensive_threshold:
            return RiskMode.DEFENSIVE
        elif self.risk_manager.metrics.consecutive_wins >= aggressive_threshold:
            return RiskMode.AGGRESSIVE
        elif self.risk_manager.metrics.consecutive_losses > 0:
            return RiskMode.RECOVERY
        else:
            return RiskMode.NORMAL

    def _get_indicator_value(self, indicators: Dict, key: str, default: float) -> float:
        """
        安全获取指标值

        Args:
            indicators: 指标字典
            key: 指标键
            default: 默认值

        Returns:
            指标值
        """
        value = indicators.get(key, default)
        if hasattr(value, 'iloc'):
            return float(value.iloc[-1]) if len(value) > 0 else default
        return float(value) if value is not None else default


def get_context_builder(risk_manager: RiskManager) -> TradingContextBuilder:
    """获取上下文构建器实例"""
    return TradingContextBuilder(risk_manager)
