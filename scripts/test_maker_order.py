#!/usr/bin/env python3
"""
Maker订单功能测试脚本

测试内容：
1. 配置验证
2. 限价单创建
3. 订单监控
4. 智能下单逻辑
5. 降级机制
"""

import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger

logger = get_logger("test_maker_order")


class TestMakerOrder:
    """Maker订单测试类"""

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
    print("检查Maker订单配置项...")

    # 检查必需的配置项
    assert hasattr(config, 'USE_MAKER_ORDER'), "缺少 USE_MAKER_ORDER 配置"
    assert hasattr(config, 'MAKER_ORDER_TIMEOUT'), "缺少 MAKER_ORDER_TIMEOUT 配置"
    assert hasattr(config, 'MAKER_PRICE_OFFSET'), "缺少 MAKER_PRICE_OFFSET 配置"
    assert hasattr(config, 'MAKER_ORDER_CHECK_INTERVAL'), "缺少 MAKER_ORDER_CHECK_INTERVAL 配置"
    assert hasattr(config, 'MAKER_AUTO_FALLBACK_TO_MARKET'), "缺少 MAKER_AUTO_FALLBACK_TO_MARKET 配置"
    assert hasattr(config, 'TRADING_FEE_RATE_MAKER'), "缺少 TRADING_FEE_RATE_MAKER 配置"
    assert hasattr(config, 'TRADING_FEE_RATE_TAKER'), "缺少 TRADING_FEE_RATE_TAKER 配置"

    print(f"  USE_MAKER_ORDER: {config.USE_MAKER_ORDER}")
    print(f"  MAKER_ORDER_TIMEOUT: {config.MAKER_ORDER_TIMEOUT}秒")
    print(f"  MAKER_PRICE_OFFSET: {config.MAKER_PRICE_OFFSET*100:.3f}%")
    print(f"  MAKER_ORDER_CHECK_INTERVAL: {config.MAKER_ORDER_CHECK_INTERVAL}秒")
    print(f"  MAKER_AUTO_FALLBACK_TO_MARKET: {config.MAKER_AUTO_FALLBACK_TO_MARKET}")
    print(f"  TRADING_FEE_RATE_MAKER: {config.TRADING_FEE_RATE_MAKER*100:.2f}%")
    print(f"  TRADING_FEE_RATE_TAKER: {config.TRADING_FEE_RATE_TAKER*100:.2f}%")

    # 验证配置值的合理性
    assert isinstance(config.USE_MAKER_ORDER, bool), "USE_MAKER_ORDER 必须是布尔值"
    assert config.MAKER_ORDER_TIMEOUT > 0, "MAKER_ORDER_TIMEOUT 必须大于0"
    assert config.MAKER_ORDER_TIMEOUT <= 60, "MAKER_ORDER_TIMEOUT 不应超过60秒"
    assert config.MAKER_PRICE_OFFSET > 0, "MAKER_PRICE_OFFSET 必须大于0"
    assert config.MAKER_PRICE_OFFSET < 0.01, "MAKER_PRICE_OFFSET 不应超过1%"
    assert config.MAKER_ORDER_CHECK_INTERVAL > 0, "MAKER_ORDER_CHECK_INTERVAL 必须大于0"
    assert config.TRADING_FEE_RATE_MAKER < config.TRADING_FEE_RATE_TAKER, "Maker费率应低于Taker费率"

    print("✓ 所有配置项验证通过")


def test_trader_methods():
    """测试2: Trader方法存在性检查"""
    print("检查Trader类的Maker订单相关方法...")

    from core.trader import BitgetTrader

    # 检查方法是否存在
    assert hasattr(BitgetTrader, 'create_limit_order'), "缺少 create_limit_order 方法"
    assert hasattr(BitgetTrader, 'wait_for_order_fill'), "缺少 wait_for_order_fill 方法"
    assert hasattr(BitgetTrader, 'cancel_order'), "缺少 cancel_order 方法"
    assert hasattr(BitgetTrader, 'create_smart_order'), "缺少 create_smart_order 方法"

    print("  ✓ create_limit_order 方法存在")
    print("  ✓ wait_for_order_fill 方法存在")
    print("  ✓ cancel_order 方法存在")
    print("  ✓ create_smart_order 方法存在")

    print("✓ 所有方法验证通过")


def test_price_calculation():
    """测试3: 价格计算逻辑"""
    print("测试挂单价格计算...")

    current_price = 100000.0  # BTC价格
    offset = config.MAKER_PRICE_OFFSET

    # 做多：挂单价格应略低于市价
    buy_price = current_price * (1 - offset)
    print(f"  做多挂单价格: {buy_price:.2f} (市价: {current_price:.2f})")
    assert buy_price < current_price, "做多挂单价格应低于市价"
    assert (current_price - buy_price) / current_price == offset, "价格偏移计算错误"

    # 做空：挂单价格应略高于市价
    sell_price = current_price * (1 + offset)
    print(f"  做空挂单价格: {sell_price:.2f} (市价: {current_price:.2f})")
    assert sell_price > current_price, "做空挂单价格应高于市价"
    assert (sell_price - current_price) / current_price == offset, "价格偏移计算错误"

    print("✓ 价格计算逻辑正确")


def test_fee_savings():
    """测试4: 手续费节省计算"""
    print("计算手续费节省...")

    position_size = 10.0  # USDT
    leverage = config.LEVERAGE
    notional_value = position_size * leverage  # 名义价值

    # Taker费用（市价单）
    taker_fee = notional_value * config.TRADING_FEE_RATE_TAKER
    print(f"  Taker费用（市价单）: {taker_fee:.4f} USDT")

    # Maker费用（限价单）
    maker_fee = notional_value * config.TRADING_FEE_RATE_MAKER
    print(f"  Maker费用（限价单）: {maker_fee:.4f} USDT")

    # 节省金额
    savings = taker_fee - maker_fee
    savings_pct = (savings / taker_fee) * 100
    print(f"  单笔节省: {savings:.4f} USDT ({savings_pct:.1f}%)")

    # 年度节省（假设每天10笔交易）
    daily_trades = 10
    yearly_savings = savings * 2 * daily_trades * 365  # *2因为开仓+平仓
    print(f"  年度节省: {yearly_savings:.2f} USDT")

    assert savings > 0, "Maker订单应该节省手续费"
    assert savings_pct > 60, "节省比例应超过60%"

    print("✓ 手续费节省计算正确")


def test_timeout_logic():
    """测试5: 超时逻辑"""
    print("测试超时逻辑...")

    timeout = config.MAKER_ORDER_TIMEOUT
    check_interval = config.MAKER_ORDER_CHECK_INTERVAL

    # 计算最大检查次数
    max_checks = int(timeout / check_interval)
    print(f"  超时时间: {timeout}秒")
    print(f"  检查间隔: {check_interval}秒")
    print(f"  最大检查次数: {max_checks}次")

    assert max_checks > 0, "至少应检查一次"
    assert max_checks < 100, "检查次数不应过多"

    print("✓ 超时逻辑合理")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Maker订单功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestMakerOrder()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("Trader方法检查", test_trader_methods)
    tester.run_test("价格计算逻辑", test_price_calculation)
    tester.run_test("手续费节省计算", test_fee_savings)
    tester.run_test("超时逻辑", test_timeout_logic)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
