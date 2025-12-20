"""
方向过滤器 - 解决做多胜率低的问题
根据市场环境动态调整做多/做空的信号强度要求
"""
import pandas as pd
from typing import Tuple
from strategies import Signal, TradeSignal
from logger_utils import get_logger

logger = get_logger("direction_filter")


class DirectionFilter:
    """方向过滤器"""

    def __init__(self):
        """初始化"""
        # 做多需要更强的确认（因为历史胜率低）
        self.long_min_strength = 0.80   # 做多需要80%强度 (优化：从70%提高)
        self.short_min_strength = 0.5   # 做空保持50%强度

        # 做多需要更多策略一致
        self.long_min_agreement = 0.75  # 做多需要75%策略一致 (优化：从70%提高)
        self.short_min_agreement = 0.6  # 做空保持60%策略一致

    def filter_signal(
        self,
        signal: TradeSignal,
        df: pd.DataFrame,
        strategy_agreement: float
    ) -> Tuple[bool, str]:
        """
        过滤信号，对做多信号要求更严格

        Args:
            signal: 交易信号
            df: K线数据
            strategy_agreement: 策略一致性（0-1）

        Returns:
            (是否通过, 原因)
        """
        # 如果是做空信号，使用正常标准
        if signal.signal == Signal.SHORT:
            if signal.strength < self.short_min_strength:
                return False, f"做空信号强度不足({signal.strength:.2f} < {self.short_min_strength})"

            if strategy_agreement < self.short_min_agreement:
                return False, f"做空策略一致性不足({strategy_agreement:.2f} < {self.short_min_agreement})"

            return True, "做空信号通过"

        # 如果是做多信号，使用更严格的标准
        elif signal.signal == Signal.LONG:
            if signal.strength < self.long_min_strength:
                return False, f"做多信号强度不足({signal.strength:.2f} < {self.long_min_strength})"

            if strategy_agreement < self.long_min_agreement:
                return False, f"做多策略一致性不足({strategy_agreement:.2f} < {self.long_min_agreement})"

            # 额外检查：做多需要明确的上涨趋势
            if not self._check_uptrend(df):
                return False, "做多需要明确的上涨趋势确认"

            return True, "做多信号通过（严格标准）"

        return True, "非开仓信号"

    def _check_uptrend(self, df: pd.DataFrame) -> bool:
        """
        检查是否处于明确的上涨趋势

        要求：
        1. EMA9 > EMA21 > EMA55（多头排列）
        2. 价格在EMA9上方
        3. 最近3根K线至少2根收阳
        """
        if len(df) < 55:
            return False

        # 计算EMA
        ema9 = df['close'].ewm(span=9, adjust=False).mean()
        ema21 = df['close'].ewm(span=21, adjust=False).mean()
        ema55 = df['close'].ewm(span=55, adjust=False).mean()

        # 检查多头排列
        if not (ema9.iloc[-1] > ema21.iloc[-1] > ema55.iloc[-1]):
            logger.debug("做多过滤: EMA未形成多头排列")
            return False

        # 检查价格在EMA9上方
        if df['close'].iloc[-1] < ema9.iloc[-1]:
            logger.debug("做多过滤: 价格未在EMA9上方")
            return False

        # 检查最近3根K线的收盘情况
        recent_candles = df.tail(3)
        bullish_candles = sum(recent_candles['close'] > recent_candles['open'])

        if bullish_candles < 2:
            logger.debug(f"做多过滤: 最近3根K线阳线不足({bullish_candles}/3)")
            return False

        # 检查成交量确认
        if not self._check_volume_confirmation(df):
            return False

        logger.info("✅ 做多趋势确认: EMA多头排列 + 价格强势 + 成交量确认")
        return True

    def _check_volume_confirmation(self, df: pd.DataFrame) -> bool:
        """
        检查成交量确认（做多需要放量突破）

        要求：
        1. 最近一根K线成交量 > 20周期均量的1.2倍
        2. 或最近3根K线平均成交量 > 20周期均量
        """
        if len(df) < 20:
            return False

        # 计算20周期平均成交量
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]

        # 检查最近一根K线是否放量
        current_volume = df['volume'].iloc[-1]
        if current_volume > avg_volume * 1.2:
            logger.info("✅ 做多成交量确认: 当前放量突破")
            return True

        # 检查最近3根K线平均成交量
        recent_avg_volume = df['volume'].tail(3).mean()
        if recent_avg_volume > avg_volume:
            logger.info("✅ 做多成交量确认: 近期成交量活跃")
            return True

        logger.debug("做多过滤: 成交量不足")
        return False

    def update_thresholds(self, long_win_rate: float, short_win_rate: float):
        """
        根据历史胜率动态调整阈值

        Args:
            long_win_rate: 做多胜率
            short_win_rate: 做空胜率
        """
        # 如果做多胜率低于30%，大幅提高要求（紧急模式）
        if long_win_rate < 0.3:
            self.long_min_strength = 0.85   # 优化：从0.8提高到0.85
            self.long_min_agreement = 0.85  # 优化：从0.8提高到0.85
            logger.warning(f"做多胜率过低({long_win_rate:.1%})，提高信号要求到85%")
        # 如果做多胜率在30-40%之间，适度提高要求（中间档）
        elif long_win_rate < 0.4:
            self.long_min_strength = 0.82   # 新增：中间档位
            self.long_min_agreement = 0.80
            logger.info(f"做多胜率偏低({long_win_rate:.1%})，提高信号要求到82%")

        # 如果做空胜率高于40%，可以适当放宽
        if short_win_rate > 0.4:
            self.short_min_strength = 0.45
            self.short_min_agreement = 0.55
            logger.info(f"做空胜率良好({short_win_rate:.1%})，适度放宽要求")


# 全局实例
_direction_filter = None


def get_direction_filter() -> DirectionFilter:
    """获取方向过滤器实例"""
    global _direction_filter
    if _direction_filter is None:
        _direction_filter = DirectionFilter()
    return _direction_filter
