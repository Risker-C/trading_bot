"""
ML信号预测器 - 预测信号质量并过滤低质量信号

⚠️ LEGACY版本：此版本内存占用较高（约200MB），建议使用ml_predictor_lite.py
在生产环境中，请启用ML_FORCE_LITE=True强制使用轻量版（内存占用降低60%）

支持三种运行模式：
- shadow: 影子模式（只记录预测，不影响交易）
- filter: 过滤模式（实际过滤信号）
- off: 关闭
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import joblib
from datetime import datetime

import config
from utils.logger_utils import get_logger
from ai.feature_engineer import FeatureEngineer
from strategies.strategies import TradeSignal

logger = get_logger("ml_predictor")


class MLSignalPredictor:
    """ML信号质量预测器"""

    def __init__(self, model_path: str = None, mode: str = None):
        """
        初始化预测器

        Args:
            model_path: 模型文件路径
            mode: 运行模式 (shadow/filter/off)
        """
        self.model_path = Path(model_path or config.ML_MODEL_PATH)
        self.mode = mode or config.ML_MODE
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.feature_engineer = FeatureEngineer()

        # Phase 2: Legacy版本警告
        logger.warning("⚠️ 使用LEGACY版本的ML预测器（内存占用约200MB）")
        logger.warning("   建议启用ML_FORCE_LITE=True使用轻量版（内存占用降低60%）")

        # 统计信息
        self.stats = {
            'total_predictions': 0,
            'filtered_signals': 0,
            'avg_quality_score': 0.0
        }

        # 加载模型（如果存在）
        if self.mode != 'off':
            self.load_model()

    def load_model(self) -> bool:
        """
        加载训练好的模型

        Returns:
            是否加载成功
        """
        if not self.model_path.exists():
            logger.warning(f"ML模型文件不存在: {self.model_path}")
            logger.info("ML预测器将在影子模式下运行（不影响交易）")
            self.mode = 'shadow'
            return False

        try:
            model_data = joblib.load(self.model_path)
            self.model = model_data['model']
            self.scaler = model_data.get('scaler')
            self.feature_names = model_data.get('feature_names')

            logger.info(f"✓ ML模型加载成功: {self.model_path}")
            logger.info(f"  模型类型: {type(self.model).__name__}")
            logger.info(f"  特征数量: {len(self.feature_names) if self.feature_names else 'unknown'}")
            logger.info(f"  运行模式: {self.mode}")

            return True

        except Exception as e:
            logger.error(f"✗ ML模型加载失败: {e}")
            self.mode = 'shadow'
            return False

    def predict_signal_quality(
        self,
        df: pd.DataFrame,
        signal: TradeSignal
    ) -> Optional[float]:
        """
        预测单个信号的质量

        Args:
            df: K线数据（包含技术指标）
            signal: 交易信号

        Returns:
            信号质量分数（0-1），如果预测失败则返回None
        """
        if self.model is None:
            return None

        try:
            # 构建信号信息字典
            signal_info = {
                'signal': signal.signal.value,
                'strength': signal.strength,
                'confidence': signal.confidence,
                'strategy': signal.strategy,
                'num_strategies': 1,
                'agreement': 1.0,
                'market_state': 'UNKNOWN'
            }

            # 提取特征
            features = self.feature_engineer.extract_features(df, signal_info)

            # 确保特征顺序与训练时一致
            if self.feature_names is not None:
                # 检查是否有缺失的特征
                missing_features = set(self.feature_names) - set(features.columns)
                if missing_features:
                    logger.warning(f"缺失特征: {missing_features}")
                    # 用默认值填充缺失特征
                    for feat in missing_features:
                        features[feat] = 0

                features = features[self.feature_names]

            # 标准化
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features.values

            # 预测概率
            if hasattr(self.model, 'predict_proba'):
                # 分类模型：返回正类概率
                quality_score = self.model.predict_proba(features_scaled)[0][1]
            else:
                # 回归模型：直接返回预测值
                quality_score = self.model.predict(features_scaled)[0]
                # 确保在0-1范围内
                quality_score = np.clip(quality_score, 0, 1)

            # 更新统计
            self.stats['total_predictions'] += 1
            self.stats['avg_quality_score'] = (
                (self.stats['avg_quality_score'] * (self.stats['total_predictions'] - 1) + quality_score)
                / self.stats['total_predictions']
            )

            return float(quality_score)

        except Exception as e:
            logger.error(f"✗ ML预测失败: {e}")
            return None

    def filter_signals(
        self,
        signals: List[TradeSignal],
        df: pd.DataFrame,
        threshold: float = None
    ) -> Tuple[List[TradeSignal], List[Dict]]:
        """
        过滤信号列表

        Args:
            signals: 信号列表
            df: K线数据
            threshold: 质量阈值（默认使用配置值）

        Returns:
            (过滤后的信号列表, 预测结果列表)
        """
        if not signals:
            return [], []

        threshold = threshold or config.ML_QUALITY_THRESHOLD

        filtered_signals = []
        predictions = []

        for signal in signals:
            # 预测信号质量
            quality_score = self.predict_signal_quality(df, signal)

            # 记录预测结果
            prediction = {
                'signal': signal.signal.value,
                'strategy': signal.strategy,
                'original_strength': signal.strength,
                'original_confidence': signal.confidence,
                'quality_score': quality_score,
                'threshold': threshold,
                'passed': False,
                'timestamp': datetime.now().isoformat()
            }

            if quality_score is None:
                # 预测失败，保留信号
                filtered_signals.append(signal)
                prediction['passed'] = True
                prediction['reason'] = 'prediction_failed'
            elif self.mode == 'shadow':
                # 影子模式：保留所有信号，只记录预测
                filtered_signals.append(signal)
                prediction['passed'] = True
                prediction['reason'] = 'shadow_mode'
            elif quality_score >= threshold:
                # 质量达标，保留信号
                filtered_signals.append(signal)
                prediction['passed'] = True
                prediction['reason'] = 'quality_passed'
            else:
                # 质量不达标，过滤掉
                self.stats['filtered_signals'] += 1
                prediction['passed'] = False
                prediction['reason'] = 'quality_too_low'

                if config.ML_VERBOSE_LOGGING:
                    logger.info(
                        f"✗ ML过滤信号: {signal.strategy} {signal.signal.value} "
                        f"(质量={quality_score:.2f} < {threshold:.2f})"
                    )

            predictions.append(prediction)

        # 日志记录
        if config.ML_VERBOSE_LOGGING and predictions:
            passed_count = sum(1 for p in predictions if p['passed'])
            avg_quality = np.mean([p['quality_score'] for p in predictions if p['quality_score'] is not None])

            logger.info(
                f"ML过滤结果: {passed_count}/{len(signals)}个信号通过 "
                f"(平均质量={avg_quality:.2f}, 阈值={threshold:.2f})"
            )

        return filtered_signals, predictions

    def should_execute_signal(
        self,
        quality_score: float,
        threshold: float = None
    ) -> bool:
        """
        判断是否应该执行信号

        Args:
            quality_score: 信号质量分数
            threshold: 质量阈值

        Returns:
            是否执行
        """
        threshold = threshold or config.ML_QUALITY_THRESHOLD

        if self.mode == 'off':
            return True
        elif self.mode == 'shadow':
            return True
        elif self.mode == 'filter':
            return quality_score >= threshold
        else:
            logger.warning(f"未知的ML模式: {self.mode}，默认执行信号")
            return True

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['mode'] = self.mode
        stats['model_loaded'] = self.model is not None
        stats['filter_rate'] = (
            self.stats['filtered_signals'] / self.stats['total_predictions']
            if self.stats['total_predictions'] > 0 else 0
        )
        return stats

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_predictions': 0,
            'filtered_signals': 0,
            'avg_quality_score': 0.0
        }


# ==================== 全局单例 ====================

_ml_predictor_instance = None


def get_ml_predictor() -> MLSignalPredictor:
    """
    获取ML预测器单例

    Returns:
        ML预测器实例
    """
    global _ml_predictor_instance

    if _ml_predictor_instance is None:
        _ml_predictor_instance = MLSignalPredictor()

    return _ml_predictor_instance


def reset_ml_predictor():
    """重置ML预测器单例（用于测试）"""
    global _ml_predictor_instance
    _ml_predictor_instance = None


# ==================== 使用示例 ====================

if __name__ == "__main__":
    from strategies.strategies import Signal

    # 测试ML预测器
    predictor = MLSignalPredictor(mode='shadow')

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

    # 模拟信号
    signals = [
        TradeSignal(Signal.LONG, "composite_score", "测试信号1", strength=0.75, confidence=0.8),
        TradeSignal(Signal.LONG, "macd_cross", "测试信号2", strength=0.6, confidence=0.7),
        TradeSignal(Signal.LONG, "ema_cross", "测试信号3", strength=0.5, confidence=0.6),
    ]

    # 过滤信号
    filtered_signals, predictions = predictor.filter_signals(signals, df, threshold=0.6)

    print(f"\n原始信号数: {len(signals)}")
    print(f"过滤后信号数: {len(filtered_signals)}")
    print(f"\n预测结果:")
    for pred in predictions:
        print(f"  {pred['strategy']}: 质量={pred['quality_score']}, 通过={pred['passed']}")

    print(f"\n统计信息:")
    stats = predictor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
