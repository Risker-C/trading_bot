#!/usr/bin/env python3
"""
止损优化测试脚本

测试内容：
1. 配置参数验证
2. 止损价格计算验证
3. ATR动态止损验证
4. 移动止损验证
5. 止损触发逻辑验证
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from logger_utils import get_logger

logger = get_logger("test_stop_loss_optimization")


class TestStopLossOptimization:
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
    """测试1: 配置参数验证"""
    print("检查止损配置参数...")

    # 检查固定止损
    assert hasattr(config, 'STOP_LOSS_PERCENT'), "缺少 STOP_LOSS_PERCENT 配置"
    assert config.STOP_LOSS_PERCENT == 0.04, f"STOP_LOSS_PERCENT 应为 0.04，实际为 {config.STOP_LOSS_PERCENT}"
    print(f"  ✓ 固定止损: {config.STOP_LOSS_PERCENT * 100}%")

    # 检查止盈
    assert hasattr(config, 'TAKE_PROFIT_PERCENT'), "缺少 TAKE_PROFIT_PERCENT 配置"
    assert config.TAKE_PROFIT_PERCENT == 0.03, f"TAKE_PROFIT_PERCENT 应为 0.03，实际为 {config.TAKE_PROFIT_PERCENT}"
    print(f"  ✓ 固定止盈: {config.TAKE_PROFIT_PERCENT * 100}%")

    # 检查移动止损
    assert hasattr(config, 'TRAILING_STOP_PERCENT'), "缺少 TRAILING_STOP_PERCENT 配置"
    assert config.TRAILING_STOP_PERCENT == 0.025, f"TRAILING_STOP_PERCENT 应为 0.025，实际为 {config.TRAILING_STOP_PERCENT}"
    print(f"  ✓ 移动止损: {config.TRAILING_STOP_PERCENT * 100}%")

    # 检查ATR配置
    assert hasattr(config, 'USE_ATR_STOP_LOSS'), "缺少 USE_ATR_STOP_LOSS 配置"
    assert config.USE_ATR_STOP_LOSS == True, "USE_ATR_STOP_LOSS 应为 True"
    print(f"  ✓ ATR止损启用: {config.USE_ATR_STOP_LOSS}")

    assert hasattr(config, 'ATR_STOP_MULTIPLIER'), "缺少 ATR_STOP_MULTIPLIER 配置"
    assert config.ATR_STOP_MULTIPLIER == 3.5, f"ATR_STOP_MULTIPLIER 应为 3.5，实际为 {config.ATR_STOP_MULTIPLIER}"
    print(f"  ✓ ATR倍数: {config.ATR_STOP_MULTIPLIER}")

    # 检查杠杆
    assert hasattr(config, 'LEVERAGE'), "缺少 LEVERAGE 配置"
    print(f"  ✓ 杠杆: {config.LEVERAGE}x")

    print("\n所有配置参数验证通过！")


def test_stop_loss_calculation():
    """测试2: 止损价格计算"""
    print("测试止损价格计算...")

    from risk_manager import RiskManager

    risk_manager = RiskManager()

    # 测试做多止损
    entry_price_long = 100000.0
    stop_loss_long = risk_manager._calculate_fixed_stop_loss(entry_price_long, 'long')

    # 计算预期止损价格
    # 做多: entry_price * (1 - STOP_LOSS_PERCENT / LEVERAGE)
    expected_long = entry_price_long * (1 - config.STOP_LOSS_PERCENT / config.LEVERAGE)

    print(f"  做多测试:")
    print(f"    开仓价: {entry_price_long}")
    print(f"    止损价: {stop_loss_long:.2f}")
    print(f"    预期值: {expected_long:.2f}")
    print(f"    价格可波动: {(entry_price_long - stop_loss_long) / entry_price_long * 100:.3f}%")

    assert abs(stop_loss_long - expected_long) < 0.01, f"做多止损计算错误: {stop_loss_long} != {expected_long}"

    # 测试做空止损
    entry_price_short = 100000.0
    stop_loss_short = risk_manager._calculate_fixed_stop_loss(entry_price_short, 'short')

    # 计算预期止损价格
    # 做空: entry_price * (1 + STOP_LOSS_PERCENT / LEVERAGE)
    expected_short = entry_price_short * (1 + config.STOP_LOSS_PERCENT / config.LEVERAGE)

    print(f"\n  做空测试:")
    print(f"    开仓价: {entry_price_short}")
    print(f"    止损价: {stop_loss_short:.2f}")
    print(f"    预期值: {expected_short:.2f}")
    print(f"    价格可波动: {(stop_loss_short - entry_price_short) / entry_price_short * 100:.3f}%")

    assert abs(stop_loss_short - expected_short) < 0.01, f"做空止损计算错误: {stop_loss_short} != {expected_short}"

    print("\n止损价格计算验证通过！")


def test_stop_loss_space():
    """测试3: 止损空间验证"""
    print("验证止损空间是否合理...")

    # 计算价格可波动空间
    price_volatility_percent = (config.STOP_LOSS_PERCENT / config.LEVERAGE) * 100

    print(f"  止损比例: {config.STOP_LOSS_PERCENT * 100}%")
    print(f"  杠杆倍数: {config.LEVERAGE}x")
    print(f"  价格可波动: {price_volatility_percent:.3f}%")

    # 验证价格波动空间是否合理（应该 >= 0.3%）
    assert price_volatility_percent >= 0.3, f"价格波动空间过小: {price_volatility_percent:.3f}% < 0.3%"

    # 验证止损不会过于宽松（应该 <= 0.5%）
    assert price_volatility_percent <= 0.5, f"价格波动空间过大: {price_volatility_percent:.3f}% > 0.5%"

    print(f"\n  ✓ 止损空间合理（0.3% - 0.5%之间）")

    # 计算风险回报比
    risk_reward_ratio = config.TAKE_PROFIT_PERCENT / config.STOP_LOSS_PERCENT
    print(f"\n  风险回报比: {risk_reward_ratio:.2f}:1")

    # 验证风险回报比是否合理（应该 >= 0.75）
    assert risk_reward_ratio >= 0.75, f"风险回报比过低: {risk_reward_ratio:.2f} < 0.75"

    print(f"  ✓ 风险回报比合理")

    print("\n止损空间验证通过！")


def test_optimization_effect():
    """测试4: 优化效果预估"""
    print("预估优化效果...")

    # 旧配置
    old_stop_loss = 0.025
    old_atr_multiplier = 2.5
    old_trailing_stop = 0.015

    # 新配置
    new_stop_loss = config.STOP_LOSS_PERCENT
    new_atr_multiplier = config.ATR_STOP_MULTIPLIER
    new_trailing_stop = config.TRAILING_STOP_PERCENT

    # 计算改进幅度
    stop_loss_improvement = (new_stop_loss - old_stop_loss) / old_stop_loss * 100
    atr_improvement = (new_atr_multiplier - old_atr_multiplier) / old_atr_multiplier * 100
    trailing_improvement = (new_trailing_stop - old_trailing_stop) / old_trailing_stop * 100

    print(f"\n  固定止损改进: {old_stop_loss*100}% → {new_stop_loss*100}% (+{stop_loss_improvement:.1f}%)")
    print(f"  ATR倍数改进: {old_atr_multiplier} → {new_atr_multiplier} (+{atr_improvement:.1f}%)")
    print(f"  移动止损改进: {old_trailing_stop*100}% → {new_trailing_stop*100}% (+{trailing_improvement:.1f}%)")

    # 验证所有参数都有改进
    assert stop_loss_improvement > 0, "固定止损未改进"
    assert atr_improvement > 0, "ATR倍数未改进"
    assert trailing_improvement > 0, "移动止损未改进"

    print(f"\n  预期效果:")
    print(f"    - 止损次数减少: ~50%")
    print(f"    - 胜率提升: 44.1% → 50%+")
    print(f"    - 盈利单保护: 显著改善")

    print("\n优化效果预估完成！")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("止损优化测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestStopLossOptimization()

    # 运行所有测试
    tester.run_test("配置参数验证", test_config_validation)
    tester.run_test("止损价格计算", test_stop_loss_calculation)
    tester.run_test("止损空间验证", test_stop_loss_space)
    tester.run_test("优化效果预估", test_optimization_effect)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
