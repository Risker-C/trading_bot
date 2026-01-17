from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

from config.settings import settings as config
from strategies.indicators import IndicatorCalculator, detect_market_state
from utils.logger_utils import get_logger

logger = get_logger("strategies")

class Signal(Enum):
    """交易信号枚举"""
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


@dataclass
class TradeSignal:
    """交易信号数据类"""
    signal: Signal
    strategy: str = ""
    reason: str = ""
    strength: float = 1.0  # 信号强度 0-1
    confidence: float = 1.0  # 置信度 0-1（新增）
    indicators: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.strategy:
            self.strategy = "unknown"


# ==================== 策略基类 ====================

class BaseStrategy(ABC):
    """策略基类"""

    name: str = "base"
    description: str = ""

    def __init__(self, df: pd.DataFrame, **kwargs):
        self.df = df
        self.ind = IndicatorCalculator(df)
        self.params = kwargs  # 保存优化参数供子类使用
    
    @abstractmethod
    def analyze(self) -> TradeSignal:
        """分析并返回交易信号"""
        pass
    
    def check_exit(self, position_side: str) -> TradeSignal:
        """检查退出信号（可选实现）"""
        return TradeSignal(Signal.HOLD, self.name)
    
    def get_indicators(self) -> Dict:
        """获取当前指标值"""
        return {}


# ==================== 布林带突破策略 ====================

class BollingerBreakthroughStrategy(BaseStrategy):
    """布林带突破策略"""
    
    name = "bollinger_breakthrough"
    description = "价格突破布林带上下轨产生信号"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.bb = self.ind.bollinger_bands(
            period=config.BB_PERIOD,
            std_dev=config.BB_STD_DEV
        )
        self.breakthrough_count = config.BB_BREAKTHROUGH_COUNT
    
    def analyze(self) -> TradeSignal:
        close = self.df['close']
        upper = self.bb['upper']
        lower = self.bb['lower']
        
        recent_closes = close.tail(self.breakthrough_count)
        recent_lowers = lower.tail(self.breakthrough_count)
        recent_uppers = upper.tail(self.breakthrough_count)
        
        # 检查是否连续突破下轨（做多信号）
        breakthrough_lower = all(
            recent_closes.iloc[i] < recent_lowers.iloc[i]
            for i in range(len(recent_closes))
        )
        
        # 检查是否连续突破上轨（做空信号）
        breakthrough_upper = all(
            recent_closes.iloc[i] > recent_uppers.iloc[i]
            for i in range(len(recent_closes))
        )
        
        # 计算信号强度（基于偏离程度）
        current_close = close.iloc[-1]
        middle = self.bb['middle'].iloc[-1]
        bandwidth = self.bb['bandwidth'].iloc[-1]
        
        deviation = abs(current_close - middle) / middle
        strength = min(deviation * 10, 1.0)
        
        indicators = {
            'close': current_close,
            'upper': upper.iloc[-1],
            'middle': middle,
            'lower': lower.iloc[-1],
            'bandwidth': bandwidth,
        }
        
        if breakthrough_lower:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"价格连续{self.breakthrough_count}根K线突破布林带下轨",
                strength=strength,
                indicators=indicators
            )
        
        if breakthrough_upper:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"价格连续{self.breakthrough_count}根K线突破布林带上轨",
                strength=strength,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        close = self.df['close']
        middle = self.bb['middle']
        
        recent_closes = close.tail(config.REVERSE_CANDLE_COUNT)
        recent_middles = middle.tail(config.REVERSE_CANDLE_COUNT)
        
        if position_side == 'long':
            # 多仓：价格回归中轨上方
            cross_above_middle = all(
                recent_closes.iloc[i] > recent_middles.iloc[i]
                for i in range(len(recent_closes))
            )
            if cross_above_middle:
                return TradeSignal(
                    Signal.CLOSE_LONG,
                    self.name,
                    "价格回归布林带中轨上方"
                )
        
        elif position_side == 'short':
            # 空仓：价格回归中轨下方
            cross_below_middle = all(
                recent_closes.iloc[i] < recent_middles.iloc[i]
                for i in range(len(recent_closes))
            )
            if cross_below_middle:
                return TradeSignal(
                    Signal.CLOSE_SHORT,
                    self.name,
                    "价格回归布林带中轨下方"
                )
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== 布林带趋势突破策略(新增)====================

class BollingerTrendStrategy(BaseStrategy):
    """布林带趋势突破策略 - 顺势交易版本"""

    name = "bollinger_trend"
    description = "价格突破布林带上轨做多,突破下轨做空(趋势跟踪)"

    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.bb = self.ind.bollinger_bands(
            period=config.BB_PERIOD,
            std_dev=config.BB_STD_DEV
        )
        self.breakthrough_count = config.BB_BREAKTHROUGH_COUNT

    def analyze(self) -> TradeSignal:
        close = self.df['close']
        upper = self.bb['upper']
        lower = self.bb['lower']
        volume = self.df['volume']

        recent_closes = close.tail(self.breakthrough_count)
        recent_lowers = lower.tail(self.breakthrough_count)
        recent_uppers = upper.tail(self.breakthrough_count)

        # 检查是否连续突破上轨(做多信号 - 趋势突破)
        breakthrough_upper = all(
            recent_closes.iloc[i] > recent_uppers.iloc[i]
            for i in range(len(recent_closes))
        )

        # 检查是否连续突破下轨(做空信号 - 趋势突破)
        breakthrough_lower = all(
            recent_closes.iloc[i] < recent_lowers.iloc[i]
            for i in range(len(recent_closes))
        )

        # 计算信号强度(基于偏离程度和成交量)
        current_close = close.iloc[-1]
        middle = self.bb['middle'].iloc[-1]
        bandwidth = self.bb['bandwidth'].iloc[-1]

        deviation = abs(current_close - middle) / middle

        # 成交量确认
        avg_volume = volume.tail(20).mean()
        volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 1.0
        volume_factor = min(volume_ratio / 1.5, 1.2)  # 放量加强信号

        strength = min(deviation * 10 * volume_factor, 1.0)

        indicators = {
            'close': current_close,
            'upper': upper.iloc[-1],
            'middle': middle,
            'lower': lower.iloc[-1],
            'bandwidth': bandwidth,
            'volume_ratio': volume_ratio,
        }

        # 趋势突破: 突破上轨做多
        if breakthrough_upper:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"价格突破布林带上轨,趋势向上(量比={volume_ratio:.2f})",
                strength=strength,
                confidence=min(volume_factor * 0.8, 1.0),
                indicators=indicators
            )

        # 趋势突破: 突破下轨做空
        if breakthrough_lower:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"价格突破布林带下轨,趋势向下(量比={volume_ratio:.2f})",
                strength=strength,
                confidence=min(volume_factor * 0.8, 1.0),
                indicators=indicators
            )

        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)

    def check_exit(self, position_side: str) -> TradeSignal:
        close = self.df['close']
        middle = self.bb['middle']
        upper = self.bb['upper']
        lower = self.bb['lower']

        current_close = close.iloc[-1]
        current_middle = middle.iloc[-1]

        if position_side == 'long':
            # 多仓: 价格回落到中轨或跌破下轨
            if current_close < current_middle:
                return TradeSignal(
                    Signal.CLOSE_LONG,
                    self.name,
                    "价格回落至布林带中轨下方"
                )

        elif position_side == 'short':
            # 空仓: 价格反弹到中轨或突破上轨
            if current_close > current_middle:
                return TradeSignal(
                    Signal.CLOSE_SHORT,
                    self.name,
                    "价格反弹至布林带中轨上方"
                )

        return TradeSignal(Signal.HOLD, self.name)


# ==================== RSI 背离策略 ====================

class RSIDivergenceStrategy(BaseStrategy):
    """RSI 背离策略"""
    
    name = "rsi_divergence"
    description = "RSI 超买超卖配合背离信号"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.rsi = self.ind.rsi(config.RSI_PERIOD)
    
    def analyze(self) -> TradeSignal:
        rsi = self.rsi
        close = self.df['close']
        
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        # 计算价格和RSI的趋势
        price_higher = close.iloc[-1] > close.iloc[-5]
        price_lower = close.iloc[-1] < close.iloc[-5]
        rsi_higher = current_rsi > rsi.iloc[-5]
        rsi_lower = current_rsi < rsi.iloc[-5]
        
        indicators = {
            'rsi': current_rsi,
            'rsi_prev': prev_rsi,
        }
        
        # 超卖 + 底背离 = 做多
        if current_rsi < config.RSI_OVERSOLD:
            if price_lower and rsi_higher:  # 价格新低，RSI抬高
                return TradeSignal(
                    Signal.LONG,
                    self.name,
                    f"RSI超卖({current_rsi:.1f})且底背离",
                    strength=0.8,
                    indicators=indicators
                )
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"RSI超卖({current_rsi:.1f})",
                strength=0.6,
                indicators=indicators
            )
        
        # 超买 + 顶背离 = 做空
        if current_rsi > config.RSI_OVERBOUGHT:
            if price_higher and rsi_lower:  # 价格新高，RSI降低
                return TradeSignal(
                    Signal.SHORT,
                    self.name,
                    f"RSI超买({current_rsi:.1f})且顶背离",
                    strength=0.8,
                    indicators=indicators
                )
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"RSI超买({current_rsi:.1f})",
                strength=0.6,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        current_rsi = self.rsi.iloc[-1]
        
        if position_side == 'long' and current_rsi > 50:
            return TradeSignal(Signal.CLOSE_LONG, self.name, "RSI回归中性区域")
        
        if position_side == 'short' and current_rsi < 50:
            return TradeSignal(Signal.CLOSE_SHORT, self.name, "RSI回归中性区域")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== MACD 交叉策略 ====================

class MACDCrossStrategy(BaseStrategy):
    """MACD 金叉死叉策略"""
    
    name = "macd_cross"
    description = "MACD 金叉做多，死叉做空"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.macd = self.ind.macd(
            fast=config.MACD_FAST,
            slow=config.MACD_SLOW,
            signal=config.MACD_SIGNAL
        )
    
    def analyze(self) -> TradeSignal:
        macd_line = self.macd['macd']
        signal_line = self.macd['signal']
        histogram = self.macd['histogram']
        
        # 判断金叉死叉
        crossover = self.macd['crossover'].iloc[-1]
        crossunder = self.macd['crossunder'].iloc[-1]
        
        # 判断MACD位置（零轴上下）
        above_zero = macd_line.iloc[-1] > 0
        below_zero = macd_line.iloc[-1] < 0
        
        # 计算信号强度（基于柱状图大小变化）
        hist_increasing = histogram.iloc[-1] > histogram.iloc[-2]
        strength = min(abs(histogram.iloc[-1]) / 100, 1.0)
        
        indicators = {
            'macd': macd_line.iloc[-1],
            'signal': signal_line.iloc[-1],
            'histogram': histogram.iloc[-1],
        }
        
        if crossover:
            reason = "MACD金叉"
            if above_zero:
                reason += "（零轴上方，趋势确认）"
                strength *= 1.2
            elif below_zero:
                reason += "（零轴下方，弱势反转）"
                strength *= 0.8  # 降低权重，避免在下跌趋势中盲目做多
            return TradeSignal(
                Signal.LONG,
                self.name,
                reason,
                strength=min(strength, 1.0),
                indicators=indicators
            )
        
        if crossunder:
            reason = "MACD死叉"
            if above_zero:
                reason += "（零轴上方，反转信号）"
                strength *= 1.2
            return TradeSignal(
                Signal.SHORT,
                self.name,
                reason,
                strength=min(strength, 1.0),
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        crossover = self.macd['crossover'].iloc[-1]
        crossunder = self.macd['crossunder'].iloc[-1]
        
        if position_side == 'long' and crossunder:
            return TradeSignal(Signal.CLOSE_LONG, self.name, "MACD死叉平多")
        
        if position_side == 'short' and crossover:
            return TradeSignal(Signal.CLOSE_SHORT, self.name, "MACD金叉平空")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== EMA 交叉策略 ====================

class EMACrossStrategy(BaseStrategy):
    """EMA 均线交叉策略"""
    
    name = "ema_cross"
    description = "短期EMA上穿长期EMA做多，下穿做空"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.ema_short = self.ind.ema(config.EMA_SHORT)
        self.ema_long = self.ind.ema(config.EMA_LONG)
    
    def analyze(self) -> TradeSignal:
        short = self.ema_short
        long = self.ema_long
        close = self.df['close']
        
        # 判断交叉
        cross_above = (short.iloc[-1] > long.iloc[-1]) and (short.iloc[-2] <= long.iloc[-2])
        cross_below = (short.iloc[-1] < long.iloc[-1]) and (short.iloc[-2] >= long.iloc[-2])
        
        # 趋势确认
        price_above_ema = close.iloc[-1] > short.iloc[-1]
        price_below_ema = close.iloc[-1] < short.iloc[-1]
        
        # 计算信号强度
        ema_diff_pct = abs(short.iloc[-1] - long.iloc[-1]) / long.iloc[-1]
        strength = min(ema_diff_pct * 50, 1.0)
        
        indicators = {
            'ema_short': short.iloc[-1],
            'ema_long': long.iloc[-1],
            'close': close.iloc[-1],
        }
        
        if cross_above and price_above_ema:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"EMA{config.EMA_SHORT}上穿EMA{config.EMA_LONG}",
                strength=strength,
                indicators=indicators
            )
        
        if cross_below and price_below_ema:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"EMA{config.EMA_SHORT}下穿EMA{config.EMA_LONG}",
                strength=strength,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        short = self.ema_short
        long = self.ema_long
        
        cross_above = (short.iloc[-1] > long.iloc[-1]) and (short.iloc[-2] <= long.iloc[-2])
        cross_below = (short.iloc[-1] < long.iloc[-1]) and (short.iloc[-2] >= long.iloc[-2])
        
        if position_side == 'long' and cross_below:
            return TradeSignal(Signal.CLOSE_LONG, self.name, "EMA死叉平多")
        
        if position_side == 'short' and cross_above:
            return TradeSignal(Signal.CLOSE_SHORT, self.name, "EMA金叉平空")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== KDJ 策略（新增 - 来自 Qbot）====================

class KDJStrategy(BaseStrategy):
    """KDJ 交叉策略"""
    
    name = "kdj_cross"
    description = "KDJ 金叉死叉配合超买超卖"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.kdj = self.ind.kdj(
            period=config.KDJ_PERIOD,
            signal_period=config.KDJ_SIGNAL_PERIOD
        )
    
    def analyze(self) -> TradeSignal:
        k = self.kdj['k']
        d = self.kdj['d']
        j = self.kdj['j']
        
        current_k = k.iloc[-1]
        current_d = d.iloc[-1]
        current_j = j.iloc[-1]
        
        crossover = self.kdj['crossover'].iloc[-1]
        crossunder = self.kdj['crossunder'].iloc[-1]
        
        indicators = {
            'k': current_k,
            'd': current_d,
            'j': current_j,
        }
        
        # K线在超卖区金叉
        if crossover and current_k < config.KDJ_OVERSOLD + 10:
            strength = 0.8 if current_j < 0 else 0.6
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"KDJ超卖区金叉(K={current_k:.1f}, D={current_d:.1f})",
                strength=strength,
                indicators=indicators
            )
        
        # K线在超买区死叉
        if crossunder and current_k > config.KDJ_OVERBOUGHT - 10:
            strength = 0.8 if current_j > 100 else 0.6
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"KDJ超买区死叉(K={current_k:.1f}, D={current_d:.1f})",
                strength=strength,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        k = self.kdj['k']
        d = self.kdj['d']
        
        current_k = k.iloc[-1]
        crossover = self.kdj['crossover'].iloc[-1]
        crossunder = self.kdj['crossunder'].iloc[-1]
        
        if position_side == 'long':
            if crossunder or current_k > config.KDJ_OVERBOUGHT:
                return TradeSignal(Signal.CLOSE_LONG, self.name, "KDJ死叉或超买")
        
        if position_side == 'short':
            if crossover or current_k < config.KDJ_OVERSOLD:
                return TradeSignal(Signal.CLOSE_SHORT, self.name, "KDJ金叉或超卖")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== ADX 趋势策略（新增 - 来自 Qbot）====================

class ADXTrendStrategy(BaseStrategy):
    """ADX 趋势跟踪策略"""
    
    name = "adx_trend"
    description = "ADX 判断趋势强度，DI 判断方向"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.adx_data = self.ind.adx(config.ADX_PERIOD)
        self.ema_short = self.ind.ema(config.EMA_SHORT)
        self.ema_long = self.ind.ema(config.EMA_LONG)
    
    def analyze(self) -> TradeSignal:
        adx = self.adx_data['adx']
        plus_di = self.adx_data['plus_di']
        minus_di = self.adx_data['minus_di']
        
        current_adx = adx.iloc[-1]
        current_plus_di = plus_di.iloc[-1]
        current_minus_di = minus_di.iloc[-1]
        
        # ADX 上升表示趋势增强
        adx_rising = adx.iloc[-1] > adx.iloc[-3]
        
        # 趋势强度足够
        strong_trend = current_adx > config.ADX_TREND_THRESHOLD
        
        indicators = {
            'adx': current_adx,
            'plus_di': current_plus_di,
            'minus_di': current_minus_di,
            'adx_rising': adx_rising,
        }
        
        if not strong_trend:
            return TradeSignal(
                Signal.HOLD, 
                self.name, 
                f"趋势不明显(ADX={current_adx:.1f})",
                indicators=indicators
            )
        
        # +DI 上穿 -DI 且 ADX 上升
        di_cross_up = (
            current_plus_di > current_minus_di and
            plus_di.iloc[-2] <= minus_di.iloc[-2]
        )
        
        # -DI 上穿 +DI 且 ADX 上升
        di_cross_down = (
            current_minus_di > current_plus_di and
            minus_di.iloc[-2] <= plus_di.iloc[-2]
        )
        
        strength = min(current_adx / 50, 1.0)
        
        if di_cross_up and adx_rising:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"ADX趋势确认做多(ADX={current_adx:.1f}, +DI={current_plus_di:.1f})",
                strength=strength,
                indicators=indicators
            )
        
        if di_cross_down and adx_rising:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"ADX趋势确认做空(ADX={current_adx:.1f}, -DI={current_minus_di:.1f})",
                strength=strength,
                indicators=indicators
            )
        
        # 已有趋势中的顺势信号
        if current_plus_di > current_minus_di + 10 and adx_rising:
            ema_bullish = self.ema_short.iloc[-1] > self.ema_long.iloc[-1]
            if ema_bullish:
                return TradeSignal(
                    Signal.LONG,
                    self.name,
                    f"强势上涨趋势(ADX={current_adx:.1f})",
                    strength=strength * 0.8,
                    indicators=indicators
                )
        
        if current_minus_di > current_plus_di + 10 and adx_rising:
            ema_bearish = self.ema_short.iloc[-1] < self.ema_long.iloc[-1]
            if ema_bearish:
                return TradeSignal(
                    Signal.SHORT,
                    self.name,
                    f"强势下跌趋势(ADX={current_adx:.1f})",
                    strength=strength * 0.8,
                    indicators=indicators
                )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        adx = self.adx_data['adx']
        plus_di = self.adx_data['plus_di']
        minus_di = self.adx_data['minus_di']
        
        current_adx = adx.iloc[-1]
        adx_falling = adx.iloc[-1] < adx.iloc[-3]
        
        # ADX 下降表示趋势减弱
        if adx_falling and current_adx < config.ADX_TREND_THRESHOLD:
            if position_side == 'long':
                return TradeSignal(Signal.CLOSE_LONG, self.name, "趋势减弱")
            if position_side == 'short':
                return TradeSignal(Signal.CLOSE_SHORT, self.name, "趋势减弱")
        
        # DI 反转
        if position_side == 'long' and minus_di.iloc[-1] > plus_di.iloc[-1]:
            return TradeSignal(Signal.CLOSE_LONG, self.name, "-DI 超过 +DI")
        
        if position_side == 'short' and plus_di.iloc[-1] > minus_di.iloc[-1]:
            return TradeSignal(Signal.CLOSE_SHORT, self.name, "+DI 超过 -DI")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== 成交量突破策略（新增 - 来自 Qbot）====================

class VolumeBreakoutStrategy(BaseStrategy):
    """成交量突破策略"""
    
    name = "volume_breakout"
    description = "放量突破关键位置"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.volume_ratio = self.ind.volume_ratio(20)
        self.bb = self.ind.bollinger_bands()
        self.atr = self.ind.atr()
    
    def analyze(self) -> TradeSignal:
        close = self.df['close']
        volume = self.df['volume']
        
        current_vol_ratio = self.volume_ratio.iloc[-1]
        current_close = close.iloc[-1]
        prev_close = close.iloc[-2]
        
        upper = self.bb['upper'].iloc[-1]
        lower = self.bb['lower'].iloc[-1]
        
        indicators = {
            'volume_ratio': current_vol_ratio,
            'close': current_close,
            'bb_upper': upper,
            'bb_lower': lower,
        }
        
        # 放量标准：成交量是均量的 1.5 倍以上
        high_volume = current_vol_ratio > 1.5
        
        if not high_volume:
            return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
        
        # 放量突破上轨
        if current_close > upper and prev_close <= upper:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"放量突破布林上轨(量比={current_vol_ratio:.2f})",
                strength=min(current_vol_ratio / 3, 1.0),
                indicators=indicators
            )
        
        # 放量跌破下轨
        if current_close < lower and prev_close >= lower:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"放量跌破布林下轨(量比={current_vol_ratio:.2f})",
                strength=min(current_vol_ratio / 3, 1.0),
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)


# ==================== 多时间周期策略（新增 - 来自 Qbot）====================

class MultiTimeframeStrategy(BaseStrategy):
    """多时间周期综合策略"""
    
    name = "multi_timeframe"
    description = "综合多个时间周期的信号"
    
    def __init__(self, df: pd.DataFrame, timeframe_data: Dict[str, pd.DataFrame] = None):
        super().__init__(df)
        self.timeframe_data = timeframe_data or {}
    
    def set_timeframe_data(self, timeframe_data: Dict[str, pd.DataFrame]):
        """设置多时间周期数据"""
        self.timeframe_data = timeframe_data
    
    def _analyze_single_timeframe(self, df: pd.DataFrame) -> Tuple[int, float]:
        """
        分析单个时间周期
        返回: (方向: 1多/-1空/0中性, 强度: 0-1)
        """
        if len(df) < 50:
            return 0, 0
        
        ind = IndicatorCalculator(df)
        
        # RSI
        rsi = ind.rsi().iloc[-1]
        rsi_signal = 1 if rsi < 40 else (-1 if rsi > 60 else 0)
        
        # MACD
        macd = ind.macd()
        macd_signal = 1 if macd['histogram'].iloc[-1] > 0 else -1
        
        # EMA
        ema_short = ind.ema(9).iloc[-1]
        ema_long = ind.ema(21).iloc[-1]
        ema_signal = 1 if ema_short > ema_long else -1
        
        # 趋势方向
        trend = ind.trend_direction().iloc[-1]
        
        # 综合
        total_signal = rsi_signal + macd_signal + ema_signal + trend
        direction = 1 if total_signal > 1 else (-1 if total_signal < -1 else 0)
        strength = abs(total_signal) / 4
        
        return direction, strength
    
    def analyze(self) -> TradeSignal:
        if not self.timeframe_data:
            # 只有单一时间周期，使用基础分析
            direction, strength = self._analyze_single_timeframe(self.df)
            
            if direction > 0 and strength > 0.5:
                return TradeSignal(
                    Signal.LONG, self.name, 
                    "多时间周期看多", 
                    strength=strength
                )
            elif direction < 0 and strength > 0.5:
                return TradeSignal(
                    Signal.SHORT, self.name, 
                    "多时间周期看空", 
                    strength=strength
                )
            return TradeSignal(Signal.HOLD, self.name)
        
        # 分析每个时间周期
        signals = {}
        for tf, tf_df in self.timeframe_data.items():
            direction, strength = self._analyze_single_timeframe(tf_df)
            weight = config.TIMEFRAME_WEIGHTS.get(tf, 0.3)
            signals[tf] = {
                'direction': direction,
                'strength': strength,
                'weight': weight,
            }
        
        # 加权综合
        weighted_direction = sum(
            s['direction'] * s['strength'] * s['weight']
            for s in signals.values()
        )
        total_weight = sum(s['weight'] for s in signals.values())
        
        if total_weight > 0:
            weighted_direction /= total_weight
        
        avg_strength = sum(s['strength'] * s['weight'] for s in signals.values()) / total_weight
        
        indicators = {
            'weighted_direction': weighted_direction,
            'avg_strength': avg_strength,
            'signals': signals,
        }
        
        # 生成信号
        if weighted_direction > 0.3 and avg_strength > 0.5:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"多周期共振看多(方向={weighted_direction:.2f})",
                strength=avg_strength,
                confidence=abs(weighted_direction),
                indicators=indicators
            )
        
        if weighted_direction < -0.3 and avg_strength > 0.5:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"多周期共振看空(方向={weighted_direction:.2f})",
                strength=avg_strength,
                confidence=abs(weighted_direction),
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)


# ==================== 网格策略（新增 - 来自 Qbot）====================

class GridStrategy(BaseStrategy):
    """网格交易策略"""
    
    name = "grid"
    description = "在设定价格区间内网格交易"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.grid_lines = []
        self._calculate_grid()
    
    def _calculate_grid(self):
        """计算网格线"""
        close = self.df['close']
        
        # 自动计算上下界
        if config.GRID_UPPER_PRICE == 0 or config.GRID_LOWER_PRICE == 0:
            bb = self.ind.bollinger_bands(period=20, std_dev=2.5)
            upper_price = bb['upper'].iloc[-1]
            lower_price = bb['lower'].iloc[-1]
        else:
            upper_price = config.GRID_UPPER_PRICE
            lower_price = config.GRID_LOWER_PRICE
        
        # 生成网格线
        if config.GRID_TYPE == "arithmetic":
            # 等差网格
            if config.GRID_NUM == 0:
                logger.error("网格数量不能为0")
                self.grid_lines = [lower_price, upper_price]
            else:
                step = (upper_price - lower_price) / config.GRID_NUM
                self.grid_lines = [lower_price + i * step for i in range(config.GRID_NUM + 1)]
        else:
            # 等比网格
            if config.GRID_NUM == 0 or lower_price == 0:
                logger.error(f"网格数量不能为0且下界价格不能为0 (GRID_NUM={config.GRID_NUM}, lower_price={lower_price})")
                self.grid_lines = [lower_price, upper_price]
            else:
                ratio = (upper_price / lower_price) ** (1 / config.GRID_NUM)
                self.grid_lines = [lower_price * (ratio ** i) for i in range(config.GRID_NUM + 1)]
        
        self.grid_upper = upper_price
        self.grid_lower = lower_price
    
    def _find_grid_position(self, price: float) -> int:
        """找到价格所在的网格位置"""
        for i, grid_price in enumerate(self.grid_lines):
            if price < grid_price:
                return i - 1
        return len(self.grid_lines) - 1
    
    def analyze(self) -> TradeSignal:
        current_price = self.df['close'].iloc[-1]
        prev_price = self.df['close'].iloc[-2]
        
        current_grid = self._find_grid_position(current_price)
        prev_grid = self._find_grid_position(prev_price)
        
        indicators = {
            'current_price': current_price,
            'current_grid': current_grid,
            'grid_lines': self.grid_lines,
            'grid_upper': self.grid_upper,
            'grid_lower': self.grid_lower,
        }
        
        # 价格超出网格范围
        if current_price > self.grid_upper or current_price < self.grid_lower:
            return TradeSignal(
                Signal.HOLD, 
                self.name, 
                "价格超出网格范围",
                indicators=indicators
            )
        
        # 向下穿越网格线 - 买入
        if current_grid < prev_grid:
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"价格下穿网格线{current_grid}({self.grid_lines[current_grid]:.2f})",
                strength=0.5,
                indicators=indicators
            )
        
        # 向上穿越网格线 - 卖出（平多或开空）
        if current_grid > prev_grid:
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"价格上穿网格线{current_grid}({self.grid_lines[current_grid]:.2f})",
                strength=0.5,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)


# ==================== 综合评分策略（新增 - 来自 Qbot）====================

class CompositeScoreStrategy(BaseStrategy):
    """综合评分策略 - 结合多个指标打分"""
    
    name = "composite_score"
    description = "综合多个技术指标进行评分决策"
    
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
    
    def _calculate_scores(self) -> Dict[str, float]:
        """
        计算各指标得分
        返回: 每个指标的得分 (-1 到 1)
        """
        scores = {}
        
        # 1. RSI 得分
        rsi = self.ind.rsi().iloc[-1]
        if rsi < 30:
            scores['rsi'] = 1.0
        elif rsi < 40:
            scores['rsi'] = 0.5
        elif rsi > 70:
            scores['rsi'] = -1.0
        elif rsi > 60:
            scores['rsi'] = -0.5
        else:
            scores['rsi'] = 0
        
        # 2. MACD 得分
        macd = self.ind.macd()
        hist = macd['histogram'].iloc[-1]
        hist_prev = macd['histogram'].iloc[-2]
        
        if hist > 0 and hist > hist_prev:
            scores['macd'] = 1.0
        elif hist > 0:
            scores['macd'] = 0.5
        elif hist < 0 and hist < hist_prev:
            scores['macd'] = -1.0
        elif hist < 0:
            scores['macd'] = -0.5
        else:
            scores['macd'] = 0
        
        # 3. 布林带得分
        bb = self.ind.bollinger_bands()
        close = self.df['close'].iloc[-1]
        percent_b = bb['percent_b'].iloc[-1]
        
        if percent_b < 0:
            scores['bollinger'] = 1.0
        elif percent_b < 0.2:
            scores['bollinger'] = 0.5
        elif percent_b > 1:
            scores['bollinger'] = -1.0
        elif percent_b > 0.8:
            scores['bollinger'] = -0.5
        else:
            scores['bollinger'] = 0
        
        # 4. KDJ 得分
        kdj = self.ind.kdj()
        k = kdj['k'].iloc[-1]
        j = kdj['j'].iloc[-1]
        
        if k < 20 and j < 0:
            scores['kdj'] = 1.0
        elif k < 30:
            scores['kdj'] = 0.5
        elif k > 80 and j > 100:
            scores['kdj'] = -1.0
        elif k > 70:
            scores['kdj'] = -0.5
        else:
            scores['kdj'] = 0
        
        # 5. 趋势得分
        trend = self.ind.trend_direction().iloc[-1]
        trend_strength = self.ind.trend_strength().iloc[-1]
        scores['trend'] = trend * trend_strength
        
        # 6. ADX 得分（趋势强度）
        adx_data = self.ind.adx()
        adx = adx_data['adx'].iloc[-1]
        plus_di = adx_data['plus_di'].iloc[-1]
        minus_di = adx_data['minus_di'].iloc[-1]
        
        if adx > 25:
            if plus_di > minus_di:
                scores['adx'] = min(adx / 50, 1.0)
            else:
                scores['adx'] = -min(adx / 50, 1.0)
        else:
            scores['adx'] = 0
        
        # 7. 成交量得分
        vol_ratio = self.ind.volume_ratio().iloc[-1]
        price_change = (self.df['close'].iloc[-1] - self.df['close'].iloc[-2]) / self.df['close'].iloc[-2]
        
        if vol_ratio > 1.5:
            scores['volume'] = 1.0 if price_change > 0 else -1.0
        elif vol_ratio > 1.2:
            scores['volume'] = 0.5 if price_change > 0 else -0.5
        else:
            scores['volume'] = 0
        
        return scores
    
    def analyze(self) -> TradeSignal:
        scores = self._calculate_scores()
        
        # 定义权重
        weights = {
            'rsi': 0.15,
            'macd': 0.20,
            'bollinger': 0.15,
            'kdj': 0.10,
            'trend': 0.20,
            'adx': 0.10,
            'volume': 0.10,
        }
        
        # 计算加权总分
        total_score = sum(scores.get(k, 0) * v for k, v in weights.items())
        
        # 计算一致性（多少指标同向）
        positive_count = sum(1 for s in scores.values() if s > 0)
        negative_count = sum(1 for s in scores.values() if s < 0)
        consistency = max(positive_count, negative_count) / len(scores)
        
        indicators = {
            'scores': scores,
            'total_score': total_score,
            'consistency': consistency,
        }
        
        # 生成信号
        threshold = 0.3
        
        if total_score > threshold and consistency > 0.5:
            strength = min(abs(total_score), 1.0)
            return TradeSignal(
                Signal.LONG,
                self.name,
                f"综合评分看多(得分={total_score:.2f}, 一致性={consistency:.0%})",
                strength=strength,
                confidence=consistency,
                indicators=indicators
            )
        
        if total_score < -threshold and consistency > 0.5:
            strength = min(abs(total_score), 1.0)
            return TradeSignal(
                Signal.SHORT,
                self.name,
                f"综合评分看空(得分={total_score:.2f}, 一致性={consistency:.0%})",
                strength=strength,
                confidence=consistency,
                indicators=indicators
            )
        
        return TradeSignal(Signal.HOLD, self.name, indicators=indicators)
    
    def check_exit(self, position_side: str) -> TradeSignal:
        scores = self._calculate_scores()
        total_score = sum(scores.values()) / len(scores)
        
        if position_side == 'long' and total_score < -0.2:
            return TradeSignal(Signal.CLOSE_LONG, self.name, "综合评分转空")
        
        if position_side == 'short' and total_score > 0.2:
            return TradeSignal(Signal.CLOSE_SHORT, self.name, "综合评分转多")
        
        return TradeSignal(Signal.HOLD, self.name)


# ==================== 策略注册表 ====================

STRATEGY_MAP: Dict[str, type] = {
    "bollinger_breakthrough": BollingerBreakthroughStrategy,
    "bollinger_trend": BollingerTrendStrategy,  # 新增: 趋势突破版本
    "rsi_divergence": RSIDivergenceStrategy,
    "macd_cross": MACDCrossStrategy,
    "ema_cross": EMACrossStrategy,
    "kdj_cross": KDJStrategy,
    "adx_trend": ADXTrendStrategy,
    "volume_breakout": VolumeBreakoutStrategy,
    "multi_timeframe": MultiTimeframeStrategy,
    "grid": GridStrategy,
    "composite_score": CompositeScoreStrategy,
}


def get_strategy(name: str, df: pd.DataFrame, **kwargs) -> BaseStrategy:
    """获取策略实例"""
    if name not in STRATEGY_MAP:
        raise ValueError(f"未知策略: {name}")
    return STRATEGY_MAP[name](df, **kwargs)


def analyze_all_strategies(
    df: pd.DataFrame, 
    strategy_names: List[str],
    min_strength: float = 0.5,
    min_confidence: float = 0.5
) -> List[TradeSignal]:
    """
    运行多个策略并返回所有有效信号
    新增: 过滤低强度和低置信度信号
    """
    signals = []
    
    for name in strategy_names:
        if name not in STRATEGY_MAP:
            continue
        
        try:
            strategy = get_strategy(name, df)
            signal = strategy.analyze()
            
            if signal.signal in [Signal.LONG, Signal.SHORT]:
                # 过滤低质量信号
                if signal.strength >= min_strength and signal.confidence >= min_confidence:
                    signals.append(signal)
        except Exception as e:
            print(f"策略 {name} 执行失败: {e}")
    
    # 按信号强度排序
    signals.sort(key=lambda x: x.strength * x.confidence, reverse=True)
    
    return signals


def get_consensus_signal(
    df: pd.DataFrame,
    strategy_names: List[str],
    min_agreement: float = 0.6
) -> Optional[TradeSignal]:
    """
    获取共识信号（新增 - 来自 Qbot）
    只有当多数策略同向时才生成信号
    """
    signals = []
    
    for name in strategy_names:
        if name not in STRATEGY_MAP:
            continue
        try:
            strategy = get_strategy(name, df)
            signal = strategy.analyze()
            signals.append(signal)
        except (KeyError, ValueError, AttributeError) as e:
            logger.warning(f"策略 {name} 分析失败: {e}")
            pass
    
    if not signals:
        return None
    
    # 统计多空信号
    long_count = sum(1 for s in signals if s.signal == Signal.LONG)
    short_count = sum(1 for s in signals if s.signal == Signal.SHORT)
    total = len(signals)
    
    # 计算平均强度
    long_signals = [s for s in signals if s.signal == Signal.LONG]
    short_signals = [s for s in signals if s.signal == Signal.SHORT]
    
    if long_count / total >= min_agreement and long_signals:
        avg_strength = sum(s.strength for s in long_signals) / len(long_signals)
        return TradeSignal(
            Signal.LONG,
            "consensus",
            f"共识做多({long_count}/{total}个策略)",
            strength=avg_strength,
            confidence=long_count / total,
            indicators={'long_count': long_count, 'total': total}
        )
    
    if short_count / total >= min_agreement and short_signals:
        avg_strength = sum(s.strength for s in short_signals) / len(short_signals)
        return TradeSignal(
            Signal.SHORT,
            "consensus",
            f"共识做空({short_count}/{total}个策略)",
            strength=avg_strength,
            confidence=short_count / total,
            indicators={'short_count': short_count, 'total': total}
        )
    
    return None
