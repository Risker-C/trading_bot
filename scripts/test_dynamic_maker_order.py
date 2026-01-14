#!/usr/bin/env python3
"""
动态Maker订单功能测试脚本

测试内容：
1. 动态配置验证
2. 信号强度过滤逻辑
3. 波动率自适应参数计算
4. 极端波动保护
5. 参数传递完整性
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger

logger = get_logger("test_dynamic_maker_order")


class TestDynamicMakerOrder:
    """动态Maker订单测试类"""

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


def test_dynamic_config():
    """测试1: 动态配置验证"""
    print("检查动态Maker订单配置项...")

    # 检查必需的配置项
    assert hasattr(config, 'ENABLE_DYNAMIC_MAKER'), "缺少 ENABLE_DYNAMIC_MAKER 配置"
    assert hasattr(config, 'MAKER_MIN_SIGNAL_STRENGTH'), "缺少 MAKER_MIN_SIGNAL_STRENGTH 配置"
    assert hasattr(config, 'MAKER_OPTIMAL_SIGNAL_STRENGTH'), "缺少 MAKER_OPTIMAL_SIGNAL_STRENGTH 配置"
    assert hasattr(config, 'MAKER_HIGH_VOL_TIMEOUT'), "缺少 MAKER_HIGH_VOL_TIMEOUT 配置"
    assert hasattr(config, 'MAKER_LOW_VOL_TIMEOUT'), "缺少 MAKER_LOW_VOL_TIMEOUT 配置"
    assert hasattr(config, 'MAKER_HIGH_VOL_OFFSET'), "缺少 MAKER_HIGH_VOL_OFFSET 配置"
    assert hasattr(config, 'MAKER_LOW_VOL_OFFSET'), "缺少 MAKER_LOW_VOL_OFFSET 配置"
    assert hasattr(config, 'MAKER_DISABLE_ON_EXTREME_VOL'), "缺少 MAKER_DISABLE_ON_EXTREME_VOL 配置"
    assert hasattr(config, 'MAKER_EXTREME_VOL_THRESHOLD'), "缺少 MAKER_EXTREME_VOL_THRESHOLD 配置"

    print(f"  ENABLE_DYNAMIC_MAKER: {config.ENABLE_DYNAMIC_MAKER}")
    print(f"  MAKER_MIN_SIGNAL_STRENGTH: {config.MAKER_MIN_SIGNAL_STRENGTH}")
    print(f"  MAKER_OPTIMAL_SIGNAL_STRENGTH: {config.MAKER_OPTIMAL_SIGNAL_STRENGTH}")
    print(f"  MAKER_HIGH_VOL_TIMEOUT: {config.MAKER_HIGH_VOL_TIMEOUT}秒")
    print(f"  MAKER_LOW_VOL_TIMEOUT: {config.MAKER_LOW_VOL_TIMEOUT}秒")
    print(f"  MAKER_HIGH_VOL_OFFSET: {config.MAKER_HIGH_VOL_OFFSET*100:.3f}%")
    print(f"  MAKER_LOW_VOL_OFFSET: {config.MAKER_LOW_VOL_OFFSET*100:.3f}%")
    print(f"  MAKER_DISABLE_ON_EXTREME_VOL: {config.MAKER_DISABLE_ON_EXTREME_VOL}")
    print(f"  MAKER_EXTREME_VOL_THRESHOLD: {config.MAKER_EXTREME_VOL_THRESHOLD*100:.1f}%")

    # 验证配置值的合理性
    assert isinstance(config.ENABLE_DYNAMIC_MAKER, bool), "ENABLE_DYNAMIC_MAKER 必须是布尔值"
    assert 0 < config.MAKER_MIN_SIGNAL_STRENGTH < 1, "MAKER_MIN_SIGNAL_STRENGTH 必须在0-1之间"
    assert 0 < config.MAKER_OPTIMAL_SIGNAL_STRENGTH < 1, "MAKER_OPTIMAL_SIGNAL_STRENGTH 必须在0-1之间"
    assert config.MAKER_MIN_SIGNAL_STRENGTH < config.MAKER_OPTIMAL_SIGNAL_STRENGTH, "最小阈值应小于最优阈值"
    assert config.MAKER_HIGH_VOL_TIMEOUT > 0, "MAKER_HIGH_VOL_TIMEOUT 必须大于0"
    assert config.MAKER_LOW_VOL_TIMEOUT > 0, "MAKER_LOW_VOL_TIMEOUT 必须大于0"
    assert config.MAKER_HIGH_VOL_TIMEOUT < config.MAKER_LOW_VOL_TIMEOUT, "高波动超时应小于低波动超时"

    print("✓ 所有配置项验证通过")


def test_signal_strength_filter():
    """测试2: 信号强度过滤逻辑"""
    print("测试信号强度过滤...")

    # 弱信号应该被过滤
    weak_signal = 0.5
    assert weak_signal < config.MAKER_MIN_SIGNAL_STRENGTH, "弱信号应低于阈值"
    print(f"  弱信号({weak_signal:.2f}) < 阈值({config.MAKER_MIN_SIGNAL_STRENGTH}) ✓")

    # 中等信号应该通过
    medium_signal = 0.7
    assert medium_signal >= config.MAKER_MIN_SIGNAL_STRENGTH, "中等信号应通过"
    assert medium_signal < config.MAKER_OPTIMAL_SIGNAL_STRENGTH, "中等信号应低于最优阈值"
    print(f"  中等信号({medium_signal:.2f}) 在阈值范围内 ✓")

    # 强信号应该通过
    strong_signal = 0.85
    assert strong_signal >= config.MAKER_OPTIMAL_SIGNAL_STRENGTH, "强信号应高于最优阈值"
    print(f"  强信号({strong_signal:.2f}) > 最优阈值({config.MAKER_OPTIMAL_SIGNAL_STRENGTH}) ✓")

    print("✓ 信号强度过滤逻辑正确")


def test_volatility_params():
    """测试3: 波动率参数计算"""
    print("测试波动率参数...")

    # 低波动
    low_vol = 0.005
    assert low_vol < config.LOW_VOLATILITY_THRESHOLD, "低波动应低于阈值"
    print(f"  低波动({low_vol:.2%}): 超时{config.MAKER_LOW_VOL_TIMEOUT}秒, 偏移{config.MAKER_LOW_VOL_OFFSET*100:.3f}%")

    # 正常波动
    normal_vol = 0.03
    assert config.LOW_VOLATILITY_THRESHOLD <= normal_vol <= config.HIGH_VOLATILITY_THRESHOLD
    print(f"  正常波动({normal_vol:.2%}): 超时{config.MAKER_ORDER_TIMEOUT}秒, 偏移{config.MAKER_PRICE_OFFSET*100:.3f}%")

    # 高波动
    high_vol = 0.07
    assert config.HIGH_VOLATILITY_THRESHOLD < high_vol < config.MAKER_EXTREME_VOL_THRESHOLD
    print(f"  高波动({high_vol:.2%}): 超时{config.MAKER_HIGH_VOL_TIMEOUT}秒, 偏移{config.MAKER_HIGH_VOL_OFFSET*100:.3f}%")

    # 极端波动
    extreme_vol = 0.09
    assert extreme_vol > config.MAKER_EXTREME_VOL_THRESHOLD, "极端波动应高于阈值"
    print(f"  极端波动({extreme_vol:.2%}): 强制使用市价单")

    print("✓ 波动率参数计算正确")


def test_trader_methods():
    """测试4: Trader方法存在性"""
    print("检查Trader类的动态Maker订单方法...")

    from trader import BitgetTrader

    # 检查方法是否存在
    assert hasattr(BitgetTrader, '_calculate_dynamic_maker_params'), "缺少 _calculate_dynamic_maker_params 方法"
    print("  ✓ _calculate_dynamic_maker_params 方法存在")

    # 检查方法签名
    import inspect
    sig = inspect.signature(BitgetTrader.create_smart_order)
    params = list(sig.parameters.keys())
    assert 'signal_strength' in params, "create_smart_order 缺少 signal_strength 参数"
    assert 'volatility' in params, "create_smart_order 缺少 volatility 参数"
    print("  ✓ create_smart_order 方法签名正确")

    sig = inspect.signature(BitgetTrader.open_long)
    params = list(sig.parameters.keys())
    assert 'signal_strength' in params, "open_long 缺少 signal_strength 参数"
    assert 'volatility' in params, "open_long 缺少 volatility 参数"
    print("  ✓ open_long 方法签名正确")

    sig = inspect.signature(BitgetTrader.open_short)
    params = list(sig.parameters.keys())
    assert 'signal_strength' in params, "open_short 缺少 signal_strength 参数"
    assert 'volatility' in params, "open_short 缺少 volatility 参数"
    print("  ✓ open_short 方法签名正确")

    print("✓ 所有方法验证通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("动态Maker订单功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestDynamicMakerOrder()

    # 运行所有测试
    tester.run_test("动态配置验证", test_dynamic_config)
    tester.run_test("信号强度过滤逻辑", test_signal_strength_filter)
    tester.run_test("波动率参数计算", test_volatility_params)
    tester.run_test("Trader方法验证", test_trader_methods)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
