"""
市场状态检测模块
根据技术指标判断当前市场处于震荡、过渡还是趋势状态
"""
from enum import Enum
from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config.settings import settings as config
from strategies.indicators import IndicatorCalculator
from utils.logger_utils import get_logger

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
    prev_regime: Optional[MarketRegime] = None  # 上一次的市场状态（用于滞回机制）


class MarketRegimeDetector:
    """市场状态检测器"""

    def __init__(self, df: pd.DataFrame, prev_regime: Optional[MarketRegime] = None):
        self.df = df
        self.ind = IndicatorCalculator(df)
        self.prev_regime = prev_regime  # 上一次的市场状态（用于滞回机制）

    @staticmethod
    def _score_adx(adx: float) -> float:
        """
        计算ADX对置信度的贡献
        ADX从25到50线性映射到0-1
        """
        return max(0.0, min(1.0, (adx - 25.0) / (50.0 - 25.0)))

    @staticmethod
    def _score_bb(bb_width_pct: float) -> float:
        """
        计算布林带宽度对置信度的贡献
        宽度从1%到4%线性映射到0-1
        """
        return max(0.0, min(1.0, (bb_width_pct - 1.0) / (4.0 - 1.0)))

    def detect(self) -> RegimeInfo:
        """
        检测当前市场状态

        判断逻辑（已优化，ADX优先）:
        1. 强趋势市: ADX >= 35 且 布林带宽度 > 2% (优先判定)
        2. 标准趋势市: ADX >= 30 且 布林带宽度 > 3%
        3. 震荡市: ADX < 20 且 布林带宽度 < 2% (必须同时满足)
        4. 过渡市: 其他情况

        修复说明:
        - 强趋势判断提前，避免被布林带条件误判为震荡市
        - 震荡市从"或"改为"且"，提高判定准确性
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
        分类市场状态（优化版 - 修复ADX优先级）
        返回: (状态, 置信度)

        改进点:
        1. ADX优先: 强趋势(ADX>35)优先判定,避免被布林带误判为震荡
        2. 滞回机制: 避免频繁切换状态
        3. 优化置信度计算: ADX和布林带分别计算贡献

        修复说明:
        - 原逻辑问题: 当ADX=55但BB宽度<2%时,会被误判为震荡市
        - 修复方案: 将强趋势判断提前到震荡市判断之前
        """
        # 滞回机制: 如果上一次是趋势市,允许稍微"变差"也继续保持
        if self.prev_regime == MarketRegime.TRENDING:
            if adx >= config.TREND_EXIT_ADX and bb_width_pct >= config.TREND_EXIT_BB:
                # 使用优化的置信度计算
                confidence = 0.7 * self._score_adx(adx) + 0.3 * self._score_bb(bb_width_pct)
                confidence = max(0.5, min(1.0, confidence))
                return MarketRegime.TRENDING, confidence

        # 【修复】强趋势优先判断: 当ADX > 35时,即使布林带宽度不够也判定为趋势市
        # 这个判断必须在震荡市判断之前,否则会被布林带<2%的条件误判
        if adx >= config.STRONG_TREND_ADX and bb_width_pct > config.STRONG_TREND_BB:
            # 使用优化的置信度计算
            confidence = 0.7 * self._score_adx(adx) + 0.3 * self._score_bb(bb_width_pct)
            confidence = max(0.5, min(1.0, confidence))
            logger.info(f"✅ 强趋势检测: ADX={adx:.1f} > {config.STRONG_TREND_ADX}, BB={bb_width_pct:.2f}% > {config.STRONG_TREND_BB}%")
            return MarketRegime.TRENDING, confidence

        # 趋势市判断 - 标准条件
        if adx >= 30 and bb_width_pct > 3.0:
            # 使用优化的置信度计算: 70% ADX权重, 30%布林带权重
            confidence = 0.7 * self._score_adx(adx) + 0.3 * self._score_bb(bb_width_pct)
            confidence = max(0.5, min(1.0, confidence))
            return MarketRegime.TRENDING, confidence

        # 震荡市判断 - 必须同时满足ADX弱且布林带窄
        # 修改逻辑: 从 "or" 改为 "and",避免强趋势被误判
        if adx < 20 and bb_width_pct < 2.0:
            # 置信度: ADX越低,布林带越窄,置信度越高
            confidence = 1.0 - (adx / 40) * 0.5 - (bb_width_pct / 4) * 0.5
            confidence = max(0.5, min(1.0, confidence))
            return MarketRegime.RANGING, confidence

        # 过渡市(默认)
        # 使用优化的置信度计算,但整体降低置信度
        confidence = 0.7 * self._score_adx(adx) + 0.3 * self._score_bb(bb_width_pct)
        confidence = confidence * 0.6  # 过渡市置信度打折
        confidence = max(0.3, min(0.7, confidence))

        return MarketRegime.TRANSITIONING, confidence

    def get_suitable_strategies(self, regime_info: RegimeInfo) -> list[str]:
        """
        根据市场状态返回适合的策略列表（修复版）

        修复说明：确保返回的策略都在config.ENABLE_STRATEGIES中

        震荡市策略:
        - composite_score (综合评分，适合各种市场)
        - macd_cross (MACD在震荡市也有效)

        过渡市策略:
        - composite_score (综合评分)
        - macd_cross
        - ema_cross

        趋势市策略:
        - bollinger_trend (趋势突破版)
        - ema_cross
        - macd_cross
        """
        if regime_info.regime == MarketRegime.RANGING:
            # 震荡市：使用综合评分 + MACD（已启用且适合震荡）
            strategies = ["composite_score", "macd_cross"]

        elif regime_info.regime == MarketRegime.TRENDING:
            # 趋势市：使用趋势跟踪策略
            strategies = [
                "bollinger_trend",
                "ema_cross",
                "macd_cross",
            ]

        else:  # TRANSITIONING
            # 过渡市：使用综合策略
            strategies = ["composite_score", "macd_cross", "ema_cross"]

        # 过滤：只返回已启用的策略
        enabled_strategies = [s for s in strategies if s in config.ENABLE_STRATEGIES]

        # 如果过滤后没有策略，使用所有已启用的策略
        if not enabled_strategies:
            logger.warning(f"市场状态{regime_info.regime.value}没有匹配的已启用策略，使用全部策略")
            enabled_strategies = config.ENABLE_STRATEGIES

        return enabled_strategies

    def should_trade(self, regime_info: RegimeInfo) -> tuple[bool, str]:
        """
        判断当前市场状态是否适合交易（优化版）
        返回: (是否交易, 原因)
        """
        # 极端波动时不交易
        if regime_info.volatility > config.HIGH_VOLATILITY_THRESHOLD * 1.5:
            return False, f"波动率过高({regime_info.volatility:.2%})"

        # 过渡市且置信度低时谨慎交易（阈值从0.5降低到0.4）
        if regime_info.regime == MarketRegime.TRANSITIONING and regime_info.confidence < config.TRANSITIONING_CONFIDENCE_THRESHOLD:
            return False, f"市场状态不明确(置信度{regime_info.confidence:.0%} < {config.TRANSITIONING_CONFIDENCE_THRESHOLD:.0%})"

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
    from core.trader import BitgetTrader

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
