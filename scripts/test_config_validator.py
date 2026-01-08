#!/usr/bin/env python3
"""
配置验证器测试脚本

测试内容：
1. 配置验证模块导入
2. RiskConfig 验证
3. ExchangeConfig 验证
4. StrategyConfig 验证
5. validate_config 函数
6. 错误配置检测
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from config_validator import RiskConfig, ExchangeConfig, StrategyConfig, validate_config
from logger_utils import get_logger

logger = get_logger("test_config_validator")


class TestConfigValidator:
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


def test_module_import():
    """测试1: 模块导入"""
    from config_validator import RiskConfig, ExchangeConfig, StrategyConfig, validate_config
    print("✓ 所有模块导入成功")


def test_risk_config_valid():
    """测试2: RiskConfig 有效配置"""
    risk_config = RiskConfig(
        stop_loss_percent=0.045,
        take_profit_percent=0.03,
        trailing_stop_percent=0.03,
        leverage=10,
        position_size_percent=0.03,
    )
    assert risk_config.stop_loss_percent == 0.045
    assert risk_config.leverage == 10
    print(f"✓ RiskConfig 创建成功: 止损={risk_config.stop_loss_percent}, 杠杆={risk_config.leverage}")


def test_risk_config_invalid_leverage():
    """测试3: RiskConfig 无效杠杆"""
    try:
        risk_config = RiskConfig(
            stop_loss_percent=0.045,
            take_profit_percent=0.03,
            trailing_stop_percent=0.03,
            leverage=200,  # 超过最大值125
            position_size_percent=0.03,
        )
        raise AssertionError("应该抛出验证错误")
    except Exception as e:
        print(f"✓ 正确捕获无效杠杆错误: {type(e).__name__}")


def test_strategy_config_valid():
    """测试4: StrategyConfig 有效配置"""
    strategy_config = StrategyConfig(
        enable_strategies=["bollinger_trend", "macd_cross"],
        min_signal_strength=0.6,
        min_strategy_agreement=0.6,
    )
    assert len(strategy_config.enable_strategies) == 2
    print(f"✓ StrategyConfig 创建成功: 策略数={len(strategy_config.enable_strategies)}")


def test_strategy_config_empty_list():
    """测试5: StrategyConfig 空策略列表"""
    try:
        strategy_config = StrategyConfig(
            enable_strategies=[],  # 空列表
            min_signal_strength=0.6,
            min_strategy_agreement=0.6,
        )
        raise AssertionError("应该抛出验证错误")
    except Exception as e:
        print(f"✓ 正确捕获空策略列表错误: {type(e).__name__}")


def test_validate_config_function():
    """测试6: validate_config 函数"""
    result = validate_config(config)
    assert result == True
    print("✓ validate_config 函数执行成功")


def test_config_values():
    """测试7: 配置值验证"""
    assert hasattr(config, 'STOP_LOSS_PERCENT')
    assert hasattr(config, 'LEVERAGE')
    assert hasattr(config, 'ENABLE_STRATEGIES')
    print(f"✓ 配置值存在: 止损={config.STOP_LOSS_PERCENT}, 杠杆={config.LEVERAGE}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("配置验证器测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestConfigValidator()

    # 运行所有测试
    tester.run_test("模块导入", test_module_import)
    tester.run_test("RiskConfig 有效配置", test_risk_config_valid)
    tester.run_test("RiskConfig 无效杠杆", test_risk_config_invalid_leverage)
    tester.run_test("StrategyConfig 有效配置", test_strategy_config_valid)
    tester.run_test("StrategyConfig 空策略列表", test_strategy_config_empty_list)
    tester.run_test("validate_config 函数", test_validate_config_function)
    tester.run_test("配置值验证", test_config_values)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
