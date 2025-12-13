"""
市场状态检测模块
根据技术指标判断当前市场处于震荡、过渡还是趋势状态
"""
from enum import Enum
from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Dict, Optional

import config
from indicators import IndicatorCalculator
from logger_utils import get_logger

logger = get_logger("market_regime")


class MarketRegime(Enum):
    """市场状态枚举"""
    RANGING = "ranging"          # 震荡市
    TRANSITIONING = "transitioning"  # 过渡市
    TRENDING = "trending"        # 趋势市


@dataclass
class RegimeInfo:
    """市场状态信息"""
    regime: MarketRegime
    confidence: float  # 置信度 0-1
    adx: float
    bb_width: float
    trend_direction: int  # 1=上涨, -1=下跌, 0=中性
    volatility: float
    details: Dict


class MarketRegimeDetector:
    """市场状态检测器"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.ind = IndicatorCalculator(df)

    def detect(self) -> RegimeInfo:
        """
        检测当前市场状态

        判断逻辑:
        1. 震荡市: ADX < 20 或 布林带宽度 < 2%
        2. 过渡市: 20 <= ADX < 30
        3. 趋势市: ADX >= 30 且 布林带宽度 > 3%
        """
        # 计算技术指标
        adx_data = self.ind.adx(config.ADX_PERIOD)
        bb = self.ind.bollinger_bands(config.BB_PERIOD, config.BB_STD_DEV)

        current_adx = adx_data['adx'].iloc[-1]
        bb_width_pct = bb['bandwidth'].iloc[-1]  # 已经是百分比,不需要再乘100

        # 趋势方向
        plus_di = adx_data['plus_di'].iloc[-1]
        minus_di = adx_data['minus_di'].iloc[-1]

        if plus_di > minus_di + 5:
            trend_direction = 1  # 上涨
        elif minus_di > plus_di + 5:
            trend_direction = -1  # 下跌
        else:
            trend_direction = 0  # 中性

        # 波动率
        volatility = self.ind.volatility(config.VOLATILITY_LOOKBACK).iloc[-1]

        # 判断市场状态
        regime, confidence = self._classify_regime(
            current_adx, bb_width_pct, volatility
        )

        details = {
            'adx': float(current_adx),
            'bb_width_pct': float(bb_width_pct),
            'plus_di': float(plus_di),
            'minus_di': float(minus_di),
            'volatility': float(volatility),
            'close': float(self.df['close'].iloc[-1]),
        }

        return RegimeInfo(
            regime=regime,
            confidence=confidence,
            adx=float(current_adx),
            bb_width=float(bb_width_pct),
            trend_direction=trend_direction,
            volatility=float(volatility),
            details=details
        )

    def _classify_regime(
        self,
        adx: float,
        bb_width_pct: float,
        volatility: float
    ) -> tuple[MarketRegime, float]:
        """
        分类市场状态
        返回: (状态, 置信度)
        """
        # 震荡市判断
        if adx < 20 or bb_width_pct < 2.0:
            # 置信度: ADX越低,布林带越窄,置信度越高
            confidence = 1.0 - (adx / 40) * 0.5 - (bb_width_pct / 4) * 0.5
            confidence = max(0.5, min(1.0, confidence))
            return MarketRegime.RANGING, confidence

        # 趋势市判断
        if adx >= 30 and bb_width_pct > 3.0:
            # 置信度: ADX越高,布林带越宽,置信度越高
            confidence = 0.5 + (adx - 30) / 40 * 0.3 + (bb_width_pct - 3) / 5 * 0.2
            confidence = max(0.5, min(1.0, confidence))
            return MarketRegime.TRENDING, confidence

        # 过渡市(默认)
        # 置信度: 越接近边界,置信度越低
        if adx < 25:
            confidence = 0.5 + (adx - 20) / 10 * 0.2
        else:
            confidence = 0.5 + (30 - adx) / 10 * 0.2
        confidence = max(0.4, min(0.7, confidence))

        return MarketRegime.TRANSITIONING, confidence

    def get_suitable_strategies(self, regime_info: RegimeInfo) -> list[str]:
        """
        根据市场状态返回适合的策略列表

        震荡市策略:
        - bollinger_breakthrough (均值回归版)
        - rsi_divergence
        - kdj_cross

        过渡市策略:
        - composite_score
        - multi_timeframe

        趋势市策略:
        - bollinger_trend (趋势突破版)
        - ema_cross
        - macd_cross
        - adx_trend
        - volume_breakout
        """
        if regime_info.regime == MarketRegime.RANGING:
            return [
                "bollinger_breakthrough",  # 均值回归
                "rsi_divergence",
                "kdj_cross",
            ]

        elif regime_info.regime == MarketRegime.TRENDING:
            return [
                "bollinger_trend",  # 趋势突破(需要新增)
                "ema_cross",
                "macd_cross",
                "adx_trend",
                "volume_breakout",
            ]

        else:  # TRANSITIONING
            return [
                "composite_score",
                "multi_timeframe",
            ]

    def should_trade(self, regime_info: RegimeInfo) -> tuple[bool, str]:
        """
        判断当前市场状态是否适合交易
        返回: (是否交易, 原因)
        """
        # 极端波动时不交易
        if regime_info.volatility > config.HIGH_VOLATILITY_THRESHOLD * 1.5:
            return False, f"波动率过高({regime_info.volatility:.2%})"

        # 过渡市且置信度低时谨慎交易
        if regime_info.regime == MarketRegime.TRANSITIONING and regime_info.confidence < 0.5:
            return False, "市场状态不明确"

        return True, "市场状态正常"


def detect_market_regime(df: pd.DataFrame) -> RegimeInfo:
    """
    便捷函数: 检测市场状态
    """
    detector = MarketRegimeDetector(df)
    return detector.detect()


def get_regime_strategies(df: pd.DataFrame) -> list[str]:
    """
    便捷函数: 获取当前市场状态下适合的策略
    """
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    logger.info(
        f"市场状态: {regime_info.regime.value.upper()} "
        f"(置信度: {regime_info.confidence:.0%}, "
        f"ADX: {regime_info.adx:.1f}, "
        f"布林带宽度: {regime_info.bb_width:.2f}%)"
    )

    strategies = detector.get_suitable_strategies(regime_info)
    logger.info(f"推荐策略: {', '.join(strategies)}")

    return strategies


# 测试代码
if __name__ == "__main__":
    import ccxt
    from trader import BitgetTrader

    print("=" * 50)
    print("市场状态检测测试")
    print("=" * 50)

    trader = BitgetTrader()
    df = trader.get_klines()

    if not df.empty:
        detector = MarketRegimeDetector(df)
        regime_info = detector.detect()

        print(f"\n当前市场状态: {regime_info.regime.value.upper()}")
        print(f"置信度: {regime_info.confidence:.0%}")
        print(f"ADX: {regime_info.adx:.1f}")
        print(f"布林带宽度: {regime_info.bb_width:.2f}%")
        print(f"趋势方向: {['下跌', '中性', '上涨'][regime_info.trend_direction + 1]}")
        print(f"波动率: {regime_info.volatility:.2%}")

        strategies = detector.get_suitable_strategies(regime_info)
        print(f"\n推荐策略:")
        for s in strategies:
            print(f"  - {s}")

        can_trade, reason = detector.should_trade(regime_info)
        print(f"\n是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
        print(f"原因: {reason}")
    else:
        print("获取K线数据失败")
