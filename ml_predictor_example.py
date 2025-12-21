"""
ML信号质量预测器 - 示例实现
这是一个简化的示例，展示如何集成ML模型到现有系统
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import joblib
from pathlib import Path

class MLSignalPredictor:
    """ML信号质量预测器"""

    def __init__(self, model_path: str = "models/signal_quality_v1.pkl"):
        """
        初始化预测器

        Args:
            model_path: 模型文件路径
        """
        self.model_path = Path(model_path)
        self.model = None
        self.scaler = None
        self.feature_names = None

        # 加载模型（如果存在）
        if self.model_path.exists():
            self.load_model()

    def load_model(self):
        """加载训练好的模型"""
        try:
            model_data = joblib.load(self.model_path)
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            print(f"✓ 模型加载成功: {self.model_path}")
        except Exception as e:
            print(f"✗ 模型加载失败: {e}")
            self.model = None

    def extract_features(self, df: pd.DataFrame, signal_info: Dict) -> pd.DataFrame:
        """
        从市场数据和信号信息中提取特征

        Args:
            df: K线数据
            signal_info: 信号信息（包含策略、强度、一致性等）

        Returns:
            特征DataFrame
        """
        features = {}

        # 1. 技术指标特征
        features['rsi'] = df['rsi'].iloc[-1] if 'rsi' in df else 50
        features['macd'] = df['macd'].iloc[-1] if 'macd' in df else 0
        features['macd_signal'] = df['macd_signal'].iloc[-1] if 'macd_signal' in df else 0
        features['bb_position'] = self._calculate_bb_position(df)
        features['atr'] = df['atr'].iloc[-1] if 'atr' in df else 0
        features['adx'] = df['adx'].iloc[-1] if 'adx' in df else 0

        # 2. 价格动量特征
        features['price_change_5m'] = self._calculate_price_change(df, 5)
        features['price_change_15m'] = self._calculate_price_change(df, 15)
        features['price_change_1h'] = self._calculate_price_change(df, 60)

        # 3. 成交量特征
        features['volume_ratio'] = self._calculate_volume_ratio(df)
        features['volume_trend'] = self._calculate_volume_trend(df)

        # 4. 波动率特征
        features['volatility'] = df['close'].pct_change().std() * 100
        features['volatility_ratio'] = features['volatility'] / df['atr'].iloc[-1] if 'atr' in df and df['atr'].iloc[-1] > 0 else 1

        # 5. 信号特征
        features['signal_strength'] = signal_info.get('strength', 0.5)
        features['strategy_agreement'] = signal_info.get('agreement', 0.5)
        features['num_strategies'] = signal_info.get('num_strategies', 1)

        # 6. 市场状态特征
        features['market_regime'] = self._encode_market_regime(signal_info.get('market_state', 'UNKNOWN'))

        # 7. 时间特征
        features['hour'] = pd.Timestamp.now().hour
        features['day_of_week'] = pd.Timestamp.now().dayofweek
        features['is_us_trading_hours'] = 1 if 14 <= pd.Timestamp.now().hour <= 21 else 0

        return pd.DataFrame([features])

    def predict_signal_quality(self, df: pd.DataFrame, signal_info: Dict) -> Optional[float]:
        """
        预测信号质量

        Args:
            df: K线数据
            signal_info: 信号信息

        Returns:
            信号质量分数（0-1），如果模型未加载则返回None
        """
        if self.model is None:
            return None

        try:
            # 提取特征
            features = self.extract_features(df, signal_info)

            # 确保特征顺序与训练时一致
            if self.feature_names is not None:
                features = features[self.feature_names]

            # 标准化
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features.values

            # 预测概率
            quality_score = self.model.predict_proba(features_scaled)[0][1]  # 获取正类概率

            return float(quality_score)

        except Exception as e:
            print(f"✗ 预测失败: {e}")
            return None

    def should_execute_signal(self, quality_score: float, threshold: float = 0.6) -> bool:
        """
        判断是否应该执行信号

        Args:
            quality_score: 信号质量分数
            threshold: 质量阈值

        Returns:
            是否执行
        """
        return quality_score >= threshold

    # ==================== 辅助方法 ====================

    def _calculate_bb_position(self, df: pd.DataFrame) -> float:
        """计算价格在布林带中的位置（0-1）"""
        if 'bb_upper' not in df or 'bb_lower' not in df:
            return 0.5

        close = df['close'].iloc[-1]
        upper = df['bb_upper'].iloc[-1]
        lower = df['bb_lower'].iloc[-1]

        if upper == lower:
            return 0.5

        return (close - lower) / (upper - lower)

    def _calculate_price_change(self, df: pd.DataFrame, periods: int) -> float:
        """计算N周期价格变化百分比"""
        if len(df) < periods + 1:
            return 0

        current = df['close'].iloc[-1]
        previous = df['close'].iloc[-periods-1]

        return (current - previous) / previous * 100

    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float:
        """计算当前成交量与平均成交量的比率"""
        if 'volume' not in df or len(df) < 20:
            return 1.0

        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-20:].mean()

        return current_volume / avg_volume if avg_volume > 0 else 1.0

    def _calculate_volume_trend(self, df: pd.DataFrame) -> float:
        """计算成交量趋势（正值表示上升，负值表示下降）"""
        if 'volume' not in df or len(df) < 10:
            return 0

        recent_volume = df['volume'].iloc[-5:].mean()
        previous_volume = df['volume'].iloc[-10:-5].mean()

        return (recent_volume - previous_volume) / previous_volume if previous_volume > 0 else 0

    def _encode_market_regime(self, regime: str) -> int:
        """编码市场状态"""
        regime_map = {
            'RANGING': 0,
            'TRANSITIONING': 1,
            'TRENDING': 2,
            'UNKNOWN': 1
        }
        return regime_map.get(regime, 1)


# ==================== 使用示例 ====================

def example_usage():
    """使用示例"""

    # 1. 初始化预测器
    predictor = MLSignalPredictor()

    # 2. 模拟市场数据
    df = pd.DataFrame({
        'close': [100, 101, 102, 103, 104],
        'volume': [1000, 1100, 1200, 1300, 1400],
        'rsi': [45, 48, 52, 55, 58],
        'macd': [-0.5, -0.3, 0.1, 0.3, 0.5],
        'macd_signal': [-0.4, -0.2, 0.0, 0.2, 0.4],
        'atr': [2.0, 2.1, 2.2, 2.3, 2.4],
        'adx': [25, 26, 27, 28, 29],
        'bb_upper': [105, 106, 107, 108, 109],
        'bb_lower': [95, 96, 97, 98, 99],
    })

    # 3. 模拟信号信息
    signal_info = {
        'strength': 0.75,
        'agreement': 0.8,
        'num_strategies': 5,
        'market_state': 'TRENDING'
    }

    # 4. 预测信号质量
    quality_score = predictor.predict_signal_quality(df, signal_info)

    if quality_score is not None:
        print(f"信号质量分数: {quality_score:.2f}")

        # 5. 判断是否执行
        should_execute = predictor.should_execute_signal(quality_score, threshold=0.6)
        print(f"是否执行: {'✓ 是' if should_execute else '✗ 否'}")
    else:
        print("模型未加载，使用默认策略")


if __name__ == "__main__":
    example_usage()
