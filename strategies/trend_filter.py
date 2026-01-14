"""
趋势过滤器
防止逆势交易，提高交易胜率
"""
from typing import Dict, Tuple
import pandas as pd

import config
from utils.logger_utils import get_logger
from strategies.strategies import Signal, TradeSignal
from strategies.indicators import IndicatorCalculator

logger = get_logger("trend_filter")


class TrendFilter:
    """趋势过滤器 - 防止逆势交易"""

    def __init__(self):
        self.enabled = getattr(config, 'ENABLE_TREND_FILTER', True)

    def check_signal(
        self,
        df: pd.DataFrame,
        signal: TradeSignal,
        indicators: Dict
    ) -> Tuple[bool, str]:
        """
        检查信号是否符合趋势过滤规则

        Args:
            df: K线数据
            signal: 交易信号
            indicators: 技术指标

        Returns:
            (是否通过, 原因)
        """
        if not self.enabled:
            return True, "趋势过滤未启用"

        # 只过滤开仓信号
        if signal.signal not in [Signal.LONG, Signal.SHORT]:
            return True, "非开仓信号"

        # 获取技术指标
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_histogram = indicators.get('macd_histogram', 0)
        ema_short = indicators.get('ema_short', 0)
        ema_long = indicators.get('ema_long', 0)
        adx = indicators.get('adx', 0)
        plus_di = indicators.get('plus_di', 0)
        minus_di = indicators.get('minus_di', 0)
        bb_percent_b = indicators.get('bb_percent_b', 0.5)

        # 判断趋势方向
        ema_trend = "up" if ema_short > ema_long else "down"
        macd_trend = "up" if macd > 0 else "down"
        di_trend = "up" if plus_di > minus_di else "down"

        # 趋势强度
        is_strong_trend = adx > 25
        is_very_strong_trend = adx > 35

        # 检查做多信号
        if signal.signal == Signal.LONG:
            return self._check_long_signal(
                rsi, macd, macd_histogram, ema_trend, macd_trend, di_trend,
                is_strong_trend, is_very_strong_trend, bb_percent_b, adx
            )

        # 检查做空信号
        if signal.signal == Signal.SHORT:
            return self._check_short_signal(
                rsi, macd, macd_histogram, ema_trend, macd_trend, di_trend,
                is_strong_trend, is_very_strong_trend, bb_percent_b, adx
            )

        return True, "未知信号类型"

    def _check_long_signal(
        self,
        rsi: float,
        macd: float,
        macd_histogram: float,
        ema_trend: str,
        macd_trend: str,
        di_trend: str,
        is_strong_trend: bool,
        is_very_strong_trend: bool,
        bb_percent_b: float,
        adx: float
    ) -> Tuple[bool, str]:
        """
        检查做多信号

        Returns:
            (是否通过, 原因)
        """
        # 规则1: 禁止在强下跌趋势中做多
        if is_strong_trend and ema_trend == "down" and macd_trend == "down":
            return False, f"强下跌趋势中禁止做多 (ADX={adx:.1f}, EMA↓, MACD↓)"

        # 规则2: 禁止在极度超卖时盲目抄底
        if rsi < 20:
            return False, f"RSI极度超卖({rsi:.1f})，等待回升到30以上"

        # 规则3: 在强下跌趋势中，即使RSI超卖也要谨慎
        if is_very_strong_trend and ema_trend == "down" and rsi < 35:
            return False, f"强下跌趋势(ADX={adx:.1f})中RSI({rsi:.1f})偏低，风险过高"

        # 规则4: MACD和EMA趋势严重背离时拒绝
        if ema_trend == "down" and macd < -500:
            return False, f"EMA下降且MACD深度负值({macd:.1f})，趋势过于疲弱"

        # 规则5: DI指标显示强烈空头时拒绝
        if is_strong_trend and di_trend == "down" and ema_trend == "down":
            return False, f"DI和EMA均显示下跌趋势(ADX={adx:.1f})，不适合做多"

        # 规则6: 布林带位置过低且趋势向下时谨慎
        if bb_percent_b < 0.1 and ema_trend == "down" and is_strong_trend:
            return False, f"价格在布林带极低位置({bb_percent_b:.2f})且下跌趋势，接飞刀风险高"

        # 规则7: 震荡市场中的下跌趋势保护（新增）
        if not is_strong_trend and ema_trend == "down":
            # 震荡下跌时，要求RSI至少在40以上才能做多
            if rsi < 40:
                return False, f"震荡下跌市场(ADX={adx:.1f})中RSI({rsi:.1f})偏低，避免抄底"
            # 震荡下跌时，MACD必须为正或接近零
            if macd < -200:
                return False, f"震荡下跌市场中MACD({macd:.1f})过低，动能不足"

        # 规则8: 震荡市场中多重指标向下时拒绝（新增）
        if not is_strong_trend and ema_trend == "down" and macd_trend == "down" and di_trend == "down":
            return False, f"震荡市场(ADX={adx:.1f})中多重指标向下，趋势不明朗"

        # 通过所有检查
        return True, "趋势过滤通过"

    def _check_short_signal(
        self,
        rsi: float,
        macd: float,
        macd_histogram: float,
        ema_trend: str,
        macd_trend: str,
        di_trend: str,
        is_strong_trend: bool,
        is_very_strong_trend: bool,
        bb_percent_b: float,
        adx: float
    ) -> Tuple[bool, str]:
        """
        检查做空信号

        Returns:
            (是否通过, 原因)
        """
        # 规则1: 禁止在强上涨趋势中做空
        if is_strong_trend and ema_trend == "up" and macd_trend == "up":
            return False, f"强上涨趋势中禁止做空 (ADX={adx:.1f}, EMA↑, MACD↑)"

        # 规则2: 禁止在极度超买时盲目追空
        if rsi > 80:
            return False, f"RSI极度超买({rsi:.1f})，等待回落到70以下"

        # 规则3: 在强上涨趋势中，即使RSI超买也要谨慎
        if is_very_strong_trend and ema_trend == "up" and rsi > 65:
            return False, f"强上涨趋势(ADX={adx:.1f})中RSI({rsi:.1f})偏高，风险过高"

        # 规则4: MACD和EMA趋势严重背离时拒绝
        if ema_trend == "up" and macd > 500:
            return False, f"EMA上升且MACD深度正值({macd:.1f})，趋势过于强劲"

        # 规则5: DI指标显示强烈多头时拒绝
        if is_strong_trend and di_trend == "up" and ema_trend == "up":
            return False, f"DI和EMA均显示上涨趋势(ADX={adx:.1f})，不适合做空"

        # 规则6: 布林带位置过高且趋势向上时谨慎
        if bb_percent_b > 0.9 and ema_trend == "up" and is_strong_trend:
            return False, f"价格在布林带极高位置({bb_percent_b:.2f})且上涨趋势，追空风险高"

        # 通过所有检查
        return True, "趋势过滤通过"

    def get_trend_summary(self, indicators: Dict) -> Dict:
        """
        获取趋势摘要

        Args:
            indicators: 技术指标

        Returns:
            趋势摘要字典
        """
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        ema_short = indicators.get('ema_short', 0)
        ema_long = indicators.get('ema_long', 0)
        adx = indicators.get('adx', 0)
        plus_di = indicators.get('plus_di', 0)
        minus_di = indicators.get('minus_di', 0)

        # 判断趋势
        ema_trend = "上涨" if ema_short > ema_long else "下跌"
        macd_trend = "上涨" if macd > 0 else "下跌"
        di_trend = "上涨" if plus_di > minus_di else "下跌"

        # 趋势强度
        if adx > 35:
            trend_strength = "强趋势"
        elif adx > 25:
            trend_strength = "中等趋势"
        elif adx > 20:
            trend_strength = "弱趋势"
        else:
            trend_strength = "震荡"

        # RSI状态
        if rsi < 20:
            rsi_status = "极度超卖"
        elif rsi < 30:
            rsi_status = "超卖"
        elif rsi > 80:
            rsi_status = "极度超买"
        elif rsi > 70:
            rsi_status = "超买"
        else:
            rsi_status = "中性"

        # 综合判断
        if ema_trend == macd_trend == di_trend:
            overall_trend = f"明确{ema_trend}"
        elif ema_trend == macd_trend or ema_trend == di_trend:
            overall_trend = f"偏向{ema_trend}"
        else:
            overall_trend = "混乱/震荡"

        return {
            'overall_trend': overall_trend,
            'ema_trend': ema_trend,
            'macd_trend': macd_trend,
            'di_trend': di_trend,
            'trend_strength': trend_strength,
            'rsi_status': rsi_status,
            'adx': adx,
            'rsi': rsi,
        }


# 全局实例
_trend_filter = None


def get_trend_filter() -> TrendFilter:
    """获取趋势过滤器单例"""
    global _trend_filter
    if _trend_filter is None:
        _trend_filter = TrendFilter()
    return _trend_filter
