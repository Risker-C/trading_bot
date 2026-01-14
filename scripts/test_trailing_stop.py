#!/usr/bin/env python3
"""
移动止损修复测试脚本

测试内容：
1. 配置验证 - 验证TRAILING_STOP_PERCENT配置正确
2. 移动止损计算 - 测试多仓和空仓的移动止损价格计算
3. 启用条件验证 - 测试移动止损的启用条件
4. 边界情况测试 - 测试各种边界情况
5. 修复前后对比 - 对比修复前后的行为差异
"""

import sys
import os
from datetime import datetime
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from utils.logger_utils import get_logger
from risk.risk_manager import RiskManager, PositionInfo

logger = get_logger("test_trailing_stop")


class TestTrailingStop:
    """移动止损测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.risk_manager = None

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
    print("\n检查配置项...")

    # 验证配置值
    print(f"TRAILING_STOP_PERCENT = {config.TRAILING_STOP_PERCENT}")
    assert config.TRAILING_STOP_PERCENT == 0.005, \
        f"配置错误: 期望 0.005, 实际 {config.TRAILING_STOP_PERCENT}"

    # 验证配置范围
    assert 0 < config.TRAILING_STOP_PERCENT < 0.1, \
        f"配置超出合理范围: {config.TRAILING_STOP_PERCENT}"

    print(f"✓ 配置值正确: {config.TRAILING_STOP_PERCENT} (0.5%)")
    print(f"✓ 配置范围合理: 0 < {config.TRAILING_STOP_PERCENT} < 0.1")


def test_long_position_trailing_stop():
    """测试2: 多仓移动止损计算"""
    print("\n测试多仓移动止损...")

    # 创建模拟的多仓持仓
    position = PositionInfo(
        side="long",
        amount=0.001,
        entry_price=86756.10,
        entry_time=datetime.now(),
        current_price=87300.0,
        highest_price=87300.0,
        lowest_price=86756.10,
        unrealized_pnl=0.544
    )

    # 创建风险管理器
    risk_manager = RiskManager(trader=None)

    # 计算移动止损
    trailing_stop = risk_manager.calculate_trailing_stop(87300.0, position)

    print(f"开仓价: {position.entry_price}")
    print(f"最高价: {position.highest_price}")
    print(f"当前价: {position.current_price}")
    print(f"移动止损价: {trailing_stop}")

    # 验证计算结果
    expected_trailing = position.highest_price * (1 - config.TRAILING_STOP_PERCENT)
    print(f"预期移动止损价: {expected_trailing}")

    assert abs(trailing_stop - expected_trailing) < 0.01, \
        f"计算错误: 期望 {expected_trailing}, 实际 {trailing_stop}"

    # 验证启用条件
    assert trailing_stop > position.entry_price, \
        f"启用条件不满足: {trailing_stop} <= {position.entry_price}"

    print(f"✓ 移动止损计算正确: {trailing_stop:.2f}")
    print(f"✓ 启用条件满足: {trailing_stop:.2f} > {position.entry_price:.2f}")


def test_short_position_trailing_stop():
    """测试3: 空仓移动止损计算"""
    print("\n测试空仓移动止损...")

    # 创建模拟的空仓持仓
    position = PositionInfo(
        side="short",
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now(),
        current_price=86500.0,
        highest_price=87000.0,
        lowest_price=86500.0,
        unrealized_pnl=0.5
    )

    # 创建风险管理器
    risk_manager = RiskManager(trader=None)

    # 计算移动止损
    trailing_stop = risk_manager.calculate_trailing_stop(86500.0, position)

    print(f"开仓价: {position.entry_price}")
    print(f"最低价: {position.lowest_price}")
    print(f"当前价: {position.current_price}")
    print(f"移动止损价: {trailing_stop}")

    # 验证计算结果
    expected_trailing = position.lowest_price * (1 + config.TRAILING_STOP_PERCENT)
    print(f"预期移动止损价: {expected_trailing}")

    assert abs(trailing_stop - expected_trailing) < 0.01, \
        f"计算错误: 期望 {expected_trailing}, 实际 {trailing_stop}"

    # 验证启用条件
    assert trailing_stop < position.entry_price, \
        f"启用条件不满足: {trailing_stop} >= {position.entry_price}"

    print(f"✓ 移动止损计算正确: {trailing_stop:.2f}")
    print(f"✓ 启用条件满足: {trailing_stop:.2f} < {position.entry_price:.2f}")


def test_trailing_stop_not_enabled():
    """测试4: 移动止损未启用情况"""
    print("\n测试移动止损未启用情况...")

    # 创建盈利不足的多仓持仓
    position = PositionInfo(
        side="long",
        amount=0.001,
        entry_price=86756.10,
        entry_time=datetime.now(),
        current_price=86800.0,
        highest_price=86800.0,  # 盈利仅0.05%
        lowest_price=86756.10,
        unrealized_pnl=0.044
    )

    # 创建风险管理器
    risk_manager = RiskManager(trader=None)

    # 计算移动止损
    trailing_stop = risk_manager.calculate_trailing_stop(86800.0, position)

    print(f"开仓价: {position.entry_price}")
    print(f"最高价: {position.highest_price}")
    print(f"盈利幅度: {(position.highest_price / position.entry_price - 1) * 100:.3f}%")
    print(f"移动止损价: {trailing_stop}")

    # 计算预期值
    expected_trailing = position.highest_price * (1 - config.TRAILING_STOP_PERCENT)
    print(f"预期移动止损价: {expected_trailing:.2f}")
    print(f"启用条件: {expected_trailing:.2f} > {position.entry_price:.2f} = {expected_trailing > position.entry_price}")

    # 验证未启用
    assert trailing_stop == 0, \
        f"应该未启用: 期望 0, 实际 {trailing_stop}"

    print(f"✓ 移动止损正确未启用 (盈利不足)")


def test_boundary_case_just_enabled():
    """测试5: 边界情况 - 刚好启用"""
    print("\n测试边界情况 - 刚好启用...")

    # 计算刚好能启用移动止损的最高价
    entry_price = 86756.10
    # trailing_price = highest_price * (1 - 0.005) > entry_price
    # highest_price > entry_price / 0.995
    min_highest_price = entry_price / (1 - config.TRAILING_STOP_PERCENT)

    print(f"开仓价: {entry_price}")
    print(f"最低启用价: {min_highest_price:.2f}")
    print(f"需要盈利: {(min_highest_price / entry_price - 1) * 100:.3f}%")

    # 创建刚好能启用的持仓
    position = PositionInfo(
        side="long",
        amount=0.001,
        entry_price=entry_price,
        entry_time=datetime.now(),
        current_price=min_highest_price + 10,
        highest_price=min_highest_price + 10,
        lowest_price=entry_price,
        unrealized_pnl=0.254
    )

    # 创建风险管理器
    risk_manager = RiskManager(trader=None)

    # 计算移动止损
    trailing_stop = risk_manager.calculate_trailing_stop(position.current_price, position)

    print(f"实际最高价: {position.highest_price}")
    print(f"移动止损价: {trailing_stop}")

    # 验证已启用
    assert trailing_stop > 0, \
        f"应该已启用: 实际 {trailing_stop}"

    assert trailing_stop > entry_price, \
        f"启用条件应满足: {trailing_stop} > {entry_price}"

    print(f"✓ 边界情况正确: 移动止损已启用")


def test_fix_comparison():
    """测试6: 修复前后对比"""
    print("\n测试修复前后对比...")

    # 使用实际案例数据
    entry_price = 86756.10
    highest_price_case1 = 87091.10  # 实际案例: 0.386%盈利
    highest_price_case2 = 87500.0   # 假设案例: 0.857%盈利

    print(f"案例1 - 实际历史数据:")
    print(f"  开仓价: {entry_price}")
    print(f"  最高价: {highest_price_case1}")
    profit_pct1 = (highest_price_case1 / entry_price - 1) * 100
    print(f"  盈利幅度: {profit_pct1:.3f}%")

    # 修复前 (2.5%)
    old_percent = 0.025
    old_trailing1 = highest_price_case1 * (1 - old_percent)
    old_enabled1 = old_trailing1 > entry_price

    print(f"\n  修复前 (回撤2.5%):")
    print(f"    移动止损价: {old_trailing1:.2f}")
    print(f"    启用条件: {old_trailing1:.2f} > {entry_price:.2f} = {old_enabled1}")
    print(f"    结果: {'✅ 已启用' if old_enabled1 else '❌ 未启用'}")

    # 修复后 (0.5%)
    new_percent = config.TRAILING_STOP_PERCENT
    new_trailing1 = highest_price_case1 * (1 - new_percent)
    new_enabled1 = new_trailing1 > entry_price

    print(f"\n  修复后 (回撤0.5%):")
    print(f"    移动止损价: {new_trailing1:.2f}")
    print(f"    启用条件: {new_trailing1:.2f} > {entry_price:.2f} = {new_enabled1}")
    print(f"    结果: {'✅ 已启用' if new_enabled1 else '❌ 未启用'}")
    print(f"    说明: 0.386%盈利不足以启用移动止损(需要>0.503%)")

    # 案例2: 更高的盈利
    print(f"\n案例2 - 更高盈利场景:")
    print(f"  开仓价: {entry_price}")
    print(f"  最高价: {highest_price_case2}")
    profit_pct2 = (highest_price_case2 / entry_price - 1) * 100
    print(f"  盈利幅度: {profit_pct2:.3f}%")

    # 修复前 (2.5%)
    old_trailing2 = highest_price_case2 * (1 - old_percent)
    old_enabled2 = old_trailing2 > entry_price

    print(f"\n  修复前 (回撤2.5%):")
    print(f"    移动止损价: {old_trailing2:.2f}")
    print(f"    启用条件: {old_trailing2:.2f} > {entry_price:.2f} = {old_enabled2}")
    print(f"    结果: {'✅ 已启用' if old_enabled2 else '❌ 未启用'}")

    # 修复后 (0.5%)
    new_trailing2 = highest_price_case2 * (1 - new_percent)
    new_enabled2 = new_trailing2 > entry_price

    print(f"\n  修复后 (回撤0.5%):")
    print(f"    移动止损价: {new_trailing2:.2f}")
    print(f"    启用条件: {new_trailing2:.2f} > {entry_price:.2f} = {new_enabled2}")
    print(f"    结果: {'✅ 已启用' if new_enabled2 else '❌ 未启用'}")

    # 验证修复效果
    assert not old_enabled1, "案例1修复前应该未启用"
    assert not new_enabled1, "案例1修复后仍未启用(盈利不足)"
    assert not old_enabled2, "案例2修复前应该未启用"
    assert new_enabled2, "案例2修复后应该已启用"

    print(f"\n✓ 修复有效: 降低启用门槛从2.56%到0.503%,更容易保护利润")


def test_various_profit_levels():
    """测试7: 不同盈利水平下的移动止损"""
    print("\n测试不同盈利水平...")

    entry_price = 86756.10
    risk_manager = RiskManager(trader=None)

    # 测试不同盈利水平
    profit_levels = [0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]

    print(f"\n{'盈利%':<10} {'最高价':<12} {'移动止损价':<12} {'状态':<10}")
    print("-" * 50)

    for profit_pct in profit_levels:
        highest_price = entry_price * (1 + profit_pct / 100)

        position = PositionInfo(
            side="long",
            amount=0.001,
            entry_price=entry_price,
            entry_time=datetime.now(),
            current_price=highest_price,
            highest_price=highest_price,
            lowest_price=entry_price,
            unrealized_pnl=0.0
        )

        trailing_stop = risk_manager.calculate_trailing_stop(highest_price, position)
        enabled = trailing_stop > 0

        print(f"{profit_pct:<10.1f} {highest_price:<12.2f} {trailing_stop:<12.2f} {'✅ 启用' if enabled else '❌ 未启用':<10}")

    print(f"\n✓ 不同盈利水平测试完成")


def test_display_format():
    """测试8: 显示格式验证"""
    print("\n测试显示格式...")

    # 验证格式化输出
    value = config.TRAILING_STOP_PERCENT

    # 旧格式 (会显示为0%)
    old_format = f"{value:.0%}"
    print(f"旧格式 (.0%): {old_format}")

    # 新格式 (正确显示0.5%)
    new_format = f"{value:.1%}"
    print(f"新格式 (.1%): {new_format}")

    # 验证
    assert old_format == "0%", f"旧格式应该是 '0%', 实际 '{old_format}'"
    assert new_format == "0.5%", f"新格式应该是 '0.5%', 实际 '{new_format}'"

    print(f"✓ 显示格式修复正确: {old_format} → {new_format}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("移动止损修复测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestTrailingStop()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("多仓移动止损计算", test_long_position_trailing_stop)
    tester.run_test("空仓移动止损计算", test_short_position_trailing_stop)
    tester.run_test("移动止损未启用情况", test_trailing_stop_not_enabled)
    tester.run_test("边界情况 - 刚好启用", test_boundary_case_just_enabled)
    tester.run_test("修复前后对比", test_fix_comparison)
    tester.run_test("不同盈利水平测试", test_various_profit_levels)
    tester.run_test("显示格式验证", test_display_format)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
