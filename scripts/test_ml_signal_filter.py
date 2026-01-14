#!/usr/bin/env python3
"""
ML信号过滤器测试脚本

测试内容：
1. 配置验证
2. 特征工程模块
3. ML预测器模块
4. 模型训练脚本
5. bot.py集成
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger
from ai.feature_engineer import FeatureEngineer
from ai.ml_predictor import MLSignalPredictor, reset_ml_predictor
from strategies.strategies import Signal, TradeSignal

logger = get_logger("test_ml_signal_filter")


class TestMLSignalFilter:
    """ML信号过滤器测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*60}")

        try:
            test_func()
            self.passed += 1
            print(f"✅ 测试通过: {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            print(f"❌ 测试失败: {test_name}")
            print(f"   错误: {e}")
            return False
        except Exception as e:
            self.failed += 1
            print(f"❌ 测试异常: {test_name}")
            print(f"   异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"成功率: {(self.passed/self.total*100):.1f}%")
        print(f"{'='*60}\n")

        return self.failed == 0


def test_config_validation():
    """测试1: 配置验证"""
    print("检查ML相关配置项...")

    # 检查配置项是否存在
    assert hasattr(config, 'ENABLE_ML_FILTER'), "缺少配置: ENABLE_ML_FILTER"
    assert hasattr(config, 'ML_MODE'), "缺少配置: ML_MODE"
    assert hasattr(config, 'ML_MODEL_PATH'), "缺少配置: ML_MODEL_PATH"
    assert hasattr(config, 'ML_QUALITY_THRESHOLD'), "缺少配置: ML_QUALITY_THRESHOLD"
    assert hasattr(config, 'ML_MIN_SIGNALS'), "缺少配置: ML_MIN_SIGNALS"
    assert hasattr(config, 'ML_LOG_PREDICTIONS'), "缺少配置: ML_LOG_PREDICTIONS"
    assert hasattr(config, 'ML_VERBOSE_LOGGING'), "缺少配置: ML_VERBOSE_LOGGING"
    assert hasattr(config, 'ML_FEATURE_LOOKBACK'), "缺少配置: ML_FEATURE_LOOKBACK"

    # 检查配置值的有效性
    assert config.ML_MODE in ['shadow', 'filter', 'off'], f"无效的ML_MODE: {config.ML_MODE}"
    assert 0 <= config.ML_QUALITY_THRESHOLD <= 1, f"无效的ML_QUALITY_THRESHOLD: {config.ML_QUALITY_THRESHOLD}"
    assert config.ML_MIN_SIGNALS >= 0, f"无效的ML_MIN_SIGNALS: {config.ML_MIN_SIGNALS}"
    assert config.ML_FEATURE_LOOKBACK > 0, f"无效的ML_FEATURE_LOOKBACK: {config.ML_FEATURE_LOOKBACK}"

    print(f"  ENABLE_ML_FILTER: {config.ENABLE_ML_FILTER}")
    print(f"  ML_MODE: {config.ML_MODE}")
    print(f"  ML_MODEL_PATH: {config.ML_MODEL_PATH}")
    print(f"  ML_QUALITY_THRESHOLD: {config.ML_QUALITY_THRESHOLD}")
    print(f"  ML_FEATURE_LOOKBACK: {config.ML_FEATURE_LOOKBACK}")


def test_feature_engineer():
    """测试2: 特征工程模块"""
    print("测试特征工程模块...")

    engineer = FeatureEngineer()

    # 创建模拟数据
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

    # 提取特征
    features = engineer.extract_features(df, signal_info)

    # 验证特征
    assert isinstance(features, pd.DataFrame), "特征应该是DataFrame"
    assert len(features) == 1, "应该返回单行特征"
    assert len(features.columns) > 40, f"特征数量应该>40，实际: {len(features.columns)}"

    # 检查关键特征
    assert 'rsi' in features.columns, "缺少特征: rsi"
    assert 'signal_strength' in features.columns, "缺少特征: signal_strength"
    assert 'signal_confidence' in features.columns, "缺少特征: signal_confidence"
    assert 'volume_ratio' in features.columns, "缺少特征: volume_ratio"

    # 检查特征值范围
    assert features['signal_strength'].iloc[0] == 0.75, "signal_strength值不正确"
    assert features['signal_confidence'].iloc[0] == 0.8, "signal_confidence值不正确"

    print(f"  提取了 {len(features.columns)} 个特征")
    print(f"  特征名称: {list(features.columns[:10])}...")


def test_ml_predictor_init():
    """测试3: ML预测器初始化"""
    print("测试ML预测器初始化...")

    # 重置单例
    reset_ml_predictor()

    # 创建预测器（影子模式）
    predictor = MLSignalPredictor(mode='shadow')

    assert predictor is not None, "预测器创建失败"
    assert predictor.mode == 'shadow', f"模式应该是shadow，实际: {predictor.mode}"
    assert predictor.feature_engineer is not None, "特征工程器未初始化"

    print(f"  模式: {predictor.mode}")
    print(f"  模型已加载: {predictor.model is not None}")


def test_ml_predictor_filter():
    """测试4: ML预测器过滤功能"""
    print("测试ML预测器过滤功能...")

    # 重置单例
    reset_ml_predictor()

    # 创建预测器（影子模式）
    predictor = MLSignalPredictor(mode='shadow')

    # 创建模拟数据
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

    # 创建模拟信号
    signals = [
        TradeSignal(Signal.LONG, "composite_score", "测试信号1", strength=0.75, confidence=0.8),
        TradeSignal(Signal.LONG, "macd_cross", "测试信号2", strength=0.6, confidence=0.7),
        TradeSignal(Signal.LONG, "ema_cross", "测试信号3", strength=0.5, confidence=0.6),
    ]

    # 过滤信号
    filtered_signals, predictions = predictor.filter_signals(signals, df, threshold=0.6)

    # 验证结果
    assert isinstance(filtered_signals, list), "过滤后的信号应该是列表"
    assert isinstance(predictions, list), "预测结果应该是列表"
    assert len(predictions) == len(signals), f"预测数量应该等于信号数量: {len(predictions)} != {len(signals)}"

    # 影子模式下应该保留所有信号
    assert len(filtered_signals) == len(signals), f"影子模式应该保留所有信号: {len(filtered_signals)} != {len(signals)}"

    # 检查预测结果结构
    for pred in predictions:
        assert 'signal' in pred, "预测结果缺少字段: signal"
        assert 'strategy' in pred, "预测结果缺少字段: strategy"
        assert 'quality_score' in pred, "预测结果缺少字段: quality_score"
        assert 'passed' in pred, "预测结果缺少字段: passed"
        assert 'reason' in pred, "预测结果缺少字段: reason"

    print(f"  原始信号数: {len(signals)}")
    print(f"  过滤后信号数: {len(filtered_signals)}")
    print(f"  预测结果数: {len(predictions)}")


def test_ml_predictor_stats():
    """测试5: ML预测器统计功能"""
    print("测试ML预测器统计功能...")

    # 重置单例
    reset_ml_predictor()

    # 创建预测器
    predictor = MLSignalPredictor(mode='shadow')

    # 获取统计信息
    stats = predictor.get_stats()

    assert isinstance(stats, dict), "统计信息应该是字典"
    assert 'mode' in stats, "统计信息缺少字段: mode"
    assert 'model_loaded' in stats, "统计信息缺少字段: model_loaded"
    assert 'total_predictions' in stats, "统计信息缺少字段: total_predictions"
    assert 'filtered_signals' in stats, "统计信息缺少字段: filtered_signals"
    assert 'filter_rate' in stats, "统计信息缺少字段: filter_rate"

    print(f"  模式: {stats['mode']}")
    print(f"  模型已加载: {stats['model_loaded']}")
    print(f"  总预测数: {stats['total_predictions']}")


def test_feature_names():
    """测试6: 特征名称列表"""
    print("测试特征名称列表...")

    engineer = FeatureEngineer()
    feature_names = engineer.get_feature_names()

    assert isinstance(feature_names, list), "特征名称应该是列表"
    assert len(feature_names) > 40, f"特征数量应该>40，实际: {len(feature_names)}"

    # 检查关键特征
    assert 'rsi' in feature_names, "缺少特征: rsi"
    assert 'macd' in feature_names, "缺少特征: macd"
    assert 'signal_strength' in feature_names, "缺少特征: signal_strength"
    assert 'volume_ratio' in feature_names, "缺少特征: volume_ratio"

    print(f"  特征数量: {len(feature_names)}")
    print(f"  前10个特征: {feature_names[:10]}")


def test_bot_integration():
    """测试7: bot.py集成"""
    print("测试bot.py集成...")

    # 检查bot.py是否导入了ml_predictor
    with open('bot.py', 'r', encoding='utf-8') as f:
        bot_content = f.read()

    assert 'from ml_predictor import get_ml_predictor' in bot_content, "bot.py未导入ml_predictor"
    assert 'self.ml_predictor' in bot_content, "bot.py未初始化ml_predictor"
    assert 'filter_signals' in bot_content, "bot.py未调用filter_signals"

    print("  ✓ bot.py已正确导入ml_predictor")
    print("  ✓ bot.py已初始化ml_predictor")
    print("  ✓ bot.py已调用filter_signals")


def test_model_trainer_exists():
    """测试8: 模型训练脚本存在"""
    print("测试模型训练脚本...")

    import os
    assert os.path.exists('model_trainer.py'), "model_trainer.py不存在"

    # 检查是否可以导入
    try:
        from ai.model_trainer import ModelTrainer
        print("  ✓ model_trainer.py可以正常导入")
        print("  ✓ ModelTrainer类存在")
    except ImportError as e:
        raise AssertionError(f"无法导入model_trainer: {e}")


def test_documentation_exists():
    """测试9: 文档存在"""
    print("测试文档...")

    import os
    assert os.path.exists('docs/ml_signal_filter.md'), "文档不存在: docs/ml_signal_filter.md"

    # 检查文档内容
    with open('docs/ml_signal_filter.md', 'r', encoding='utf-8') as f:
        doc_content = f.read()

    assert '# ML信号过滤器功能说明文档' in doc_content, "文档标题不正确"
    assert '## 概述' in doc_content, "文档缺少概述章节"
    assert '## 配置说明' in doc_content, "文档缺少配置说明章节"
    assert '## 使用方法' in doc_content, "文档缺少使用方法章节"

    print("  ✓ 文档存在且结构完整")


def test_error_handling():
    """测试10: 错误处理"""
    print("测试错误处理...")

    # 重置单例
    reset_ml_predictor()

    # 创建预测器
    predictor = MLSignalPredictor(mode='shadow')

    # 测试空信号列表
    filtered_signals, predictions = predictor.filter_signals([], pd.DataFrame())
    assert len(filtered_signals) == 0, "空信号列表应该返回空列表"
    assert len(predictions) == 0, "空信号列表应该返回空预测"

    # 测试无效数据
    try:
        engineer = FeatureEngineer()
        features = engineer.extract_features(pd.DataFrame(), {})
        # 应该返回默认特征，不应该抛出异常
        assert len(features) == 1, "无效数据应该返回默认特征"
        print("  ✓ 错误处理正常")
    except Exception as e:
        raise AssertionError(f"错误处理失败: {e}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("ML信号过滤器测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestMLSignalFilter()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("特征工程模块", test_feature_engineer)
    tester.run_test("ML预测器初始化", test_ml_predictor_init)
    tester.run_test("ML预测器过滤功能", test_ml_predictor_filter)
    tester.run_test("ML预测器统计功能", test_ml_predictor_stats)
    tester.run_test("特征名称列表", test_feature_names)
    tester.run_test("bot.py集成", test_bot_integration)
    tester.run_test("模型训练脚本存在", test_model_trainer_exists)
    tester.run_test("文档存在", test_documentation_exists)
    tester.run_test("错误处理", test_error_handling)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
