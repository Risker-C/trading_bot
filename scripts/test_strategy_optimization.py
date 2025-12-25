#!/usr/bin/env python3
"""
策略优化功能测试脚本

测试内容：
1. 配置验证测试
2. 策略筛选测试
3. reason字段记录测试
4. 策略级差异化止损测试
"""

import sys
import os
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from logger_utils import get_logger
from risk_manager import RiskManager
from strategies import TradeSignal, Signal

logger = get_logger("test_strategy_optimization")


class TestStrategyOptimization:
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
    print("检查策略优化相关配置...")

    # 检查策略列表
    assert hasattr(config, 'ENABLE_STRATEGIES'), "缺少 ENABLE_STRATEGIES 配置"
    assert isinstance(config.ENABLE_STRATEGIES, list), "ENABLE_STRATEGIES 必须是列表"
    assert len(config.ENABLE_STRATEGIES) > 0, "ENABLE_STRATEGIES 不能为空"

    print(f"✓ 启用的策略: {config.ENABLE_STRATEGIES}")

    # 检查是否禁用了rsi_divergence
    assert 'rsi_divergence' not in config.ENABLE_STRATEGIES, \
        "rsi_divergence 应该被禁用（表现最差）"
    print("✓ rsi_divergence 已禁用")

    # 检查是否启用了multi_timeframe和adx_trend
    assert 'multi_timeframe' in config.ENABLE_STRATEGIES, \
        "multi_timeframe 应该启用（表现最好）"
    assert 'adx_trend' in config.ENABLE_STRATEGIES, \
        "adx_trend 应该启用（表现中等）"
    print("✓ multi_timeframe 和 adx_trend 已启用")

    # 检查差异化止损配置
    assert hasattr(config, 'USE_STRATEGY_SPECIFIC_STOPS'), \
        "缺少 USE_STRATEGY_SPECIFIC_STOPS 配置"
    assert config.USE_STRATEGY_SPECIFIC_STOPS == True, \
        "USE_STRATEGY_SPECIFIC_STOPS 应该为 True"
    print("✓ 策略级差异化止损已启用")

    # 检查策略配置字典
    assert hasattr(config, 'STRATEGY_STOP_CONFIGS'), \
        "缺少 STRATEGY_STOP_CONFIGS 配置"
    assert isinstance(config.STRATEGY_STOP_CONFIGS, dict), \
        "STRATEGY_STOP_CONFIGS 必须是字典"

    # 检查multi_timeframe配置
    assert 'multi_timeframe' in config.STRATEGY_STOP_CONFIGS, \
        "缺少 multi_timeframe 的差异化配置"
    mt_config = config.STRATEGY_STOP_CONFIGS['multi_timeframe']
    assert mt_config['stop_loss_pct'] == 0.05, \
        "multi_timeframe 止损应为 5%"
    assert mt_config['atr_multiplier'] == 4.5, \
        "multi_timeframe ATR倍数应为 4.5"
    print("✓ multi_timeframe 差异化配置正确")

    # 检查adx_trend配置
    assert 'adx_trend' in config.STRATEGY_STOP_CONFIGS, \
        "缺少 adx_trend 的差异化配置"
    adx_config = config.STRATEGY_STOP_CONFIGS['adx_trend']
    assert adx_config['stop_loss_pct'] == 0.045, \
        "adx_trend 止损应为 4.5%"
    assert adx_config['atr_multiplier'] == 4.0, \
        "adx_trend ATR倍数应为 4.0"
    print("✓ adx_trend 差异化配置正确")

    print("\n所有配置验证通过！")


def test_strategy_specific_stop_loss():
    """测试2: 策略级差异化止损"""
    print("测试策略级差异化止损计算...")

    # 创建风控管理器
    risk_manager = RiskManager()

    # 测试数据
    entry_price = 100.0
    side = 'long'

    # 创建模拟K线数据
    df = pd.DataFrame({
        'high': [101, 102, 103, 104, 105],
        'low': [99, 98, 97, 96, 95],
        'close': [100, 101, 102, 103, 104]
    })

    # 测试multi_timeframe策略的止损
    print("\n测试 multi_timeframe 策略...")
    stop_loss_mt = risk_manager.calculate_stop_loss(
        entry_price, side, df, strategy='multi_timeframe'
    )
    print(f"  开仓价: {entry_price}")
    print(f"  止损价: {stop_loss_mt:.2f}")
    print(f"  止损幅度: {(entry_price - stop_loss_mt) / entry_price * 100:.2f}%")

    # 验证止损价格合理性
    assert stop_loss_mt < entry_price, "做多止损价应低于开仓价"
    assert stop_loss_mt > 0, "止损价应大于0"

    # 测试adx_trend策略的止损
    print("\n测试 adx_trend 策略...")
    stop_loss_adx = risk_manager.calculate_stop_loss(
        entry_price, side, df, strategy='adx_trend'
    )
    print(f"  开仓价: {entry_price}")
    print(f"  止损价: {stop_loss_adx:.2f}")
    print(f"  止损幅度: {(entry_price - stop_loss_adx) / entry_price * 100:.2f}%")

    # 验证止损价格合理性
    assert stop_loss_adx < entry_price, "做多止损价应低于开仓价"
    assert stop_loss_adx > 0, "止损价应大于0"

    # 验证multi_timeframe的止损更宽松
    assert stop_loss_mt < stop_loss_adx, \
        "multi_timeframe 的止损应该更宽松（止损价更低）"
    print(f"\n✓ multi_timeframe 止损更宽松: {stop_loss_mt:.2f} < {stop_loss_adx:.2f}")

    # 测试未配置策略使用默认止损
    print("\n测试未配置策略使用默认止损...")
    stop_loss_default = risk_manager.calculate_stop_loss(
        entry_price, side, df, strategy='unknown_strategy'
    )
    print(f"  开仓价: {entry_price}")
    print(f"  止损价: {stop_loss_default:.2f}")
    print(f"  止损幅度: {(entry_price - stop_loss_default) / entry_price * 100:.2f}%")

    assert stop_loss_default < entry_price, "做多止损价应低于开仓价"
    print("✓ 未配置策略正确使用默认止损")

    print("\n策略级差异化止损测试通过！")


def test_strategy_specific_take_profit():
    """测试3: 策略级差异化止盈"""
    print("测试策略级差异化止盈计算...")

    # 创建风控管理器
    risk_manager = RiskManager()

    # 测试数据
    entry_price = 100.0
    side = 'long'

    # 测试multi_timeframe策略的止盈
    print("\n测试 multi_timeframe 策略...")
    take_profit_mt = risk_manager.calculate_take_profit(
        entry_price, side, strategy='multi_timeframe'
    )
    print(f"  开仓价: {entry_price}")
    print(f"  止盈价: {take_profit_mt:.2f}")
    print(f"  止盈幅度: {(take_profit_mt - entry_price) / entry_price * 100:.2f}%")

    # 验证止盈价格合理性
    assert take_profit_mt > entry_price, "做多止盈价应高于开仓价"

    # 测试adx_trend策略的止盈
    print("\n测试 adx_trend 策略...")
    take_profit_adx = risk_manager.calculate_take_profit(
        entry_price, side, strategy='adx_trend'
    )
    print(f"  开仓价: {entry_price}")
    print(f"  止盈价: {take_profit_adx:.2f}")
    print(f"  止盈幅度: {(take_profit_adx - entry_price) / entry_price * 100:.2f}%")

    # 验证止盈价格合理性
    assert take_profit_adx > entry_price, "做多止盈价应高于开仓价"

    # 验证multi_timeframe的止盈更高
    assert take_profit_mt > take_profit_adx, \
        "multi_timeframe 的止盈应该更高"
    print(f"\n✓ multi_timeframe 止盈更高: {take_profit_mt:.2f} > {take_profit_adx:.2f}")

    print("\n策略级差异化止盈测试通过！")


def test_trade_signal_structure():
    """测试4: TradeSignal结构验证"""
    print("测试 TradeSignal 数据结构...")

    # 创建测试信号
    signal = TradeSignal(
        signal=Signal.LONG,
        strategy="multi_timeframe",
        reason="多时间周期看多",
        strength=0.75,
        confidence=1.0,
        indicators={'rsi': 45, 'macd': 0.5}
    )

    # 验证字段
    assert signal.signal == Signal.LONG, "信号类型错误"
    assert signal.strategy == "multi_timeframe", "策略名称错误"
    assert signal.reason == "多时间周期看多", "原因字段错误"
    assert signal.strength == 0.75, "强度字段错误"
    assert signal.confidence == 1.0, "置信度字段错误"

    print(f"✓ 信号类型: {signal.signal}")
    print(f"✓ 策略名称: {signal.strategy}")
    print(f"✓ 开单原因: {signal.reason}")
    print(f"✓ 信号强度: {signal.strength}")
    print(f"✓ 置信度: {signal.confidence}")

    print("\nTradeSignal 结构验证通过！")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("策略优化功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestStrategyOptimization()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("策略级差异化止损", test_strategy_specific_stop_loss)
    tester.run_test("策略级差异化止盈", test_strategy_specific_take_profit)
    tester.run_test("TradeSignal结构验证", test_trade_signal_structure)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
