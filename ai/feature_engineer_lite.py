"""
轻量级特征工程模块 - 内存优化版

优化策略：
1. 移除pandas依赖，使用纯numpy
2. 减少特征数量：47个 → 10个关键特征
3. 使用float32替代float64
4. 返回numpy数组而非DataFrame
5. 最小化内存分配

内存占用对比：
- 原版：~100-150 MB (pandas + 47特征)
- 优化版：~20-30 MB (numpy + 10特征)
"""

import numpy as np
from typing import Dict, List, Optional, Union
from datetime import datetime

from config.settings import settings as config
from utils.logger_utils import get_logger

logger = get_logger("feature_engineer_lite")


class LightweightFeatureEngineer:
    """轻量级特征工程器 - 内存优化版"""

    # 关键特征列表（10个核心特征）
    CRITICAL_FEATURES = [
        'signal_strength',      # 信号强度
        'strategy_agreement',   # 策略一致性
        'rsi',                  # RSI指标
        'adx',                  # 趋势强度
        'atr_pct',              # ATR百分比（波动率）
        'bb_position',          # 布林带位置
        'volume_ratio',         # 成交量比率
        'price_change_10',      # 10周期价格变化
        'volatility_10',        # 10周期波动率
        'market_regime',        # 市场状态
    ]

    def __init__(self, lookback: int = None):
        """
        初始化轻量级特征工程器

        Args:
            lookback: 特征计算回溯周期（K线数量）
        """
        self.lookback = lookback or config.ML_FEATURE_LOOKBACK
        self.feature_count = len(self.CRITICAL_FEATURES)

    def extract_features(
        self,
        data: Union[Dict, np.ndarray],
        signal_info: Dict
    ) -> np.ndarray:
        """
        从市场数据和信号信息中提取特征（轻量级版本）

        Args:
            data: 市场数据
                - 如果是dict: 包含OHLCV和技术指标的字典
                - 如果是ndarray: K线数据数组
            signal_info: 信号信息字典

        Returns:
            特征数组 (shape: [10,], dtype: float32)
        """
        try:
            # 初始化特征数组（使用float32节省内存）
            features = np.zeros(self.feature_count, dtype=np.float32)

            # 1. 信号特征（最重要）
            features[0] = float(signal_info.get('strength', 0.5))
            features[1] = float(signal_info.get('agreement', 0.5))

            # 2. 技术指标特征
            features[2] = self._get_rsi(data)
            features[3] = self._get_adx(data)
            features[4] = self._get_atr_pct(data)
            features[5] = self._get_bb_position(data)

            # 3. 成交量特征
            features[6] = self._get_volume_ratio(data)

            # 4. 价格动量特征
            features[7] = self._get_price_change(data, period=10)

            # 5. 波动率特征
            features[8] = self._get_volatility(data, period=10)

            # 6. 市场状态特征
            features[9] = self._encode_market_regime(
                signal_info.get('market_state', 'UNKNOWN')
            )

            return features

        except Exception as e:
            logger.error(f"轻量级特征提取失败: {e}")
            return self._get_default_features()

    def _get_rsi(self, data: Union[Dict, np.ndarray]) -> float:
        """获取RSI值"""
        try:
            if isinstance(data, dict):
                return float(data.get('rsi', 50.0))
            # 如果是数组，假设最后一列是RSI
            return float(data[-1, -1]) if len(data.shape) > 1 else 50.0
        except:
            return 50.0

    def _get_adx(self, data: Union[Dict, np.ndarray]) -> float:
        """获取ADX值"""
        try:
            if isinstance(data, dict):
                return float(data.get('adx', 20.0))
            return 20.0
        except:
            return 20.0

    def _get_atr_pct(self, data: Union[Dict, np.ndarray]) -> float:
        """获取ATR百分比"""
        try:
            if isinstance(data, dict):
                atr = data.get('atr', 0.0)
                close = data.get('close', 0.0)
                if isinstance(close, (list, np.ndarray)):
                    close = close[-1] if len(close) > 0 else 0.0
                return float(atr / close) if close > 0 else 0.0
            return 0.0
        except:
            return 0.0

    def _get_bb_position(self, data: Union[Dict, np.ndarray]) -> float:
        """获取布林带位置（0-1）"""
        try:
            if isinstance(data, dict):
                close = data.get('close', 0.0)
                if isinstance(close, (list, np.ndarray)):
                    close = close[-1] if len(close) > 0 else 0.0

                upper = data.get('bb_upper', 0.0)
                if isinstance(upper, (list, np.ndarray)):
                    upper = upper[-1] if len(upper) > 0 else 0.0

                lower = data.get('bb_lower', 0.0)
                if isinstance(lower, (list, np.ndarray)):
                    lower = lower[-1] if len(lower) > 0 else 0.0

                if upper != lower:
                    return float((close - lower) / (upper - lower))
            return 0.5
        except:
            return 0.5

    def _get_volume_ratio(self, data: Union[Dict, np.ndarray]) -> float:
        """获取成交量比率"""
        try:
            if isinstance(data, dict):
                volume = data.get('volume', [])
                if isinstance(volume, (list, np.ndarray)) and len(volume) >= 20:
                    volume_arr = np.array(volume, dtype=np.float32)
                    current = volume_arr[-1]
                    avg = np.mean(volume_arr[-20:])
                    return float(current / avg) if avg > 0 else 1.0
            return 1.0
        except:
            return 1.0

    def _get_price_change(self, data: Union[Dict, np.ndarray], period: int = 10) -> float:
        """获取价格变化百分比"""
        try:
            if isinstance(data, dict):
                close = data.get('close', [])
                if isinstance(close, (list, np.ndarray)) and len(close) >= period + 1:
                    close_arr = np.array(close, dtype=np.float32)
                    current = close_arr[-1]
                    previous = close_arr[-period-1]
                    return float((current - previous) / previous * 100) if previous > 0 else 0.0
            return 0.0
        except:
            return 0.0

    def _get_volatility(self, data: Union[Dict, np.ndarray], period: int = 10) -> float:
        """获取波动率"""
        try:
            if isinstance(data, dict):
                close = data.get('close', [])
                if isinstance(close, (list, np.ndarray)) and len(close) >= period:
                    close_arr = np.array(close[-period:], dtype=np.float32)
                    returns = np.diff(close_arr) / close_arr[:-1]
                    return float(np.std(returns) * 100)
            return 0.0
        except:
            return 0.0

    def _encode_market_regime(self, regime: str) -> float:
        """编码市场状态"""
        regime_map = {
            'RANGING': 0.0,
            'TRANSITIONING': 1.0,
            'TRENDING': 2.0,
            'UNKNOWN': 1.0
        }
        return float(regime_map.get(regime, 1.0))

    def _get_default_features(self) -> np.ndarray:
        """获取默认特征（当提取失败时使用）"""
        return np.array([
            0.5,   # signal_strength
            0.5,   # strategy_agreement
            50.0,  # rsi
            20.0,  # adx
            0.0,   # atr_pct
            0.5,   # bb_position
            1.0,   # volume_ratio
            0.0,   # price_change_10
            0.0,   # volatility_10
            1.0,   # market_regime
        ], dtype=np.float32)

    def get_feature_names(self) -> List[str]:
        """获取特征名称列表"""
        return self.CRITICAL_FEATURES.copy()

    def get_feature_count(self) -> int:
        """获取特征数量"""
        return self.feature_count


# ==================== 兼容性包装器 ====================

class PandasCompatibleWrapper:
    """
    pandas兼容性包装器

    将pandas DataFrame转换为dict格式，供轻量级特征工程器使用
    """

    def __init__(self):
        self.engineer = LightweightFeatureEngineer()

    def extract_features(self, df, signal_info: Dict) -> np.ndarray:
        """
        从pandas DataFrame提取特征

        Args:
            df: pandas DataFrame（K线数据）
            signal_info: 信号信息

        Returns:
            特征数组
        """
        try:
            # 将DataFrame转换为dict格式
            data = {}

            # 提取最后一行的标量值
            if 'rsi' in df.columns:
                data['rsi'] = float(df['rsi'].iloc[-1])
            if 'adx' in df.columns:
                data['adx'] = float(df['adx'].iloc[-1])
            if 'atr' in df.columns:
                data['atr'] = float(df['atr'].iloc[-1])

            # 提取数组值
            if 'close' in df.columns:
                data['close'] = df['close'].values.astype(np.float32)
            if 'volume' in df.columns:
                data['volume'] = df['volume'].values.astype(np.float32)
            if 'bb_upper' in df.columns:
                data['bb_upper'] = df['bb_upper'].values.astype(np.float32)
            if 'bb_lower' in df.columns:
                data['bb_lower'] = df['bb_lower'].values.astype(np.float32)

            return self.engineer.extract_features(data, signal_info)

        except Exception as e:
            logger.error(f"pandas兼容性包装器提取失败: {e}")
            return self.engineer._get_default_features()

    def get_feature_names(self) -> List[str]:
        """获取特征名称"""
        return self.engineer.get_feature_names()


# ==================== 使用示例 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("轻量级特征工程器测试")
    print("=" * 60)

    # 创建轻量级特征工程器
    engineer = LightweightFeatureEngineer()

    # 模拟数据（dict格式）
    data = {
        'close': np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110], dtype=np.float32),
        'volume': np.array([1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000], dtype=np.float32),
        'rsi': 58.5,
        'adx': 28.3,
        'atr': 2.5,
        'bb_upper': 112.0,
        'bb_lower': 98.0,
    }

    signal_info = {
        'strength': 0.75,
        'agreement': 0.8,
        'market_state': 'TRENDING'
    }

    # 提取特征
    features = engineer.extract_features(data, signal_info)

    print(f"\n特征数量: {len(features)}")
    print(f"特征类型: {features.dtype}")
    print(f"内存占用: {features.nbytes} bytes")
    print(f"\n特征值:")
    for name, value in zip(engineer.get_feature_names(), features):
        print(f"  {name:20s}: {value:.4f}")

    print("\n" + "=" * 60)
    print("内存优化对比")
    print("=" * 60)
    print(f"原版特征数量: 47")
    print(f"优化版特征数量: {len(features)}")
    print(f"特征减少: {(1 - len(features)/47)*100:.1f}%")
    print(f"\n原版内存（估算）: ~150 MB (pandas + 47特征)")
    print(f"优化版内存（估算）: ~30 MB (numpy + 10特征)")
    print(f"内存节省: ~80%")
    print("=" * 60)
