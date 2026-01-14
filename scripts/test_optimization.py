#!/usr/bin/env python3
"""
项目优化验证测试脚本

测试内容：
1. Claude异步化API调用验证
2. 配置统一性验证
3. 数据库批量写入验证
4. 异常处理机制验证
5. 性能优化验证
"""

import sys
import os
from datetime import datetime
import asyncio
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
from config.settings import settings as config
from utils.logger_utils import get_logger, db
from ai.claude_analyzer import ClaudeAnalyzer
from strategies.indicators import calc_bollinger_bands, calc_bollinger_bandwidth, calc_bollinger_percent_b
import pandas as pd
import numpy as np

logger = get_logger("test_optimization")


class TestOptimization:
    """优化测试类"""

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


def test_config_unification():
    """测试1: 配置统一性验证"""
    print("验证配置项是否正确统一...")

    # 检查config.py中是否有必要的配置项
    assert hasattr(config, 'ENABLE_STRATEGIES'), "缺少 ENABLE_STRATEGIES 配置"
    assert hasattr(config, 'USE_CONSENSUS_SIGNAL'), "缺少 USE_CONSENSUS_SIGNAL 配置"
    assert hasattr(config, 'MIN_STRATEGY_AGREEMENT'), "缺少 MIN_STRATEGY_AGREEMENT 配置"

    # 检查新增的配置项
    assert hasattr(config, 'CLAUDE_TIMEOUT'), "缺少 CLAUDE_TIMEOUT 配置"
    assert hasattr(config, 'DB_BATCH_SIZE'), "缺少 DB_BATCH_SIZE 配置"
    assert hasattr(config, 'DB_BATCH_FLUSH_INTERVAL'), "缺少 DB_BATCH_FLUSH_INTERVAL 配置"
    assert hasattr(config, 'MAX_CONSECUTIVE_ERRORS'), "缺少 MAX_CONSECUTIVE_ERRORS 配置"
    assert hasattr(config, 'ERROR_BACKOFF_SECONDS'), "缺少 ERROR_BACKOFF_SECONDS 配置"

    # 检查config/strategies.py是否已删除
    strategies_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'strategies.py')
    assert not os.path.exists(strategies_path), "config/strategies.py 应该已被删除"

    print("✓ 配置统一性验证通过")


def test_claude_async():
    """测试2: Claude异步化验证"""
    print("验证Claude异步方法是否存在...")

    analyzer = ClaudeAnalyzer()

    # 检查异步方法是否存在
    assert hasattr(analyzer, 'analyze_signal_async'), "缺少 analyze_signal_async 方法"
    assert hasattr(analyzer, '_call_claude_api_sync'), "缺少 _call_claude_api_sync 方法"
    assert hasattr(analyzer, '_executor'), "缺少 _executor 线程池"

    # 检查超时配置
    assert hasattr(analyzer, 'timeout'), "缺少 timeout 属性"

    print("✓ Claude异步化验证通过")


def test_database_batch_write():
    """测试3: 数据库批量写入验证"""
    print("验证数据库批量写入机制...")

    # 检查数据库对象是否有批量写入相关属性
    assert hasattr(db, '_trade_buffer'), "缺少 _trade_buffer 缓冲区"
    assert hasattr(db, '_signal_buffer'), "缺少 _signal_buffer 缓冲区"
    assert hasattr(db, '_batch_size'), "缺少 _batch_size 配置"
    assert hasattr(db, '_batch_flush_interval'), "缺少 _batch_flush_interval 配置"

    # 检查批量写入方法
    assert hasattr(db, '_flush_trade_buffer'), "缺少 _flush_trade_buffer 方法"
    assert hasattr(db, '_flush_signal_buffer'), "缺少 _flush_signal_buffer 方法"

    # 验证配置值
    assert db._batch_size > 0, "批量大小必须大于0"
    assert db._batch_flush_interval > 0, "刷新间隔必须大于0"

    print(f"✓ 数据库批量写入验证通过 (batch_size={db._batch_size}, flush_interval={db._batch_flush_interval}s)")


def test_error_handling():
    """测试4: 异常处理配置验证"""
    print("验证异常处理配置...")

    # 检查错误处理配置项
    assert hasattr(config, 'MAX_CONSECUTIVE_ERRORS'), "缺少 MAX_CONSECUTIVE_ERRORS 配置"
    assert hasattr(config, 'ERROR_BACKOFF_SECONDS'), "缺少 ERROR_BACKOFF_SECONDS 配置"

    # 验证配置值合理性
    assert config.MAX_CONSECUTIVE_ERRORS > 0, "最大连续错误次数必须大于0"
    assert config.ERROR_BACKOFF_SECONDS > 0, "错误退避时间必须大于0"

    print(f"✓ 异常处理配置验证通过 (max_errors={config.MAX_CONSECUTIVE_ERRORS}, backoff={config.ERROR_BACKOFF_SECONDS}s)")


def test_indicators_optimization():
    """测试5: 指标优化验证"""
    print("验证指标计算优化...")

    # 创建测试数据
    np.random.seed(42)
    close_prices = pd.Series(100 + np.random.randn(100).cumsum())

    # 测试优化前的调用方式（不传入bands）
    bandwidth1 = calc_bollinger_bandwidth(close_prices, period=20, std_dev=2)
    assert len(bandwidth1) == len(close_prices), "bandwidth计算结果长度不匹配"

    # 测试优化后的调用方式（传入预计算的bands）
    bands = calc_bollinger_bands(close_prices, period=20, std_dev=2)
    bandwidth2 = calc_bollinger_bandwidth(close_prices, period=20, std_dev=2, bands=bands)
    percent_b = calc_bollinger_percent_b(close_prices, period=20, std_dev=2, bands=bands)

    # 验证结果一致性
    assert len(bandwidth2) == len(close_prices), "优化后bandwidth计算结果长度不匹配"
    assert len(percent_b) == len(close_prices), "percent_b计算结果长度不匹配"

    # 验证优化后的性能提升（通过减少重复计算）
    # 两种方式的结果应该相同
    assert (bandwidth1.fillna(0) == bandwidth2.fillna(0)).all(), "优化前后结果不一致"

    print("✓ 指标优化验证通过")


def test_performance_improvement():
    """测试6: 性能提升验证"""
    print("验证性能优化效果...")

    # 创建测试数据
    np.random.seed(42)
    close_prices = pd.Series(100 + np.random.randn(1000).cumsum())

    # 测试优化前（重复计算）
    start = time.time()
    for _ in range(10):
        calc_bollinger_bandwidth(close_prices, period=20, std_dev=2)
        calc_bollinger_percent_b(close_prices, period=20, std_dev=2)
    time_before = time.time() - start

    # 测试优化后（复用计算）
    start = time.time()
    for _ in range(10):
        bands = calc_bollinger_bands(close_prices, period=20, std_dev=2)
        calc_bollinger_bandwidth(close_prices, period=20, std_dev=2, bands=bands)
        calc_bollinger_percent_b(close_prices, period=20, std_dev=2, bands=bands)
    time_after = time.time() - start

    improvement = (time_before - time_after) / time_before * 100

    print(f"  优化前耗时: {time_before:.4f}s")
    print(f"  优化后耗时: {time_after:.4f}s")
    print(f"  性能提升: {improvement:.1f}%")

    # 验证确实有性能提升
    assert time_after < time_before, "优化后性能应该更好"

    print("✓ 性能提升验证通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("项目优化验证测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestOptimization()

    # 运行所有测试
    tester.run_test("配置统一性验证", test_config_unification)
    tester.run_test("Claude异步化验证", test_claude_async)
    tester.run_test("数据库批量写入验证", test_database_batch_write)
    tester.run_test("异常处理配置验证", test_error_handling)
    tester.run_test("指标优化验证", test_indicators_optimization)
    tester.run_test("性能提升验证", test_performance_improvement)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
