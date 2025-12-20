#!/usr/bin/env python3
"""
方向过滤器测试脚本

测试内容：
1. 配置验证
2. 做多信号过滤（严格标准）
3. 做空信号过滤（正常标准）
4. 趋势确认逻辑
5. 自适应阈值调整
6. 边界条件测试
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from direction_filter import DirectionFilter, get_direction_filter
from strategies import Signal, TradeSignal
from logger_utils import get_logger

logger = get_logger("test_direction_filter")


class TestDirectionFilter:
    """测试类"""

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
    print("检查配置项是否存在...")

    # 检查必需的配置项
    assert hasattr(config, 'ENABLE_DIRECTION_FILTER'), "缺少 ENABLE_DIRECTION_FILTER 配置"
    assert hasattr(config, 'LONG_MIN_STRENGTH'), "缺少 LONG_MIN_STRENGTH 配置"
    assert hasattr(config, 'LONG_MIN_AGREEMENT'), "缺少 LONG_MIN_AGREEMENT 配置"
    assert hasattr(config, 'SHORT_MIN_STRENGTH'), "缺少 SHORT_MIN_STRENGTH 配置"
    assert hasattr(config, 'SHORT_MIN_AGREEMENT'), "缺少 SHORT_MIN_AGREEMENT 配置"

    print(f"✓ ENABLE_DIRECTION_FILTER = {config.ENABLE_DIRECTION_FILTER}")
    print(f"✓ LONG_MIN_STRENGTH = {config.LONG_MIN_STRENGTH}")
    print(f"✓ LONG_MIN_AGREEMENT = {config.LONG_MIN_AGREEMENT}")
    print(f"✓ SHORT_MIN_STRENGTH = {config.SHORT_MIN_STRENGTH}")
    print(f"✓ SHORT_MIN_AGREEMENT = {config.SHORT_MIN_AGREEMENT}")

    # 检查配置值的合理性
    assert 0 <= config.LONG_MIN_STRENGTH <= 1, "LONG_MIN_STRENGTH 应在 0-1 之间"
    assert 0 <= config.LONG_MIN_AGREEMENT <= 1, "LONG_MIN_AGREEMENT 应在 0-1 之间"
    assert 0 <= config.SHORT_MIN_STRENGTH <= 1, "SHORT_MIN_STRENGTH 应在 0-1 之间"
    assert 0 <= config.SHORT_MIN_AGREEMENT <= 1, "SHORT_MIN_AGREEMENT 应在 0-1 之间"

    print("✓ 所有配置值在合理范围内")


def test_filter_initialization():
    """测试2: 过滤器初始化"""
    print("测试过滤器初始化...")

    # 创建过滤器实例
    filter1 = DirectionFilter()
    assert filter1 is not None, "过滤器创建失败"
    print(f"✓ 过滤器实例创建成功")

    # 检查初始阈值（优化后的值）
    assert filter1.long_min_strength == 0.80, "做多信号强度阈值不正确"
    assert filter1.short_min_strength == 0.5, "做空信号强度阈值不正确"
    assert filter1.long_min_agreement == 0.75, "做多策略一致性阈值不正确"
    assert filter1.short_min_agreement == 0.6, "做空策略一致性阈值不正确"
    print(f"✓ 初始阈值设置正确")

    # 测试单例模式
    filter2 = get_direction_filter()
    filter3 = get_direction_filter()
    assert filter2 is filter3, "单例模式失败"
    print(f"✓ 单例模式工作正常")


def create_test_dataframe(trend_type='uptrend'):
    """创建测试用的DataFrame"""
    # 生成100根K线数据
    dates = pd.date_range(start='2024-01-01', periods=100, freq='15min')

    if trend_type == 'uptrend':
        # 上涨趋势：价格逐步上升
        close_prices = np.linspace(50000, 52000, 100)
        # 添加一些随机波动
        close_prices += np.random.randn(100) * 100
        # 最近3根K线收阳
        close_prices[-3:] = [51800, 51900, 52000]
        open_prices = close_prices - 50  # 收阳

    elif trend_type == 'downtrend':
        # 下跌趋势：价格逐步下降
        close_prices = np.linspace(52000, 50000, 100)
        close_prices += np.random.randn(100) * 100
        open_prices = close_prices + 50  # 收阴

    else:  # sideways
        # 震荡：价格在范围内波动
        close_prices = 51000 + np.random.randn(100) * 200
        open_prices = close_prices + np.random.randn(100) * 50

    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_prices,
        'high': np.maximum(open_prices, close_prices) + np.random.rand(100) * 50,
        'low': np.minimum(open_prices, close_prices) - np.random.rand(100) * 50,
        'close': close_prices,
        'volume': np.random.rand(100) * 1000000
    })

    return df


def test_long_signal_strong():
    """测试3: 做多信号 - 强信号应通过"""
    print("测试强做多信号...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('uptrend')

    # 创建强做多信号
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.85,  # 高于阈值0.80
        strategy="test_strategy",
        reason="测试强信号"
    )

    strategy_agreement = 0.8  # 高于阈值0.75

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert passed, f"强做多信号应该通过，但被拒绝: {reason}"


def test_long_signal_weak_strength():
    """测试4: 做多信号 - 信号强度不足应拒绝"""
    print("测试弱做多信号（强度不足）...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('uptrend')

    # 创建弱做多信号（强度不足）
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.7,  # 低于阈值0.80
        strategy="test_strategy",
        reason="测试弱信号"
    )

    strategy_agreement = 0.8

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert not passed, "弱做多信号应该被拒绝"
    assert "信号强度不足" in reason, f"拒绝原因不正确: {reason}"


def test_long_signal_weak_agreement():
    """测试5: 做多信号 - 策略一致性不足应拒绝"""
    print("测试做多信号（策略一致性不足）...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('uptrend')

    # 创建做多信号（策略一致性不足）
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.85,  # 强度足够
        strategy="test_strategy",
        reason="测试策略一致性"
    )

    strategy_agreement = 0.7  # 低于阈值0.75

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert not passed, "策略一致性不足的做多信号应该被拒绝"
    assert "策略一致性不足" in reason, f"拒绝原因不正确: {reason}"


def test_long_signal_no_uptrend():
    """测试6: 做多信号 - 无上涨趋势应拒绝"""
    print("测试做多信号（无上涨趋势）...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('downtrend')  # 下跌趋势

    # 创建做多信号
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.85,
        strategy="test_strategy",
        reason="测试趋势确认"
    )

    strategy_agreement = 0.8

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert not passed, "下跌趋势中的做多信号应该被拒绝"
    assert "上涨趋势" in reason, f"拒绝原因不正确: {reason}"


def test_short_signal_normal():
    """测试7: 做空信号 - 正常标准"""
    print("测试做空信号（正常标准）...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('downtrend')

    # 创建做空信号（满足正常标准）
    signal = TradeSignal(
        signal=Signal.SHORT,
        strength=0.6,  # 高于阈值0.5
        strategy="test_strategy",
        reason="测试做空信号"
    )

    strategy_agreement = 0.65  # 高于阈值0.6

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert passed, f"正常做空信号应该通过，但被拒绝: {reason}"


def test_short_signal_weak():
    """测试8: 做空信号 - 弱信号应拒绝"""
    print("测试弱做空信号...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('downtrend')

    # 创建弱做空信号
    signal = TradeSignal(
        signal=Signal.SHORT,
        strength=0.4,  # 低于阈值0.5
        strategy="test_strategy",
        reason="测试弱做空信号"
    )

    strategy_agreement = 0.65

    passed, reason = filter_obj.filter_signal(signal, df, strategy_agreement)

    print(f"过滤结果: {passed}")
    print(f"原因: {reason}")

    assert not passed, "弱做空信号应该被拒绝"
    assert "信号强度不足" in reason, f"拒绝原因不正确: {reason}"


def test_uptrend_detection():
    """测试9: 上涨趋势检测"""
    print("测试上涨趋势检测逻辑...")

    filter_obj = DirectionFilter()

    # 测试上涨趋势
    df_up = create_test_dataframe('uptrend')
    is_uptrend = filter_obj._check_uptrend(df_up)
    print(f"上涨趋势检测结果: {is_uptrend}")
    assert is_uptrend, "应该检测到上涨趋势"

    # 测试下跌趋势
    df_down = create_test_dataframe('downtrend')
    is_uptrend = filter_obj._check_uptrend(df_down)
    print(f"下跌趋势检测结果: {is_uptrend}")
    assert not is_uptrend, "不应该检测到上涨趋势"

    # 测试震荡市场
    df_side = create_test_dataframe('sideways')
    is_uptrend = filter_obj._check_uptrend(df_side)
    print(f"震荡市场检测结果: {is_uptrend}")
    # 震荡市场可能通过也可能不通过，取决于随机数据


def test_adaptive_thresholds():
    """测试10: 自适应阈值调整"""
    print("测试自适应阈值调整...")

    filter_obj = DirectionFilter()

    # 记录初始阈值
    initial_long_strength = filter_obj.long_min_strength
    initial_short_strength = filter_obj.short_min_strength
    print(f"初始做多强度阈值: {initial_long_strength}")
    print(f"初始做空强度阈值: {initial_short_strength}")

    # 测试场景1: 做多胜率过低
    print("\n场景1: 做多胜率过低（< 30%）")
    filter_obj.update_thresholds(long_win_rate=0.25, short_win_rate=0.35)
    print(f"调整后做多强度阈值: {filter_obj.long_min_strength}")
    print(f"调整后做多一致性阈值: {filter_obj.long_min_agreement}")
    assert filter_obj.long_min_strength > initial_long_strength, "做多胜率低时应提高阈值"

    # 重置
    filter_obj = DirectionFilter()

    # 测试场景2: 做空胜率良好
    print("\n场景2: 做空胜率良好（> 40%）")
    filter_obj.update_thresholds(long_win_rate=0.35, short_win_rate=0.45)
    print(f"调整后做空强度阈值: {filter_obj.short_min_strength}")
    print(f"调整后做空一致性阈值: {filter_obj.short_min_agreement}")
    assert filter_obj.short_min_strength < initial_short_strength, "做空胜率高时应放宽阈值"


def test_boundary_conditions():
    """测试11: 边界条件"""
    print("测试边界条件...")

    filter_obj = DirectionFilter()
    df = create_test_dataframe('uptrend')

    # 测试1: 信号强度刚好等于阈值
    print("\n子测试1: 信号强度刚好等于阈值")
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.80,  # 刚好等于阈值
        strategy="test_strategy",
        reason="边界测试"
    )
    passed, reason = filter_obj.filter_signal(signal, df, 0.75)
    print(f"结果: {passed}, 原因: {reason}")
    assert passed, "信号强度等于阈值应该通过"

    # 测试2: 策略一致性为0
    print("\n子测试2: 策略一致性为0")
    signal = TradeSignal(
        signal=Signal.LONG,
        strength=0.85,
        strategy="test_strategy",
        reason="边界测试"
    )
    passed, reason = filter_obj.filter_signal(signal, df, 0.0)
    print(f"结果: {passed}, 原因: {reason}")
    assert not passed, "策略一致性为0应该被拒绝"

    # 测试3: 策略一致性为1
    print("\n子测试3: 策略一致性为1")
    passed, reason = filter_obj.filter_signal(signal, df, 1.0)
    print(f"结果: {passed}, 原因: {reason}")
    # 应该通过（如果趋势也满足）

    # 测试4: 数据不足（少于55根K线）
    print("\n子测试4: 数据不足")
    df_short = df.head(50)  # 只有50根K线
    passed, reason = filter_obj.filter_signal(signal, df_short, 0.8)
    print(f"结果: {passed}, 原因: {reason}")
    # 数据不足时趋势检测会失败


def test_integration():
    """测试12: 集成测试"""
    print("测试完整的过滤流程...")

    filter_obj = get_direction_filter()

    # 模拟真实场景：多个信号依次过滤
    test_cases = [
        {
            'name': '强做多信号 + 上涨趋势',
            'signal': TradeSignal(
                signal=Signal.LONG,
                strategy="strategy1",
                reason="强信号",
                strength=0.85
            ),
            'df': create_test_dataframe('uptrend'),
            'agreement': 0.8,
            'should_pass': True
        },
        {
            'name': '弱做多信号 + 上涨趋势',
            'signal': TradeSignal(
                signal=Signal.LONG,
                strategy="strategy2",
                reason="弱信号",
                strength=0.7
            ),
            'df': create_test_dataframe('uptrend'),
            'agreement': 0.8,
            'should_pass': False
        },
        {
            'name': '强做多信号 + 下跌趋势',
            'signal': TradeSignal(
                signal=Signal.LONG,
                strategy="strategy3",
                reason="强信号但趋势不对",
                strength=0.85
            ),
            'df': create_test_dataframe('downtrend'),
            'agreement': 0.8,
            'should_pass': False
        },
        {
            'name': '正常做空信号',
            'signal': TradeSignal(
                signal=Signal.SHORT,
                strategy="strategy4",
                reason="正常做空",
                strength=0.6
            ),
            'df': create_test_dataframe('downtrend'),
            'agreement': 0.7,
            'should_pass': True
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n  场景{i}: {case['name']}")
        passed, reason = filter_obj.filter_signal(
            case['signal'],
            case['df'],
            case['agreement']
        )
        print(f"  结果: {'通过' if passed else '拒绝'}")
        print(f"  原因: {reason}")

        if case['should_pass']:
            assert passed, f"场景{i}应该通过但被拒绝: {reason}"
        else:
            assert not passed, f"场景{i}应该被拒绝但通过了"

    print("\n✓ 所有集成测试场景通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("方向过滤器测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestDirectionFilter()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("过滤器初始化", test_filter_initialization)
    tester.run_test("做多信号 - 强信号应通过", test_long_signal_strong)
    tester.run_test("做多信号 - 信号强度不足应拒绝", test_long_signal_weak_strength)
    tester.run_test("做多信号 - 策略一致性不足应拒绝", test_long_signal_weak_agreement)
    tester.run_test("做多信号 - 无上涨趋势应拒绝", test_long_signal_no_uptrend)
    tester.run_test("做空信号 - 正常标准", test_short_signal_normal)
    tester.run_test("做空信号 - 弱信号应拒绝", test_short_signal_weak)
    tester.run_test("上涨趋势检测", test_uptrend_detection)
    tester.run_test("自适应阈值调整", test_adaptive_thresholds)
    tester.run_test("边界条件", test_boundary_conditions)
    tester.run_test("集成测试", test_integration)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
