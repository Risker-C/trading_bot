"""
特征工程模块 - ML信号过滤器

从市场数据和信号信息中提取特征，用于ML模型预测信号质量
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

import config
from utils.logger_utils import get_logger

logger = get_logger("feature_engineer")


class FeatureEngineer:
    """特征工程类"""

    def __init__(self, lookback: int = None):
        """
        初始化特征工程器

        Args:
            lookback: 特征计算回溯周期（K线数量）
        """
        self.lookback = lookback or config.ML_FEATURE_LOOKBACK

    def extract_features(self, df: pd.DataFrame, signal_info: Dict) -> pd.DataFrame:
        """
        从市场数据和信号信息中提取特征

        Args:
            df: K线数据（包含技术指标）
            signal_info: 信号信息字典
                - signal: 信号类型 (long/short)
                - strength: 信号强度
                - confidence: 信号置信度
                - strategy: 策略名称
                - num_strategies: 策略数量
                - agreement: 策略一致性
                - market_state: 市场状态

        Returns:
            特征DataFrame（单行）
        """
        features = {}

        try:
            # 1. 技术指标特征
            features.update(self._extract_indicator_features(df))

            # 2. 价格动量特征
            features.update(self._extract_momentum_features(df))

            # 3. 成交量特征
            features.update(self._extract_volume_features(df))

            # 4. 波动率特征
            features.update(self._extract_volatility_features(df))

            # 5. 信号特征
            features.update(self._extract_signal_features(signal_info))

            # 6. 市场状态特征
            features.update(self._extract_market_features(df, signal_info))

            # 7. 时间特征
            features.update(self._extract_time_features())

            # 8. 价格形态特征
            features.update(self._extract_pattern_features(df))

            return pd.DataFrame([features])

        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return pd.DataFrame([self._get_default_features()])

    def _extract_indicator_features(self, df: pd.DataFrame) -> Dict:
        """提取技术指标特征"""
        features = {}

        # RSI
        if 'rsi' in df.columns:
            features['rsi'] = df['rsi'].iloc[-1]
            features['rsi_oversold'] = 1 if df['rsi'].iloc[-1] < 30 else 0
            features['rsi_overbought'] = 1 if df['rsi'].iloc[-1] > 70 else 0
        else:
            features['rsi'] = 50
            features['rsi_oversold'] = 0
            features['rsi_overbought'] = 0

        # MACD
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            features['macd'] = df['macd'].iloc[-1]
            features['macd_signal'] = df['macd_signal'].iloc[-1]
            features['macd_histogram'] = df['macd'].iloc[-1] - df['macd_signal'].iloc[-1]
            features['macd_above_zero'] = 1 if df['macd'].iloc[-1] > 0 else 0
        else:
            features['macd'] = 0
            features['macd_signal'] = 0
            features['macd_histogram'] = 0
            features['macd_above_zero'] = 0

        # 布林带
        if 'bb_upper' in df.columns and 'bb_lower' in df.columns and 'bb_middle' in df.columns:
            close = df['close'].iloc[-1]
            upper = df['bb_upper'].iloc[-1]
            lower = df['bb_lower'].iloc[-1]
            middle = df['bb_middle'].iloc[-1]

            bb_width = (upper - lower) / middle if middle > 0 else 0
            bb_position = (close - lower) / (upper - lower) if upper != lower else 0.5

            features['bb_width'] = bb_width
            features['bb_position'] = bb_position
            features['bb_squeeze'] = 1 if bb_width < 0.02 else 0  # 布林带收窄
        else:
            features['bb_width'] = 0.02
            features['bb_position'] = 0.5
            features['bb_squeeze'] = 0

        # ATR
        if 'atr' in df.columns:
            features['atr'] = df['atr'].iloc[-1]
            features['atr_pct'] = df['atr'].iloc[-1] / df['close'].iloc[-1] if df['close'].iloc[-1] > 0 else 0
        else:
            features['atr'] = 0
            features['atr_pct'] = 0

        # ADX
        if 'adx' in df.columns:
            features['adx'] = df['adx'].iloc[-1]
            features['adx_strong_trend'] = 1 if df['adx'].iloc[-1] > 25 else 0
        else:
            features['adx'] = 20
            features['adx_strong_trend'] = 0

        # EMA
        if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
            ema_fast = df['ema_fast'].iloc[-1]
            ema_slow = df['ema_slow'].iloc[-1]
            features['ema_diff_pct'] = (ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0
            features['ema_bullish'] = 1 if ema_fast > ema_slow else 0
        else:
            features['ema_diff_pct'] = 0
            features['ema_bullish'] = 0

        return features

    def _extract_momentum_features(self, df: pd.DataFrame) -> Dict:
        """提取价格动量特征"""
        features = {}

        close = df['close']

        # 不同周期的价格变化
        for period in [5, 10, 20]:
            if len(df) >= period + 1:
                price_change = (close.iloc[-1] - close.iloc[-period-1]) / close.iloc[-period-1]
                features[f'price_change_{period}'] = price_change * 100  # 转换为百分比
            else:
                features[f'price_change_{period}'] = 0

        # 价格动量（ROC）
        if len(df) >= 10:
            roc = (close.iloc[-1] - close.iloc[-10]) / close.iloc[-10] * 100
            features['roc_10'] = roc
        else:
            features['roc_10'] = 0

        # 价格加速度（动量的变化）
        if len(df) >= 20:
            momentum_now = close.iloc[-1] - close.iloc[-10]
            momentum_prev = close.iloc[-10] - close.iloc[-20]
            features['momentum_acceleration'] = momentum_now - momentum_prev
        else:
            features['momentum_acceleration'] = 0

        return features

    def _extract_volume_features(self, df: pd.DataFrame) -> Dict:
        """提取成交量特征"""
        features = {}

        if 'volume' not in df.columns or len(df) < 20:
            features['volume_ratio'] = 1.0
            features['volume_trend'] = 0
            features['volume_spike'] = 0
            return features

        volume = df['volume']
        current_volume = volume.iloc[-1]
        avg_volume_20 = volume.iloc[-20:].mean()

        # 成交量比率
        features['volume_ratio'] = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0

        # 成交量趋势
        if len(df) >= 10:
            recent_volume = volume.iloc[-5:].mean()
            previous_volume = volume.iloc[-10:-5].mean()
            features['volume_trend'] = (recent_volume - previous_volume) / previous_volume if previous_volume > 0 else 0
        else:
            features['volume_trend'] = 0

        # 成交量突增
        features['volume_spike'] = 1 if features['volume_ratio'] > 2.0 else 0

        return features

    def _extract_volatility_features(self, df: pd.DataFrame) -> Dict:
        """提取波动率特征"""
        features = {}

        close = df['close']

        # 历史波动率（不同周期）
        for period in [5, 10, 20]:
            if len(df) >= period:
                returns = close.pct_change().iloc[-period:]
                volatility = returns.std() * 100  # 转换为百分比
                features[f'volatility_{period}'] = volatility
            else:
                features[f'volatility_{period}'] = 0

        # 波动率比率（当前vs历史）
        if len(df) >= 20:
            vol_recent = close.pct_change().iloc[-5:].std()
            vol_historical = close.pct_change().iloc[-20:].std()
            features['volatility_ratio'] = vol_recent / vol_historical if vol_historical > 0 else 1.0
        else:
            features['volatility_ratio'] = 1.0

        # ATR相对波动率
        if 'atr' in df.columns:
            features['atr_volatility_ratio'] = df['atr'].iloc[-1] / close.iloc[-1] if close.iloc[-1] > 0 else 0
        else:
            features['atr_volatility_ratio'] = 0

        return features

    def _extract_signal_features(self, signal_info: Dict) -> Dict:
        """提取信号特征"""
        features = {}

        # 信号强度和置信度
        features['signal_strength'] = signal_info.get('strength', 0.5)
        features['signal_confidence'] = signal_info.get('confidence', 0.5)
        features['signal_quality'] = features['signal_strength'] * features['signal_confidence']

        # 策略一致性
        features['strategy_agreement'] = signal_info.get('agreement', 0.5)
        features['num_strategies'] = signal_info.get('num_strategies', 1)

        # 信号方向
        signal_type = signal_info.get('signal', 'long')
        features['signal_is_long'] = 1 if signal_type == 'long' else 0

        # 策略类型编码
        strategy = signal_info.get('strategy', 'unknown')
        features['strategy_type'] = self._encode_strategy(strategy)

        return features

    def _extract_market_features(self, df: pd.DataFrame, signal_info: Dict) -> Dict:
        """提取市场状态特征"""
        features = {}

        # 市场状态编码
        market_state = signal_info.get('market_state', 'UNKNOWN')
        features['market_regime'] = self._encode_market_regime(market_state)

        # 趋势强度
        if 'adx' in df.columns:
            adx = df['adx'].iloc[-1]
            if adx > 25:
                features['trend_strength'] = 2  # 强趋势
            elif adx > 20:
                features['trend_strength'] = 1  # 中等趋势
            else:
                features['trend_strength'] = 0  # 弱趋势/震荡
        else:
            features['trend_strength'] = 0

        # 价格位置（相对于最近高低点）
        if len(df) >= 20:
            high_20 = df['high'].iloc[-20:].max()
            low_20 = df['low'].iloc[-20:].min()
            close = df['close'].iloc[-1]
            features['price_position'] = (close - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5
        else:
            features['price_position'] = 0.5

        return features

    def _extract_time_features(self) -> Dict:
        """提取时间特征"""
        features = {}

        now = datetime.now()

        # 小时（0-23）
        features['hour'] = now.hour

        # 星期几（0-6，0=周一）
        features['day_of_week'] = now.weekday()

        # 是否美股交易时间（UTC+8: 22:30-05:00）
        features['is_us_trading_hours'] = 1 if 14 <= now.hour <= 21 else 0

        # 是否亚洲交易时间（UTC+8: 09:00-17:00）
        features['is_asia_trading_hours'] = 1 if 9 <= now.hour <= 17 else 0

        # 是否周末
        features['is_weekend'] = 1 if now.weekday() >= 5 else 0

        return features

    def _extract_pattern_features(self, df: pd.DataFrame) -> Dict:
        """提取价格形态特征"""
        features = {}

        if len(df) < 3:
            features['candle_pattern'] = 0
            features['higher_high'] = 0
            features['lower_low'] = 0
            return features

        # K线形态
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]

        # 阳线/阴线
        is_bullish = last_candle['close'] > last_candle['open']
        features['candle_bullish'] = 1 if is_bullish else 0

        # K线实体大小
        body_size = abs(last_candle['close'] - last_candle['open'])
        candle_range = last_candle['high'] - last_candle['low']
        features['candle_body_ratio'] = body_size / candle_range if candle_range > 0 else 0

        # 上下影线
        if is_bullish:
            upper_shadow = last_candle['high'] - last_candle['close']
            lower_shadow = last_candle['open'] - last_candle['low']
        else:
            upper_shadow = last_candle['high'] - last_candle['open']
            lower_shadow = last_candle['close'] - last_candle['low']

        features['upper_shadow_ratio'] = upper_shadow / candle_range if candle_range > 0 else 0
        features['lower_shadow_ratio'] = lower_shadow / candle_range if candle_range > 0 else 0

        # 高低点趋势
        if len(df) >= 5:
            recent_highs = df['high'].iloc[-5:]
            recent_lows = df['low'].iloc[-5:]
            features['higher_high'] = 1 if recent_highs.iloc[-1] > recent_highs.iloc[-3] else 0
            features['lower_low'] = 1 if recent_lows.iloc[-1] < recent_lows.iloc[-3] else 0
        else:
            features['higher_high'] = 0
            features['lower_low'] = 0

        return features

    def _encode_strategy(self, strategy: str) -> int:
        """编码策略类型"""
        strategy_map = {
            'bollinger_breakthrough': 0,
            'bollinger_trend': 1,
            'rsi_divergence': 2,
            'macd_cross': 3,
            'ema_cross': 4,
            'kdj_cross': 5,
            'adx_trend': 6,
            'volume_breakout': 7,
            'multi_timeframe': 8,
            'grid': 9,
            'composite_score': 10,
            'consensus': 11,
            'unknown': 12
        }
        return strategy_map.get(strategy, 12)

    def _encode_market_regime(self, regime: str) -> int:
        """编码市场状态"""
        regime_map = {
            'RANGING': 0,
            'TRANSITIONING': 1,
            'TRENDING': 2,
            'UNKNOWN': 1
        }
        return regime_map.get(regime, 1)

    def _get_default_features(self) -> Dict:
        """获取默认特征（当提取失败时使用）"""
        return {
            # 技术指标
            'rsi': 50, 'rsi_oversold': 0, 'rsi_overbought': 0,
            'macd': 0, 'macd_signal': 0, 'macd_histogram': 0, 'macd_above_zero': 0,
            'bb_width': 0.02, 'bb_position': 0.5, 'bb_squeeze': 0,
            'atr': 0, 'atr_pct': 0,
            'adx': 20, 'adx_strong_trend': 0,
            'ema_diff_pct': 0, 'ema_bullish': 0,

            # 动量
            'price_change_5': 0, 'price_change_10': 0, 'price_change_20': 0,
            'roc_10': 0, 'momentum_acceleration': 0,

            # 成交量
            'volume_ratio': 1.0, 'volume_trend': 0, 'volume_spike': 0,

            # 波动率
            'volatility_5': 0, 'volatility_10': 0, 'volatility_20': 0,
            'volatility_ratio': 1.0, 'atr_volatility_ratio': 0,

            # 信号
            'signal_strength': 0.5, 'signal_confidence': 0.5, 'signal_quality': 0.25,
            'strategy_agreement': 0.5, 'num_strategies': 1,
            'signal_is_long': 1, 'strategy_type': 12,

            # 市场
            'market_regime': 1, 'trend_strength': 0, 'price_position': 0.5,

            # 时间
            'hour': 12, 'day_of_week': 0, 'is_us_trading_hours': 0,
            'is_asia_trading_hours': 0, 'is_weekend': 0,

            # 形态
            'candle_bullish': 1, 'candle_body_ratio': 0.5,
            'upper_shadow_ratio': 0.2, 'lower_shadow_ratio': 0.2,
            'higher_high': 0, 'lower_low': 0
        }

    def get_feature_names(self) -> List[str]:
        """获取所有特征名称（用于模型训练）"""
        return list(self._get_default_features().keys())


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 测试特征提取
    engineer = FeatureEngineer()

    # 模拟数据
    df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104],
        'high': [101, 102, 103, 104, 105],
        'low': [99, 100, 101, 102, 103],
        'close': [100, 101, 102, 103, 104],
        'volume': [1000, 1100, 1200, 1300, 1400],
        'rsi': [45, 48, 52, 55, 58],
        'macd': [-0.5, -0.3, 0.1, 0.3, 0.5],
        'macd_signal': [-0.4, -0.2, 0.0, 0.2, 0.4],
        'atr': [2.0, 2.1, 2.2, 2.3, 2.4],
        'adx': [25, 26, 27, 28, 29],
        'bb_upper': [105, 106, 107, 108, 109],
        'bb_middle': [100, 101, 102, 103, 104],
        'bb_lower': [95, 96, 97, 98, 99],
    })

    signal_info = {
        'signal': 'long',
        'strength': 0.75,
        'confidence': 0.8,
        'strategy': 'composite_score',
        'num_strategies': 5,
        'agreement': 0.8,
        'market_state': 'TRENDING'
    }

    features = engineer.extract_features(df, signal_info)
    print("提取的特征:")
    print(features.T)
    print(f"\n特征数量: {len(features.columns)}")
