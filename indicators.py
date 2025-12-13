import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict, List


# ==================== 基础移动平均 ====================

def calc_sma(data: pd.Series, period: int) -> pd.Series:
    """简单移动平均线"""
    return data.rolling(window=period).mean()


def calc_ema(data: pd.Series, period: int) -> pd.Series:
    """指数移动平均线"""
    return data.ewm(span=period, adjust=False).mean()


def calc_wma(data: pd.Series, period: int) -> pd.Series:
    """加权移动平均线（新增）"""
    weights = np.arange(1, period + 1)
    return data.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


# ==================== 布林带 ====================

def calc_bollinger_bands(
    close: pd.Series, 
    period: int = 20, 
    std_dev: float = 2
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算布林带
    返回: (上轨, 中轨, 下轨)
    """
    middle = calc_sma(close, period)
    std = close.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower


def calc_bollinger_bandwidth(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2
) -> pd.Series:
    """计算布林带宽度（新增 - 来自 Qbot）"""
    upper, middle, lower = calc_bollinger_bands(close, period, std_dev)
    return (upper - lower) / middle * 100


def calc_bollinger_percent_b(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2
) -> pd.Series:
    """计算 %B 指标（新增 - 来自 Qbot）"""
    upper, middle, lower = calc_bollinger_bands(close, period, std_dev)
    return (close - lower) / (upper - lower)


# ==================== RSI ====================

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI 相对强弱指标"""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_stoch_rsi(
    close: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """计算 Stochastic RSI（新增 - 来自 Qbot）"""
    rsi = calc_rsi(close, rsi_period)
    
    stoch_rsi = (rsi - rsi.rolling(stoch_period).min()) / \
                (rsi.rolling(stoch_period).max() - rsi.rolling(stoch_period).min())
    
    k = stoch_rsi.rolling(k_period).mean() * 100
    d = k.rolling(d_period).mean()
    
    return k, d


# ==================== MACD ====================

def calc_macd(
    close: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算 MACD
    返回: (MACD线, 信号线, 柱状图)
    """
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ==================== KDJ（新增 - 来自 Qbot）====================

def calc_kdj(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 9,
    signal_period: int = 3
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算 KDJ 指标
    返回: (K, D, J)
    """
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    rsv = rsv.fillna(50)
    
    k = rsv.ewm(com=signal_period - 1, adjust=False).mean()
    d = k.ewm(com=signal_period - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j


# ==================== ADX/DMI（新增 - 来自 Qbot）====================

def calc_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算 ADX 和 DMI 指标
    返回: (ADX, +DI, -DI)
    """
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)
    
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    
    # ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    return adx, plus_di, minus_di


# ==================== 威廉指标（新增）====================

def calc_williams_r(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """计算威廉指标 %R"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    
    wr = (highest_high - close) / (highest_high - lowest_low) * -100
    return wr


# ==================== OBV 成交量指标（新增 - 来自 Qbot）====================

def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """计算 OBV 能量潮"""
    direction = np.where(close > close.shift(1), 1, 
                np.where(close < close.shift(1), -1, 0))
    obv = (volume * direction).cumsum()
    return pd.Series(obv, index=close.index)


def calc_obv_divergence(
    close: pd.Series,
    volume: pd.Series,
    period: int = 14
) -> pd.Series:
    """计算 OBV 背离（新增）"""
    obv = calc_obv(close, volume)
    
    price_trend = (close - close.shift(period)) / close.shift(period)
    obv_trend = (obv - obv.shift(period)) / (obv.shift(period).abs() + 1)
    
    # 背离度：价格和OBV趋势不一致时为正
    divergence = price_trend * obv_trend
    divergence = np.where(divergence < 0, -divergence, 0)
    
    return pd.Series(divergence, index=close.index)


# ==================== VWAP（新增 - 来自 Qbot）====================

def calc_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series
) -> pd.Series:
    """计算 VWAP 成交量加权平均价"""
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    return vwap


def calc_vwap_bands(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    std_dev: float = 2
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """计算 VWAP 带（新增）"""
    vwap = calc_vwap(high, low, close, volume)
    typical_price = (high + low + close) / 3
    
    squared_diff = ((typical_price - vwap) ** 2 * volume).cumsum() / volume.cumsum()
    std = np.sqrt(squared_diff)
    
    upper = vwap + std * std_dev
    lower = vwap - std * std_dev
    
    return upper, vwap, lower


# ==================== ATR ====================

def calc_atr(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """计算 ATR 平均真实波幅"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calc_atr_percent(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """计算 ATR 百分比（新增）"""
    atr = calc_atr(high, low, close, period)
    return atr / close * 100


# ==================== 波动率指标（新增 - 来自 Qbot）====================

def calc_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """计算历史波动率"""
    log_returns = np.log(close / close.shift(1))
    volatility = log_returns.rolling(window=period).std() * np.sqrt(252)
    return volatility


def calc_volatility_ratio(
    close: pd.Series,
    short_period: int = 5,
    long_period: int = 20
) -> pd.Series:
    """计算波动率比率（新增）"""
    short_vol = calc_volatility(close, short_period)
    long_vol = calc_volatility(close, long_period)
    return short_vol / long_vol


def calc_chaikin_volatility(
    high: pd.Series,
    low: pd.Series,
    period: int = 10,
    roc_period: int = 10
) -> pd.Series:
    """计算 Chaikin 波动率（新增 - 来自 Qbot）"""
    hl_ema = calc_ema(high - low, period)
    cv = (hl_ema - hl_ema.shift(roc_period)) / hl_ema.shift(roc_period) * 100
    return cv


# ==================== 趋势强度指标（新增 - 来自 Qbot）====================

def calc_trend_strength(
    close: pd.Series,
    period: int = 20
) -> pd.Series:
    """
    计算趋势强度 (0-1)
    基于价格与均线的偏离程度和方向一致性
    """
    sma = calc_sma(close, period)
    
    # 偏离度
    deviation = (close - sma) / sma
    
    # 方向一致性（最近N根K线的涨跌方向）
    changes = close.diff()
    direction_consistency = changes.rolling(period).apply(
        lambda x: abs(sum(np.sign(x))) / len(x), raw=True
    )
    
    # 综合趋势强度
    trend_strength = abs(deviation) * direction_consistency
    
    # 归一化到 0-1
    trend_strength = trend_strength.clip(0, 1)
    
    return trend_strength


def calc_trend_direction(
    close: pd.Series,
    short_period: int = 10,
    long_period: int = 30
) -> pd.Series:
    """
    计算趋势方向
    返回: 1(上升), -1(下降), 0(横盘)
    """
    short_ma = calc_ema(close, short_period)
    long_ma = calc_ema(close, long_period)
    
    trend = np.where(
        short_ma > long_ma * 1.001, 1,
        np.where(short_ma < long_ma * 0.999, -1, 0)
    )
    
    return pd.Series(trend, index=close.index)


# ==================== 支撑阻力位（新增 - 来自 Qbot）====================

def calc_pivot_points(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series
) -> Dict[str, float]:
    """计算枢轴点支撑阻力位"""
    h = high.iloc[-1]
    l = low.iloc[-1]
    c = close.iloc[-1]
    
    pivot = (h + l + c) / 3
    
    return {
        'pivot': pivot,
        'r1': 2 * pivot - l,
        'r2': pivot + (h - l),
        'r3': h + 2 * (pivot - l),
        's1': 2 * pivot - h,
        's2': pivot - (h - l),
        's3': l - 2 * (h - pivot),
    }


def calc_support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
    num_levels: int = 3
) -> Dict[str, List[float]]:
    """
    计算支撑阻力位（基于历史高低点）
    """
    recent_high = high.tail(period)
    recent_low = low.tail(period)
    current_price = close.iloc[-1]
    
    # 找出局部高点和低点
    all_prices = pd.concat([recent_high, recent_low]).sort_values()
    
    # 分为支撑位（低于当前价）和阻力位（高于当前价）
    supports = all_prices[all_prices < current_price].tail(num_levels).tolist()
    resistances = all_prices[all_prices > current_price].head(num_levels).tolist()
    
    return {
        'supports': supports,
        'resistances': resistances,
        'current': current_price,
    }


# ==================== 成交量分析（新增）====================

def calc_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """计算成交量均线"""
    return calc_sma(volume, period)


def calc_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """计算量比"""
    return volume / calc_sma(volume, period)


def calc_mfi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 14
) -> pd.Series:
    """计算 MFI 资金流量指标（新增 - 来自 Qbot）"""
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume
    
    positive_flow = np.where(
        typical_price > typical_price.shift(1),
        raw_money_flow, 0
    )
    negative_flow = np.where(
        typical_price < typical_price.shift(1),
        raw_money_flow, 0
    )
    
    positive_flow = pd.Series(positive_flow, index=close.index)
    negative_flow = pd.Series(negative_flow, index=close.index)
    
    positive_sum = positive_flow.rolling(period).sum()
    negative_sum = negative_flow.rolling(period).sum()
    
    mfi = 100 - (100 / (1 + positive_sum / negative_sum))
    return mfi


# ==================== K线形态识别 ====================

def detect_candle_pattern(df: pd.DataFrame) -> str:
    """
    检测K线形态
    返回: 'bullish' / 'bearish' / 'neutral' / 具体形态名
    """
    if len(df) < 3:
        return 'neutral'
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]
    
    # 基础判断
    is_bullish = last['close'] > last['open']
    is_bearish = last['close'] < last['open']
    
    body_size = abs(last['close'] - last['open'])
    total_range = last['high'] - last['low']
    
    if total_range == 0:
        return 'neutral'
    
    body_ratio = body_size / total_range
    upper_shadow = last['high'] - max(last['close'], last['open'])
    lower_shadow = min(last['close'], last['open']) - last['low']
    
    # 吞没形态
    if is_bullish:
        if (last['open'] < prev['close'] and 
            last['close'] > prev['open'] and
            prev['close'] < prev['open']):
            return 'bullish_engulfing'
    
    if is_bearish:
        if (last['open'] > prev['close'] and 
            last['close'] < prev['open'] and
            prev['close'] > prev['open']):
            return 'bearish_engulfing'
    
    # 锤子线（新增）
    if lower_shadow > body_size * 2 and upper_shadow < body_size * 0.5:
        return 'hammer' if is_bullish else 'hanging_man'
    
    # 倒锤子（新增）
    if upper_shadow > body_size * 2 and lower_shadow < body_size * 0.5:
        return 'inverted_hammer' if is_bullish else 'shooting_star'
    
    # 十字星（新增）
    if body_ratio < 0.1:
        if lower_shadow > body_size and upper_shadow > body_size:
            return 'doji'
        elif lower_shadow > body_size * 2:
            return 'dragonfly_doji'
        elif upper_shadow > body_size * 2:
            return 'gravestone_doji'
    
    # 早晨之星（新增）
    if len(df) >= 3:
        if (prev2['close'] < prev2['open'] and  # 第一根阴线
            abs(prev['close'] - prev['open']) < (prev2['high'] - prev2['low']) * 0.3 and  # 第二根小实体
            is_bullish and last['close'] > (prev2['open'] + prev2['close']) / 2):  # 第三根阳线收复一半
            return 'morning_star'
    
    # 黄昏之星（新增）
    if len(df) >= 3:
        if (prev2['close'] > prev2['open'] and  # 第一根阳线
            abs(prev['close'] - prev['open']) < (prev2['high'] - prev2['low']) * 0.3 and  # 第二根小实体
            is_bearish and last['close'] < (prev2['open'] + prev2['close']) / 2):  # 第三根阴线收复一半
            return 'evening_star'
    
    # 三只乌鸦/三白兵（新增）
    if len(df) >= 3:
        three_bearish = all(df.iloc[i]['close'] < df.iloc[i]['open'] for i in range(-3, 0))
        three_bullish = all(df.iloc[i]['close'] > df.iloc[i]['open'] for i in range(-3, 0))
        
        if three_bearish:
            return 'three_black_crows'
        if three_bullish:
            return 'three_white_soldiers'
    
    if is_bullish:
        return 'bullish'
    elif is_bearish:
        return 'bearish'
    
    return 'neutral'


# ==================== 市场状态识别（新增 - 来自 Qbot）====================

def detect_market_state(
    df: pd.DataFrame,
    atr_period: int = 14,
    adx_period: int = 14,
    adx_threshold: float = 25
) -> Dict[str, any]:
    """
    识别市场状态
    返回: {
        'state': 'trending_up' / 'trending_down' / 'ranging' / 'volatile',
        'strength': 0-1,
        'adx': float,
        'volatility': float,
    }
    """
    close = df['close']
    high = df['high']
    low = df['low']
    
    # 计算 ADX
    adx, plus_di, minus_di = calc_adx(high, low, close, adx_period)
    current_adx = adx.iloc[-1]
    
    # 计算波动率
    atr = calc_atr(high, low, close, atr_period)
    atr_percent = atr.iloc[-1] / close.iloc[-1] * 100
    
    # 计算趋势方向
    trend_direction = calc_trend_direction(close)
    current_direction = trend_direction.iloc[-1]
    
    # 判断市场状态
    if current_adx > adx_threshold:
        if current_direction > 0:
            state = 'trending_up'
        elif current_direction < 0:
            state = 'trending_down'
        else:
            state = 'ranging'
    else:
        if atr_percent > 3:  # 高波动
            state = 'volatile'
        else:
            state = 'ranging'
    
    # 计算强度
    strength = min(current_adx / 50, 1.0)
    
    return {
        'state': state,
        'strength': strength,
        'adx': current_adx,
        'plus_di': plus_di.iloc[-1],
        'minus_di': minus_di.iloc[-1],
        'volatility': atr_percent,
        'trend_direction': current_direction,
    }


# ==================== 综合指标计算器 ====================

class IndicatorCalculator:
    """技术指标计算器"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.close = df['close']
        self.high = df['high']
        self.low = df['low']
        self.open = df['open']
        self.volume = df.get('volume', pd.Series([0] * len(df)))
    
    def sma(self, period: int) -> pd.Series:
        return calc_sma(self.close, period)
    
    def ema(self, period: int) -> pd.Series:
        return calc_ema(self.close, period)
    
    def wma(self, period: int) -> pd.Series:
        return calc_wma(self.close, period)
    
    def bollinger_bands(
        self, 
        period: int = 20, 
        std_dev: float = 2
    ) -> Dict[str, pd.Series]:
        upper, middle, lower = calc_bollinger_bands(self.close, period, std_dev)
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'bandwidth': calc_bollinger_bandwidth(self.close, period, std_dev),
            'percent_b': calc_bollinger_percent_b(self.close, period, std_dev),
        }
    
    def rsi(self, period: int = 14) -> pd.Series:
        return calc_rsi(self.close, period)
    
    def stoch_rsi(
        self,
        rsi_period: int = 14,
        stoch_period: int = 14,
        k_period: int = 3,
        d_period: int = 3
    ) -> Dict[str, pd.Series]:
        k, d = calc_stoch_rsi(self.close, rsi_period, stoch_period, k_period, d_period)
        return {'k': k, 'd': d}
    
    def macd(
        self, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Dict[str, pd.Series]:
        macd_line, signal_line, histogram = calc_macd(self.close, fast, slow, signal)
        
        # 金叉死叉判断
        crossover = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        crossunder = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram,
            'crossover': crossover,
            'crossunder': crossunder,
        }
    
    def kdj(
        self,
        period: int = 9,
        signal_period: int = 3
    ) -> Dict[str, pd.Series]:
        """KDJ 指标（新增）"""
        k, d, j = calc_kdj(self.high, self.low, self.close, period, signal_period)
        
        # 金叉死叉
        crossover = (k > d) & (k.shift(1) <= d.shift(1))
        crossunder = (k < d) & (k.shift(1) >= d.shift(1))
        
        return {
            'k': k,
            'd': d,
            'j': j,
            'crossover': crossover,
            'crossunder': crossunder,
        }
    
    def adx(self, period: int = 14) -> Dict[str, pd.Series]:
        """ADX 指标（新增）"""
        adx, plus_di, minus_di = calc_adx(self.high, self.low, self.close, period)
        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
        }
    
    def williams_r(self, period: int = 14) -> pd.Series:
        """威廉指标（新增）"""
        return calc_williams_r(self.high, self.low, self.close, period)
    
    def obv(self) -> pd.Series:
        """OBV（新增）"""
        return calc_obv(self.close, self.volume)
    
    def obv_divergence(self, period: int = 14) -> pd.Series:
        """OBV 背离（新增）"""
        return calc_obv_divergence(self.close, self.volume, period)
    
    def vwap(self) -> pd.Series:
        """VWAP（新增）"""
        return calc_vwap(self.high, self.low, self.close, self.volume)
    
    def vwap_bands(self, std_dev: float = 2) -> Dict[str, pd.Series]:
        """VWAP 带（新增）"""
        upper, middle, lower = calc_vwap_bands(
            self.high, self.low, self.close, self.volume, std_dev
        )
        return {'upper': upper, 'middle': middle, 'lower': lower}
    
    def atr(self, period: int = 14) -> pd.Series:
        return calc_atr(self.high, self.low, self.close, period)
    
    def atr_percent(self, period: int = 14) -> pd.Series:
        """ATR 百分比（新增）"""
        return calc_atr_percent(self.high, self.low, self.close, period)
    
    def volatility(self, period: int = 20) -> pd.Series:
        """波动率（新增）"""
        return calc_volatility(self.close, period)
    
    def volatility_ratio(self, short_period: int = 5, long_period: int = 20) -> pd.Series:
        """波动率比率（新增）"""
        return calc_volatility_ratio(self.close, short_period, long_period)
    
    def trend_strength(self, period: int = 20) -> pd.Series:
        """趋势强度（新增）"""
        return calc_trend_strength(self.close, period)
    
    def trend_direction(self, short_period: int = 10, long_period: int = 30) -> pd.Series:
        """趋势方向（新增）"""
        return calc_trend_direction(self.close, short_period, long_period)
    
    def pivot_points(self) -> Dict[str, float]:
        """枢轴点（新增）"""
        return calc_pivot_points(self.high, self.low, self.close)
    
    def support_resistance(
        self,
        period: int = 20,
        num_levels: int = 3
    ) -> Dict[str, any]:
        """支撑阻力位（新增）"""
        return calc_support_resistance(self.high, self.low, self.close, period, num_levels)
    
    def volume_ratio(self, period: int = 20) -> pd.Series:
        """量比（新增）"""
        return calc_volume_ratio(self.volume, period)
    
    def mfi(self, period: int = 14) -> pd.Series:
        """MFI（新增）"""
        return calc_mfi(self.high, self.low, self.close, self.volume, period)
    
    def candle_pattern(self) -> str:
        """K线形态（新增）"""
        return detect_candle_pattern(self.df)
    
    def market_state(self) -> Dict[str, any]:
        """市场状态（新增）"""
        return detect_market_state(self.df)
    
    def get_all_indicators(self) -> Dict[str, any]:
        """获取所有指标（用于策略分析）"""
        return {
            'rsi': self.rsi(),
            'macd': self.macd(),
            'bollinger': self.bollinger_bands(),
            'kdj': self.kdj(),
            'adx': self.adx(),
            'atr': self.atr(),
            'atr_percent': self.atr_percent(),
            'volatility': self.volatility(),
            'trend_strength': self.trend_strength(),
            'trend_direction': self.trend_direction(),
            'volume_ratio': self.volume_ratio(),
            'market_state': self.market_state(),
            'candle_pattern': self.candle_pattern(),
        }

    def calculate_all(self) -> pd.DataFrame:
        """计算所有指标并添加到DataFrame中"""
        result = self.df.copy()

        # RSI
        result['rsi'] = self.rsi()

        # MACD
        macd_data = self.macd()
        result['macd'] = macd_data['macd']
        result['macd_signal'] = macd_data['signal']
        result['macd_histogram'] = macd_data['histogram']

        # Bollinger Bands
        bb_data = self.bollinger_bands()
        result['bb_upper'] = bb_data['upper']
        result['bb_middle'] = bb_data['middle']
        result['bb_lower'] = bb_data['lower']
        result['bb_bandwidth'] = bb_data['bandwidth']

        # KDJ
        kdj_data = self.kdj()
        result['kdj_k'] = kdj_data['k']
        result['kdj_d'] = kdj_data['d']
        result['kdj_j'] = kdj_data['j']

        # ADX
        adx_data = self.adx()
        result['adx'] = adx_data['adx']
        result['adx_plus'] = adx_data['plus_di']
        result['adx_minus'] = adx_data['minus_di']

        # ATR
        result['atr'] = self.atr()
        result['atr_percent'] = self.atr_percent()

        # EMA
        result['ema_7'] = self.ema(7)
        result['ema_25'] = self.ema(25)
        result['ema_99'] = self.ema(99)

        # 趋势和波动
        result['volatility'] = self.volatility()
        result['trend_strength'] = self.trend_strength()
        result['trend_direction'] = self.trend_direction()
        result['volume_ratio'] = self.volume_ratio()

        return result

