#!/usr/bin/env python3
"""
动态止盈功能测试脚本

测试内容：
1. 配置验证
2. 手续费计算
3. 净盈利计算
4. 价格窗口管理
5. 价格均值计算
6. 动态止盈触发逻辑（多仓）
7. 动态止盈触发逻辑（空仓）
8. 盈利门槛检查
9. 价格窗口不足场景
10. 动态价格更新频率
"""

import sys
import os
from datetime import datetime
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from risk_manager import PositionInfo, RiskManager
from logger_utils import get_logger

logger = get_logger("test_trailing_take_profit")


class TestTrailingTakeProfit:
    """测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.risk_manager = RiskManager()

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
    print("检查动态止盈相关配置...")

    # 检查配置项是否存在
    assert hasattr(config, 'ENABLE_TRAILING_TAKE_PROFIT'), "缺少配置: ENABLE_TRAILING_TAKE_PROFIT"
    assert hasattr(config, 'MIN_PROFIT_THRESHOLD_USDT'), "缺少配置: MIN_PROFIT_THRESHOLD_USDT"
    assert hasattr(config, 'TRAILING_TP_PRICE_WINDOW'), "缺少配置: TRAILING_TP_PRICE_WINDOW"
    assert hasattr(config, 'TRAILING_TP_FALLBACK_PERCENT'), "缺少配置: TRAILING_TP_FALLBACK_PERCENT"
    assert hasattr(config, 'TRADING_FEE_RATE'), "缺少配置: TRADING_FEE_RATE"
    assert hasattr(config, 'ENABLE_DYNAMIC_CHECK_INTERVAL'), "缺少配置: ENABLE_DYNAMIC_CHECK_INTERVAL"
    assert hasattr(config, 'DEFAULT_CHECK_INTERVAL'), "缺少配置: DEFAULT_CHECK_INTERVAL"
    assert hasattr(config, 'POSITION_CHECK_INTERVAL'), "缺少配置: POSITION_CHECK_INTERVAL"

    # 检查配置值的合理性
    assert config.MIN_PROFIT_THRESHOLD_USDT > 0, "最小盈利门槛必须大于0"
    assert config.TRAILING_TP_PRICE_WINDOW >= 3, "价格窗口大小至少为3"
    assert 0 < config.TRAILING_TP_FALLBACK_PERCENT < 0.01, "回撤百分比应在0-1%之间"
    assert 0 < config.TRADING_FEE_RATE < 0.01, "手续费率应在0-1%之间"
    assert config.POSITION_CHECK_INTERVAL < config.DEFAULT_CHECK_INTERVAL, "持仓时检查间隔应小于默认间隔"

    print(f"✓ ENABLE_TRAILING_TAKE_PROFIT = {config.ENABLE_TRAILING_TAKE_PROFIT}")
    print(f"✓ MIN_PROFIT_THRESHOLD_USDT = {config.MIN_PROFIT_THRESHOLD_USDT}")
    print(f"✓ TRAILING_TP_PRICE_WINDOW = {config.TRAILING_TP_PRICE_WINDOW}")
    print(f"✓ TRAILING_TP_FALLBACK_PERCENT = {config.TRAILING_TP_FALLBACK_PERCENT}")
    print(f"✓ TRADING_FEE_RATE = {config.TRADING_FEE_RATE}")
    print(f"✓ POSITION_CHECK_INTERVAL = {config.POSITION_CHECK_INTERVAL}秒")
    print(f"✓ DEFAULT_CHECK_INTERVAL = {config.DEFAULT_CHECK_INTERVAL}秒")


def test_entry_fee_calculation():
    """测试2: 手续费计算"""
    print("测试开仓手续费计算...")

    # 创建测试持仓
    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )

    # 计算手续费
    entry_fee = position.calculate_entry_fee(87000.0, 0.001)

    # 验证计算结果
    expected_fee = 87000.0 * 0.001 * config.TRADING_FEE_RATE
    assert abs(entry_fee - expected_fee) < 0.0001, f"手续费计算错误: {entry_fee} != {expected_fee}"

    print(f"✓ 开仓价: 87000.0")
    print(f"✓ 数量: 0.001")
    print(f"✓ 手续费率: {config.TRADING_FEE_RATE}")
    print(f"✓ 计算结果: {entry_fee:.4f} USDT")
    print(f"✓ 预期结果: {expected_fee:.4f} USDT")


def test_net_profit_calculation():
    """测试3: 净盈利计算"""
    print("测试净盈利计算...")

    # 创建测试持仓（多仓）
    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )
    position.entry_fee = position.calculate_entry_fee(87000.0, 0.001)

    # 测试盈利场景
    current_price = 87500.0
    net_profit = position.calculate_net_profit(current_price)

    # 验证计算
    gross_profit = (87500.0 - 87000.0) * 0.001  # 0.5 USDT
    close_fee = 87500.0 * 0.001 * config.TRADING_FEE_RATE
    expected_net_profit = gross_profit - position.entry_fee - close_fee

    assert abs(net_profit - expected_net_profit) < 0.0001, f"净盈利计算错误: {net_profit} != {expected_net_profit}"

    print(f"✓ 开仓价: 87000.0")
    print(f"✓ 当前价: 87500.0")
    print(f"✓ 毛盈利: {gross_profit:.4f} USDT")
    print(f"✓ 开仓手续费: {position.entry_fee:.4f} USDT")
    print(f"✓ 平仓手续费: {close_fee:.4f} USDT")
    print(f"✓ 净盈利: {net_profit:.4f} USDT")

    # 测试亏损场景
    current_price = 86500.0
    net_profit = position.calculate_net_profit(current_price)
    assert net_profit < 0, "亏损场景应该返回负值"
    print(f"✓ 亏损场景净盈利: {net_profit:.4f} USDT")


def test_price_window_management():
    """测试4: 价格窗口管理"""
    print("测试价格窗口管理...")

    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )

    # 添加价格到窗口
    prices = [87100, 87200, 87300, 87400, 87500, 87600, 87700]
    for price in prices:
        position.update_recent_prices(price)

    # 验证窗口大小
    assert len(position.recent_prices) == config.TRAILING_TP_PRICE_WINDOW, \
        f"窗口大小错误: {len(position.recent_prices)} != {config.TRAILING_TP_PRICE_WINDOW}"

    # 验证窗口内容（应该保留最后N个）
    expected_prices = prices[-config.TRAILING_TP_PRICE_WINDOW:]
    assert position.recent_prices == expected_prices, \
        f"窗口内容错误: {position.recent_prices} != {expected_prices}"

    print(f"✓ 添加价格: {prices}")
    print(f"✓ 窗口大小: {len(position.recent_prices)}")
    print(f"✓ 窗口内容: {position.recent_prices}")


def test_price_average_calculation():
    """测试5: 价格均值计算"""
    print("测试价格均值计算...")

    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )

    # 添加价格
    prices = [87100, 87200, 87300, 87400, 87500]
    for price in prices:
        position.update_recent_prices(price)

    # 计算均值
    avg = position.get_price_average()
    expected_avg = sum(prices) / len(prices)

    assert abs(avg - expected_avg) < 0.01, f"均值计算错误: {avg} != {expected_avg}"

    print(f"✓ 价格列表: {prices}")
    print(f"✓ 计算均值: {avg:.2f}")
    print(f"✓ 预期均值: {expected_avg:.2f}")


def test_trailing_tp_trigger_long():
    """测试6: 动态止盈触发逻辑（多仓）"""
    print("测试动态止盈触发逻辑（多仓）...")

    # 创建风险管理器和持仓
    risk_manager = RiskManager()
    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )
    position.entry_fee = position.calculate_entry_fee(87000.0, 0.001)

    # 模拟价格上涨，达到盈利门槛
    prices = [87100, 87200, 87300, 87400, 87500]
    for price in prices:
        trailing_tp = risk_manager.calculate_trailing_take_profit(price, position)
        # 前几次不应触发（窗口未满或未跌破均值）
        if len(position.recent_prices) < config.TRAILING_TP_PRICE_WINDOW:
            assert trailing_tp == 0, f"窗口未满时不应触发: {trailing_tp}"

    print(f"✓ 价格上涨阶段: {prices}")
    print(f"✓ 最大盈利: {position.max_profit:.4f} USDT")
    print(f"✓ 盈利门槛已达: {position.profit_threshold_reached}")

    # 计算当前价格均值和回撤阈值
    price_avg = position.get_price_average()
    fallback_threshold = price_avg * (1 - config.TRAILING_TP_FALLBACK_PERCENT)

    # 使用一个明显低于阈值的价格来触发
    # 注意：这个价格会被添加到窗口，所以要确保即使添加后仍然触发
    trigger_price = price_avg * 0.99  # 下跌1%，远大于0.1%的阈值

    trailing_tp = risk_manager.calculate_trailing_take_profit(trigger_price, position)

    assert trailing_tp > 0, f"应该触发止盈: {trailing_tp} (均值: {price_avg:.2f}, 阈值: {fallback_threshold:.2f}, 触发价: {trigger_price:.2f})"
    assert trailing_tp == trigger_price, f"止盈价格应该等于触发价格: {trailing_tp} != {trigger_price}"

    print(f"✓ 价格均值: {price_avg:.2f}")
    print(f"✓ 回撤阈值: {fallback_threshold:.2f}")
    print(f"✓ 触发价格: {trigger_price:.2f}")
    print(f"✓ 止盈价格: {trailing_tp:.2f}")


def test_trailing_tp_trigger_short():
    """测试7: 动态止盈触发逻辑（空仓）"""
    print("测试动态止盈触发逻辑（空仓）...")

    # 创建风险管理器和持仓
    risk_manager = RiskManager()
    position = PositionInfo(
        side='short',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )
    position.entry_fee = position.calculate_entry_fee(87000.0, 0.001)

    # 模拟价格下跌，达到盈利门槛
    prices = [86900, 86800, 86700, 86600, 86500]
    for price in prices:
        trailing_tp = risk_manager.calculate_trailing_take_profit(price, position)
        if len(position.recent_prices) < config.TRAILING_TP_PRICE_WINDOW:
            assert trailing_tp == 0, f"窗口未满时不应触发: {trailing_tp}"

    print(f"✓ 价格下跌阶段: {prices}")
    print(f"✓ 最大盈利: {position.max_profit:.4f} USDT")
    print(f"✓ 盈利门槛已达: {position.profit_threshold_reached}")

    # 计算当前价格均值和回撤阈值
    price_avg = position.get_price_average()
    fallback_threshold = price_avg * (1 + config.TRAILING_TP_FALLBACK_PERCENT)

    # 使用一个明显高于阈值的价格来触发
    # 注意：这个价格会被添加到窗口，所以要确保即使添加后仍然触发
    trigger_price = price_avg * 1.01  # 上涨1%，远大于0.1%的阈值

    trailing_tp = risk_manager.calculate_trailing_take_profit(trigger_price, position)

    assert trailing_tp > 0, f"应该触发止盈: {trailing_tp} (均值: {price_avg:.2f}, 阈值: {fallback_threshold:.2f}, 触发价: {trigger_price:.2f})"
    assert trailing_tp == trigger_price, f"止盈价格应该等于触发价格: {trailing_tp} != {trigger_price}"

    print(f"✓ 价格均值: {price_avg:.2f}")
    print(f"✓ 回撤阈值: {fallback_threshold:.2f}")
    print(f"✓ 触发价格: {trigger_price:.2f}")
    print(f"✓ 止盈价格: {trailing_tp:.2f}")


def test_profit_threshold_check():
    """测试8: 盈利门槛检查"""
    print("测试盈利门槛检查...")

    risk_manager = RiskManager()
    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )
    position.entry_fee = position.calculate_entry_fee(87000.0, 0.001)

    # 测试盈利未达门槛的情况
    # 计算一个刚好低于门槛的价格
    # 门槛 = 0.012 USDT
    # 需要的毛盈利 = 门槛 + 开仓手续费 + 平仓手续费
    # 毛盈利 = (价格差) * 数量

    # 使用一个很小的价格上涨
    small_increase_price = 87010.0  # 只上涨10 USDT
    trailing_tp = risk_manager.calculate_trailing_take_profit(small_increase_price, position)

    # 应该不触发（盈利未达门槛）
    assert trailing_tp == 0, f"盈利未达门槛时不应触发: {trailing_tp}"
    assert not position.profit_threshold_reached, "盈利门槛不应被标记为已达"

    print(f"✓ 小幅上涨价格: {small_increase_price}")
    print(f"✓ 净盈利: {position.calculate_net_profit(small_increase_price):.4f} USDT")
    print(f"✓ 盈利门槛: {config.MIN_PROFIT_THRESHOLD_USDT:.4f} USDT")
    print(f"✓ 门槛已达: {position.profit_threshold_reached}")

    # 测试盈利达到门槛的情况
    large_increase_price = 87500.0  # 上涨500 USDT
    trailing_tp = risk_manager.calculate_trailing_take_profit(large_increase_price, position)

    # 应该标记为已达门槛
    assert position.profit_threshold_reached, "盈利门槛应该被标记为已达"

    print(f"✓ 大幅上涨价格: {large_increase_price}")
    print(f"✓ 净盈利: {position.calculate_net_profit(large_increase_price):.4f} USDT")
    print(f"✓ 门槛已达: {position.profit_threshold_reached}")


def test_insufficient_price_window():
    """测试9: 价格窗口不足场景"""
    print("测试价格窗口不足场景...")

    risk_manager = RiskManager()
    position = PositionInfo(
        side='long',
        amount=0.001,
        entry_price=87000.0,
        entry_time=datetime.now()
    )
    position.entry_fee = position.calculate_entry_fee(87000.0, 0.001)
    position.profit_threshold_reached = True  # 手动设置为已达门槛

    # 只添加少量价格（少于窗口大小）
    prices = [87100, 87200]
    for price in prices:
        position.update_recent_prices(price)

    # 尝试触发止盈
    trailing_tp = risk_manager.calculate_trailing_take_profit(87000.0, position)

    # 应该不触发（窗口不足）
    assert trailing_tp == 0, f"窗口不足时不应触发: {trailing_tp}"

    print(f"✓ 价格窗口: {position.recent_prices}")
    print(f"✓ 窗口大小: {len(position.recent_prices)}")
    print(f"✓ 要求大小: {config.TRAILING_TP_PRICE_WINDOW}")
    print(f"✓ 触发结果: {trailing_tp}")


def test_dynamic_check_interval():
    """测试10: 动态价格更新频率"""
    print("测试动态价格更新频率配置...")

    # 验证配置
    assert config.ENABLE_DYNAMIC_CHECK_INTERVAL, "动态价格更新应该启用"
    assert config.POSITION_CHECK_INTERVAL < config.DEFAULT_CHECK_INTERVAL, \
        "持仓时检查间隔应小于默认间隔"

    print(f"✓ 动态价格更新: {config.ENABLE_DYNAMIC_CHECK_INTERVAL}")
    print(f"✓ 默认检查间隔: {config.DEFAULT_CHECK_INTERVAL}秒")
    print(f"✓ 持仓时检查间隔: {config.POSITION_CHECK_INTERVAL}秒")
    print(f"✓ 频率提升: {(config.DEFAULT_CHECK_INTERVAL / config.POSITION_CHECK_INTERVAL):.1f}倍")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("动态止盈功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestTrailingTakeProfit()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("手续费计算", test_entry_fee_calculation)
    tester.run_test("净盈利计算", test_net_profit_calculation)
    tester.run_test("价格窗口管理", test_price_window_management)
    tester.run_test("价格均值计算", test_price_average_calculation)
    tester.run_test("动态止盈触发逻辑（多仓）", test_trailing_tp_trigger_long)
    tester.run_test("动态止盈触发逻辑（空仓）", test_trailing_tp_trigger_short)
    tester.run_test("盈利门槛检查", test_profit_threshold_check)
    tester.run_test("价格窗口不足场景", test_insufficient_price_window)
    tester.run_test("动态价格更新频率", test_dynamic_check_interval)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
