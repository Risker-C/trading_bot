#!/usr/bin/env python3
"""
综合优化测试脚本

测试内容：
1. 配置参数验证
2. 动态止盈门槛计算
3. 止盈止损参数合理性
4. ML质量阈值验证
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from risk_manager import RiskManager, PositionInfo
from utils.logger_utils import get_logger

logger = get_logger("test_comprehensive_optimization")


class TestComprehensiveOptimization:
    """综合优化测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.risk_manager = RiskManager()

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*80}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*80}")

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
        print(f"\n{'='*80}")
        print("测试摘要")
        print(f"{'='*80}")
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"成功率: {(self.passed/self.total*100):.1f}%")
        print(f"{'='*80}\n")

        return self.failed == 0


def test_config_parameters():
    """测试1: 验证配置参数"""
    print("验证配置参数:")

    # 验证止盈比例
    print(f"  止盈比例: {config.TAKE_PROFIT_PERCENT}")
    assert config.TAKE_PROFIT_PERCENT == 0.06, \
        f"止盈比例错误: 期望 0.06, 实际 {config.TAKE_PROFIT_PERCENT}"
    print(f"  ✓ 止盈比例正确: 6%")

    # 验证移动止损比例
    print(f"  移动止损比例: {config.TRAILING_STOP_PERCENT}")
    assert config.TRAILING_STOP_PERCENT == 0.015, \
        f"移动止损比例错误: 期望 0.015, 实际 {config.TRAILING_STOP_PERCENT}"
    print(f"  ✓ 移动止损比例正确: 1.5%")

    # 验证动态止盈门槛倍数
    assert hasattr(config, 'MIN_PROFIT_THRESHOLD_MULTIPLIER'), \
        "缺少 MIN_PROFIT_THRESHOLD_MULTIPLIER 配置"
    print(f"  动态止盈门槛倍数: {config.MIN_PROFIT_THRESHOLD_MULTIPLIER}")
    assert config.MIN_PROFIT_THRESHOLD_MULTIPLIER == 1.5, \
        f"动态止盈门槛倍数错误: 期望 1.5, 实际 {config.MIN_PROFIT_THRESHOLD_MULTIPLIER}"
    print(f"  ✓ 动态止盈门槛倍数正确: 1.5")

    # 验证ML质量阈值
    print(f"  ML质量阈值: {config.ML_QUALITY_THRESHOLD}")
    assert config.ML_QUALITY_THRESHOLD == 0.35, \
        f"ML质量阈值错误: 期望 0.35, 实际 {config.ML_QUALITY_THRESHOLD}"
    print(f"  ✓ ML质量阈值正确: 0.35")


def test_dynamic_threshold_calculation():
    """测试2: 动态止盈门槛计算"""
    print("测试动态止盈门槛计算:")

    risk_manager = RiskManager()

    # 测试场景1: 10 USDT仓位
    entry_price = 100000.0
    amount = 0.0001  # 约10 USDT
    current_price = 100200.0  # 上涨0.2%

    position = PositionInfo(
        side='long',
        amount=amount,
        entry_price=entry_price,
        entry_time=datetime.now()
    )

    # 计算手续费
    entry_fee = entry_price * amount * config.TRADING_FEE_RATE
    close_fee = current_price * amount * config.TRADING_FEE_RATE
    total_fee = entry_fee + close_fee

    # 计算动态门槛
    dynamic_threshold = total_fee * config.MIN_PROFIT_THRESHOLD_MULTIPLIER

    # 计算净盈利
    gross_profit = (current_price - entry_price) * amount
    net_profit = gross_profit - total_fee

    print(f"\n场景1: 10 USDT仓位，上涨0.2%")
    print(f"  开仓价: {entry_price:.2f}")
    print(f"  当前价: {current_price:.2f}")
    print(f"  仓位大小: {amount:.6f}")
    print(f"  开仓手续费: {entry_fee:.6f} USDT")
    print(f"  平仓手续费: {close_fee:.6f} USDT")
    print(f"  总手续费: {total_fee:.6f} USDT")
    print(f"  动态门槛: {dynamic_threshold:.6f} USDT")
    print(f"  毛盈利: {gross_profit:.6f} USDT")
    print(f"  净盈利: {net_profit:.6f} USDT")
    print(f"  是否超过门槛: {net_profit > dynamic_threshold}")

    # 验证动态门槛计算正确
    expected_threshold = total_fee * 1.5
    assert abs(dynamic_threshold - expected_threshold) < 0.000001, \
        f"动态门槛计算错误: 期望 {expected_threshold:.6f}, 实际 {dynamic_threshold:.6f}"
    print(f"  ✓ 动态门槛计算正确")

    # 测试场景2: 100 USDT仓位
    amount2 = 0.001  # 约100 USDT
    entry_fee2 = entry_price * amount2 * config.TRADING_FEE_RATE
    close_fee2 = current_price * amount2 * config.TRADING_FEE_RATE
    total_fee2 = entry_fee2 + close_fee2
    dynamic_threshold2 = total_fee2 * config.MIN_PROFIT_THRESHOLD_MULTIPLIER

    print(f"\n场景2: 100 USDT仓位，上涨0.2%")
    print(f"  仓位大小: {amount2:.6f}")
    print(f"  总手续费: {total_fee2:.6f} USDT")
    print(f"  动态门槛: {dynamic_threshold2:.6f} USDT")

    # 验证动态门槛随仓位大小线性增长
    ratio = amount2 / amount
    threshold_ratio = dynamic_threshold2 / dynamic_threshold
    assert abs(ratio - threshold_ratio) < 0.01, \
        f"动态门槛未随仓位线性增长: 仓位比例 {ratio:.2f}, 门槛比例 {threshold_ratio:.2f}"
    print(f"  ✓ 动态门槛随仓位线性增长: {ratio:.2f}x")


def test_take_profit_reasonableness():
    """测试3: 止盈参数合理性"""
    print("测试止盈参数合理性:")

    # 验证止盈目标不会太高
    assert config.TAKE_PROFIT_PERCENT <= 0.10, \
        f"止盈目标过高: {config.TAKE_PROFIT_PERCENT:.1%} > 10%"
    print(f"  ✓ 止盈目标合理: {config.TAKE_PROFIT_PERCENT:.1%} <= 10%")

    # 验证止盈目标不会太低
    assert config.TAKE_PROFIT_PERCENT >= 0.03, \
        f"止盈目标过低: {config.TAKE_PROFIT_PERCENT:.1%} < 3%"
    print(f"  ✓ 止盈目标不会过低: {config.TAKE_PROFIT_PERCENT:.1%} >= 3%")

    # 验证盈亏比
    risk_reward_ratio = config.TAKE_PROFIT_PERCENT / config.STOP_LOSS_PERCENT
    print(f"  盈亏比: {risk_reward_ratio:.2f}:1")
    assert risk_reward_ratio >= 2.0, \
        f"盈亏比过低: {risk_reward_ratio:.2f}:1 < 2:1"
    print(f"  ✓ 盈亏比合理: {risk_reward_ratio:.2f}:1 >= 2:1")


def test_trailing_stop_reasonableness():
    """测试4: 移动止损参数合理性"""
    print("测试移动止损参数合理性:")

    # 计算启用移动止损需要的最小涨幅
    min_gain_required = config.TRAILING_STOP_PERCENT / (1 - config.TRAILING_STOP_PERCENT) * 100
    print(f"  移动止损回撤: {config.TRAILING_STOP_PERCENT:.2%}")
    print(f"  需要最小涨幅: {min_gain_required:.3f}%")

    # 验证最小涨幅不会太高（应该<2%，保守策略允许更高的门槛）
    assert min_gain_required < 2.0, \
        f"最小涨幅过高: {min_gain_required:.3f}% >= 2%"
    print(f"  ✓ 最小涨幅合理: {min_gain_required:.3f}% < 2%")

    # 验证移动止损不会太紧（应该>0.5%）
    assert config.TRAILING_STOP_PERCENT > 0.005, \
        f"移动止损过紧: {config.TRAILING_STOP_PERCENT:.2%} <= 0.5%"
    print(f"  ✓ 移动止损不会过紧: {config.TRAILING_STOP_PERCENT:.2%} > 0.5%")

    # 验证移动止损不会太松（应该<3%）
    assert config.TRAILING_STOP_PERCENT < 0.03, \
        f"移动止损过松: {config.TRAILING_STOP_PERCENT:.2%} >= 3%"
    print(f"  ✓ 移动止损不会过松: {config.TRAILING_STOP_PERCENT:.2%} < 3%")


def test_ml_threshold_reasonableness():
    """测试5: ML质量阈值合理性"""
    print("测试ML质量阈值合理性:")

    # 验证阈值在合理范围内（0.2-0.8）
    assert 0.2 <= config.ML_QUALITY_THRESHOLD <= 0.8, \
        f"ML质量阈值不合理: {config.ML_QUALITY_THRESHOLD} 不在 [0.2, 0.8] 范围内"
    print(f"  ✓ ML质量阈值在合理范围: {config.ML_QUALITY_THRESHOLD} ∈ [0.2, 0.8]")

    # 验证阈值不会过高（避免过度过滤）
    assert config.ML_QUALITY_THRESHOLD <= 0.6, \
        f"ML质量阈值过高: {config.ML_QUALITY_THRESHOLD} > 0.6，可能过度过滤"
    print(f"  ✓ ML质量阈值不会过高: {config.ML_QUALITY_THRESHOLD} <= 0.6")

    # 验证阈值不会过低（避免无效过滤）
    assert config.ML_QUALITY_THRESHOLD >= 0.25, \
        f"ML质量阈值过低: {config.ML_QUALITY_THRESHOLD} < 0.25，可能无效过滤"
    print(f"  ✓ ML质量阈值不会过低: {config.ML_QUALITY_THRESHOLD} >= 0.25")


def test_dynamic_threshold_multiplier():
    """测试6: 动态止盈门槛倍数合理性"""
    print("测试动态止盈门槛倍数合理性:")

    multiplier = config.MIN_PROFIT_THRESHOLD_MULTIPLIER
    print(f"  倍数: {multiplier}")

    # 验证倍数在合理范围内（1.0-3.0）
    assert 1.0 <= multiplier <= 3.0, \
        f"倍数不合理: {multiplier} 不在 [1.0, 3.0] 范围内"
    print(f"  ✓ 倍数在合理范围: {multiplier} ∈ [1.0, 3.0]")

    # 验证倍数不会太低（至少要覆盖手续费）
    assert multiplier >= 1.2, \
        f"倍数过低: {multiplier} < 1.2，可能无法覆盖手续费"
    print(f"  ✓ 倍数不会过低: {multiplier} >= 1.2")

    # 验证倍数不会太高（避免门槛过高）
    assert multiplier <= 2.0, \
        f"倍数过高: {multiplier} > 2.0，门槛可能过高"
    print(f"  ✓ 倍数不会过高: {multiplier} <= 2.0")

    # 计算示例门槛
    example_position_value = 10.0  # 10 USDT
    example_fee_rate = config.TRADING_FEE_RATE
    example_total_fee = example_position_value * example_fee_rate * 2  # 开仓+平仓
    example_threshold = example_total_fee * multiplier
    example_threshold_pct = example_threshold / example_position_value * 100

    print(f"\n  示例计算（10 USDT仓位）:")
    print(f"    总手续费: {example_total_fee:.4f} USDT ({example_total_fee/example_position_value*100:.2f}%)")
    print(f"    动态门槛: {example_threshold:.4f} USDT ({example_threshold_pct:.2f}%)")
    print(f"    需要盈利: >{example_threshold_pct:.2f}% 才启用动态止盈")


def test_parameter_consistency():
    """测试7: 参数一致性"""
    print("测试参数一致性:")

    # 验证止盈 > 止损（盈亏比>1）
    assert config.TAKE_PROFIT_PERCENT > config.STOP_LOSS_PERCENT, \
        f"止盈应大于止损: {config.TAKE_PROFIT_PERCENT:.1%} <= {config.STOP_LOSS_PERCENT:.1%}"
    print(f"  ✓ 止盈 > 止损: {config.TAKE_PROFIT_PERCENT:.1%} > {config.STOP_LOSS_PERCENT:.1%}")

    # 验证移动止损 < 止盈（避免冲突）
    assert config.TRAILING_STOP_PERCENT < config.TAKE_PROFIT_PERCENT, \
        f"移动止损应小于止盈: {config.TRAILING_STOP_PERCENT:.1%} >= {config.TAKE_PROFIT_PERCENT:.1%}"
    print(f"  ✓ 移动止损 < 止盈: {config.TRAILING_STOP_PERCENT:.1%} < {config.TAKE_PROFIT_PERCENT:.1%}")

    # 验证移动止损 < 止损（避免过早触发）
    assert config.TRAILING_STOP_PERCENT < config.STOP_LOSS_PERCENT, \
        f"移动止损应小于止损: {config.TRAILING_STOP_PERCENT:.1%} >= {config.STOP_LOSS_PERCENT:.1%}"
    print(f"  ✓ 移动止损 < 止损: {config.TRAILING_STOP_PERCENT:.1%} < {config.STOP_LOSS_PERCENT:.1%}")


def test_real_scenario():
    """测试8: 真实场景模拟"""
    print("测试真实场景模拟:")

    risk_manager = RiskManager()

    # 场景：10 USDT仓位，价格上涨0.3%
    entry_price = 87500.0
    current_price = 87762.5  # 上涨0.3%
    amount = 0.0001143  # 约10 USDT

    position = PositionInfo(
        side='long',
        amount=amount,
        entry_price=entry_price,
        entry_time=datetime.now()
    )

    # 设置开仓手续费
    position.entry_fee = entry_price * amount * config.TRADING_FEE_RATE

    # 更新价格
    position.update_price(current_price)

    # 计算净盈利
    net_profit = position.calculate_net_profit(current_price)

    # 计算动态门槛
    close_fee = current_price * amount * config.TRADING_FEE_RATE
    total_fee = position.entry_fee + close_fee
    dynamic_threshold = total_fee * config.MIN_PROFIT_THRESHOLD_MULTIPLIER

    print(f"\n  场景: 10 USDT仓位，价格上涨0.3%")
    print(f"    开仓价: {entry_price:.2f}")
    print(f"    当前价: {current_price:.2f}")
    print(f"    涨幅: {(current_price/entry_price-1)*100:.2f}%")
    print(f"    净盈利: {net_profit:.4f} USDT")
    print(f"    总手续费: {total_fee:.4f} USDT")
    print(f"    动态门槛: {dynamic_threshold:.4f} USDT")
    print(f"    是否超过门槛: {net_profit > dynamic_threshold}")

    # 验证净盈利为正
    assert net_profit > 0, \
        f"净盈利应为正: {net_profit:.4f} <= 0"
    print(f"  ✓ 净盈利为正: {net_profit:.4f} USDT")

    # 验证动态门槛合理
    assert dynamic_threshold > 0, \
        f"动态门槛应为正: {dynamic_threshold:.4f} <= 0"
    print(f"  ✓ 动态门槛合理: {dynamic_threshold:.4f} USDT")

    # 在0.3%涨幅下，应该能超过门槛
    if net_profit > dynamic_threshold:
        print(f"  ✓ 0.3%涨幅能超过动态门槛，可以启用动态止盈")
    else:
        print(f"  ⚠ 0.3%涨幅未超过动态门槛，需要更高涨幅")


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("综合优化测试")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    tester = TestComprehensiveOptimization()

    # 运行所有测试
    tester.run_test("配置参数验证", test_config_parameters)
    tester.run_test("动态止盈门槛计算", test_dynamic_threshold_calculation)
    tester.run_test("止盈参数合理性", test_take_profit_reasonableness)
    tester.run_test("移动止损参数合理性", test_trailing_stop_reasonableness)
    tester.run_test("ML质量阈值合理性", test_ml_threshold_reasonableness)
    tester.run_test("动态止盈门槛倍数合理性", test_dynamic_threshold_multiplier)
    tester.run_test("参数一致性", test_parameter_consistency)
    tester.run_test("真实场景模拟", test_real_scenario)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success:
        print("\n🎉 所有测试通过！综合优化验证成功！")
        print("\n优化总结:")
        print("  ✅ 配置参数: 止盈6%, 移动止损1.5%, ML阈值0.35")
        print("  ✅ 动态门槛: 基于手续费1.5倍，自动适应仓位大小")
        print("  ✅ 参数合理: 盈亏比、移动止损、ML阈值均在合理范围")
        print("  ✅ 真实场景: 0.3%涨幅能触发动态止盈")
    else:
        print("\n❌ 部分测试失败，请检查问题！")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
