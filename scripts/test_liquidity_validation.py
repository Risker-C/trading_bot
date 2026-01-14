#!/usr/bin/env python3
"""
流动性验证系统测试脚本

测试内容：
1. 配置验证
2. 验证器初始化
3. 简化模式验证（基于ticker）
4. 价差检查
5. 流动性不足场景
6. 流动性充足场景
7. 平仓订单跳过验证
8. 禁用验证场景
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
from config.settings import settings as config
from utils.logger_utils import get_logger
from risk.liquidity_validator import get_liquidity_validator, LiquidityValidator

logger = get_logger("test_liquidity_validation")


class TestLiquidityValidation:
    """流动性验证测试类"""

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
    print("检查流动性验证配置...")

    # 检查配置项是否存在
    assert hasattr(config, 'LIQUIDITY_VALIDATION_ENABLED'), "缺少 LIQUIDITY_VALIDATION_ENABLED 配置"
    assert hasattr(config, 'MIN_ORDERBOOK_DEPTH_MULTIPLIER'), "缺少 MIN_ORDERBOOK_DEPTH_MULTIPLIER 配置"
    assert hasattr(config, 'MIN_ORDERBOOK_DEPTH_USDT'), "缺少 MIN_ORDERBOOK_DEPTH_USDT 配置"
    assert hasattr(config, 'ORDERBOOK_DATA_FRESHNESS_SECONDS'), "缺少 ORDERBOOK_DATA_FRESHNESS_SECONDS 配置"
    assert hasattr(config, 'LIQUIDITY_INSUFFICIENT_ACTION'), "缺少 LIQUIDITY_INSUFFICIENT_ACTION 配置"

    # 检查配置值的合理性
    assert isinstance(config.LIQUIDITY_VALIDATION_ENABLED, bool), "LIQUIDITY_VALIDATION_ENABLED 必须是布尔值"
    assert config.MIN_ORDERBOOK_DEPTH_MULTIPLIER > 0, "MIN_ORDERBOOK_DEPTH_MULTIPLIER 必须大于0"
    assert config.MIN_ORDERBOOK_DEPTH_USDT > 0, "MIN_ORDERBOOK_DEPTH_USDT 必须大于0"
    assert config.ORDERBOOK_DATA_FRESHNESS_SECONDS > 0, "ORDERBOOK_DATA_FRESHNESS_SECONDS 必须大于0"
    assert config.LIQUIDITY_INSUFFICIENT_ACTION in ['reject', 'reduce', 'ignore'], \
        "LIQUIDITY_INSUFFICIENT_ACTION 必须是 'reject', 'reduce' 或 'ignore'"

    print(f"  LIQUIDITY_VALIDATION_ENABLED = {config.LIQUIDITY_VALIDATION_ENABLED}")
    print(f"  MIN_ORDERBOOK_DEPTH_MULTIPLIER = {config.MIN_ORDERBOOK_DEPTH_MULTIPLIER}")
    print(f"  MIN_ORDERBOOK_DEPTH_USDT = {config.MIN_ORDERBOOK_DEPTH_USDT}")
    print(f"  ORDERBOOK_DATA_FRESHNESS_SECONDS = {config.ORDERBOOK_DATA_FRESHNESS_SECONDS}")
    print(f"  LIQUIDITY_INSUFFICIENT_ACTION = {config.LIQUIDITY_INSUFFICIENT_ACTION}")


def test_validator_initialization():
    """测试2: 验证器初始化"""
    print("测试验证器初始化...")

    # 获取验证器实例
    validator = get_liquidity_validator()
    assert validator is not None, "验证器初始化失败"
    assert isinstance(validator, LiquidityValidator), "验证器类型错误"

    # 检查单例模式
    validator2 = get_liquidity_validator()
    assert validator is validator2, "单例模式失败，返回了不同的实例"

    # 检查验证器属性
    assert hasattr(validator, 'enabled'), "验证器缺少 enabled 属性"
    assert hasattr(validator, 'depth_multiplier'), "验证器缺少 depth_multiplier 属性"
    assert hasattr(validator, 'min_depth_usdt'), "验证器缺少 min_depth_usdt 属性"

    print(f"  验证器已启用: {validator.enabled}")
    print(f"  深度倍数: {validator.depth_multiplier}")
    print(f"  最小深度: {validator.min_depth_usdt} USDT")


def test_ticker_validation_good_liquidity():
    """测试3: Ticker验证 - 流动性充足"""
    print("测试流动性充足场景...")

    validator = get_liquidity_validator()

    # 模拟良好的ticker数据（价差小）
    ticker = {
        'bid': 87400.0,
        'ask': 87410.0,  # 价差 = 10 / 87400 = 0.011% < 1.0%
        'last': 87405.0
    }

    order_amount = 0.001  # 0.001 BTC
    order_price = 87405.0
    is_buy = True

    passed, reason, details = validator.validate_liquidity(
        ticker=ticker,
        order_amount=order_amount,
        order_price=order_price,
        is_buy=is_buy
    )

    assert passed == True, f"流动性充足但验证失败: {reason}"
    assert 'spread_pct' in details, "缺少价差信息"
    print(f"  验证通过: {reason}")
    print(f"  价差: {details['spread_pct']:.4f}%")


def test_ticker_validation_high_spread():
    """测试4: Ticker验证 - 价差过大"""
    print("测试价差过大场景...")

    validator = get_liquidity_validator()

    # 模拟价差过大的ticker数据
    ticker = {
        'bid': 87000.0,
        'ask': 88000.0,  # 价差 = 1000 / 87000 = 1.15% > 1.0%
        'last': 87500.0
    }

    order_amount = 0.001
    order_price = 87500.0
    is_buy = True

    passed, reason, details = validator.validate_liquidity(
        ticker=ticker,
        order_amount=order_amount,
        order_price=order_price,
        is_buy=is_buy
    )

    assert passed == False, "价差过大但验证通过"
    assert "价差过大" in reason, f"错误原因不正确: {reason}"
    print(f"  验证失败（预期）: {reason}")
    print(f"  价差: {details.get('spread_pct', 0):.4f}%")


def test_validation_disabled():
    """测试5: 禁用验证"""
    print("测试禁用验证场景...")

    # 临时禁用验证
    original_enabled = config.LIQUIDITY_VALIDATION_ENABLED
    config.LIQUIDITY_VALIDATION_ENABLED = False

    validator = LiquidityValidator()  # 创建新实例以应用新配置

    # 即使ticker数据很差，也应该通过
    ticker = {
        'bid': 80000.0,
        'ask': 90000.0,  # 价差巨大
        'last': 85000.0
    }

    passed, reason, details = validator.validate_liquidity(
        ticker=ticker,
        order_amount=0.001,
        order_price=85000.0,
        is_buy=True
    )

    # 恢复配置
    config.LIQUIDITY_VALIDATION_ENABLED = original_enabled

    assert passed == True, "禁用验证后仍然拒绝订单"
    assert "未启用" in reason, f"原因不正确: {reason}"
    print(f"  验证通过（禁用状态）: {reason}")


def run_tests():
    """运行所有测试并返回结果"""
    print("\n" + "="*60)
    print("流动性验证系统测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestLiquidityValidation()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("验证器初始化", test_validator_initialization)
    tester.run_test("Ticker验证 - 流动性充足", test_ticker_validation_good_liquidity)
    tester.run_test("Ticker验证 - 价差过大", test_ticker_validation_high_spread)
    tester.run_test("禁用验证", test_validation_disabled)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return success


def main():
    """主测试函数"""
    success = run_tests()
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

