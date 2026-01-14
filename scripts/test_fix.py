#!/usr/bin/env python3
"""
测试数据库日志修复
"""
import numpy as np
import pandas as pd
from utils.logger_utils import db, get_logger

logger = get_logger("test_fix")

def test_log_signal_with_numpy_types():
    """测试 log_signal 是否能正确处理 numpy 类型"""

    logger.info("=" * 50)
    logger.info("开始测试数据库日志修复")
    logger.info("=" * 50)

    # 模拟策略信号中的 indicators (包含 numpy 类型)
    test_cases = [
        {
            "name": "测试1: numpy.float64",
            "indicators": {
                'rsi': np.float64(28.7),
                'rsi_prev': np.float64(30.5),
            }
        },
        {
            "name": "测试2: numpy.int64",
            "indicators": {
                'period': np.int64(14),
                'count': np.int64(5),
            }
        },
        {
            "name": "测试3: 混合类型",
            "indicators": {
                'rsi': np.float64(28.7),
                'macd': np.float64(0.0123),
                'signal': np.float64(-0.0045),
                'histogram': np.float64(0.0168),
                'close': np.float64(42350.5),
                'volume_ratio': np.float64(1.85),
            }
        },
        {
            "name": "测试4: numpy 数组",
            "indicators": {
                'prices': np.array([100.0, 101.0, 102.0]),
                'volumes': np.array([1000, 1100, 1200]),
            }
        },
        {
            "name": "测试5: 嵌套字典",
            "indicators": {
                'rsi': np.float64(28.7),
                'macd': {
                    'macd': np.float64(0.0123),
                    'signal': np.float64(-0.0045),
                    'histogram': np.float64(0.0168),
                }
            }
        },
    ]

    success_count = 0
    fail_count = 0

    for test_case in test_cases:
        try:
            logger.info(f"\n{test_case['name']}")
            logger.info(f"indicators 类型: {type(test_case['indicators'])}")

            # 尝试记录信号
            signal_id = db.log_signal(
                strategy="test_strategy",
                signal="long",
                reason="测试信号",
                strength=0.8,
                confidence=0.9,
                indicators=test_case['indicators']
            )

            logger.info(f"✅ 成功! signal_id={signal_id}")
            success_count += 1

        except Exception as e:
            logger.error(f"❌ 失败! 错误: {e}")
            fail_count += 1

    # 总结
    logger.info("\n" + "=" * 50)
    logger.info("测试结果总结")
    logger.info("=" * 50)
    logger.info(f"总测试数: {len(test_cases)}")
    logger.info(f"✅ 成功: {success_count}")
    logger.info(f"❌ 失败: {fail_count}")

    if fail_count == 0:
        logger.info("\n🎉 所有测试通过! 修复成功!")
        return True
    else:
        logger.error(f"\n⚠️  有 {fail_count} 个测试失败")
        return False


if __name__ == "__main__":
    success = test_log_signal_with_numpy_types()
    exit(0 if success else 1)
