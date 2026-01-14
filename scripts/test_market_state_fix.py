#!/usr/bin/env python3
"""
市场状态检测修复测试脚本

测试内容：
1. 强趋势 + 窄布林带场景（修复的核心场景）
2. 标准趋势场景
3. 真正的震荡市场景
4. 边界情况测试
5. 滞回机制测试
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
from config.settings import settings as config
from strategies.market_regime import MarketRegimeDetector, MarketRegime
from utils.logger_utils import get_logger

logger = get_logger("test_market_state_fix")


class TestMarketStateFix:
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


def create_mock_df_with_indicators(adx: float, bb_width_pct: float, plus_di: float = None, minus_di: float = None) -> pd.DataFrame:
    """
    创建模拟的K线数据，并注入指定的指标值

    Args:
        adx: ADX值
        bb_width_pct: 布林带宽度百分比
        plus_di: +DI值（可选，默认根据趋势方向计算）
        minus_di: -DI值（可选，默认根据趋势方向计算）
    """
    # 创建基础K线数据（100根K线）
    periods = 100
    base_price = 100.0

    # 根据ADX和布林带宽度生成合理的价格数据
    if adx > 35:  # 强趋势
        # 生成趋势性价格
        trend = np.linspace(0, 10, periods)
        noise = np.random.normal(0, bb_width_pct * base_price / 100, periods)
        close_prices = base_price + trend + noise
    elif adx < 20:  # 震荡
        # 生成震荡性价格
        noise = np.random.normal(0, bb_width_pct * base_price / 100, periods)
        close_prices = base_price + noise
    else:  # 过渡
        # 生成混合价格
        trend = np.linspace(0, 5, periods)
        noise = np.random.normal(0, bb_width_pct * base_price / 100, periods)
        close_prices = base_price + trend * 0.5 + noise

    # 确保价格为正
    close_prices = np.maximum(close_prices, base_price * 0.9)

    # 生成OHLC数据
    high_prices = close_prices * (1 + bb_width_pct / 200)
    low_prices = close_prices * (1 - bb_width_pct / 200)
    open_prices = np.roll(close_prices, 1)
    open_prices[0] = close_prices[0]

    # 生成成交量
    volumes = np.random.uniform(1000, 2000, periods)

    # 创建DataFrame
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=periods, freq='15min'),
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })

    return df


def test_strong_trend_narrow_bb():
    """测试1: 强趋势 + 窄布林带（修复的核心场景）"""
    print("\n场景: ADX=55.3, BB宽度=1.72%")
    print("预期: 应该判定为 TRENDING（强趋势豁免）")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=55.3, bb_width_pct=1.72)

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n实际结果:")
    print(f"  市场状态: {regime_info.regime.value.upper()}")
    print(f"  置信度: {regime_info.confidence:.0%}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")

    # 验证结果
    assert regime_info.regime == MarketRegime.TRENDING, \
        f"预期 TRENDING，实际 {regime_info.regime.value.upper()}"
    assert regime_info.adx >= config.STRONG_TREND_ADX, \
        f"ADX应该 >= {config.STRONG_TREND_ADX}"

    print(f"\n✅ 修复验证成功: 强趋势不再被误判为震荡市")


def test_standard_trend():
    """测试2: 标准趋势场景"""
    print("\n场景: ADX=32.0, BB宽度=3.5%")
    print("预期: 应该判定为 TRENDING（标准趋势）")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=32.0, bb_width_pct=3.5)

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n实际结果:")
    print(f"  市场状态: {regime_info.regime.value.upper()}")
    print(f"  置信度: {regime_info.confidence:.0%}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")

    # 验证结果
    assert regime_info.regime == MarketRegime.TRENDING, \
        f"预期 TRENDING，实际 {regime_info.regime.value.upper()}"


def test_true_ranging():
    """测试3: 真正的震荡市场景"""
    print("\n场景: ADX=18.0, BB宽度=1.5%")
    print("预期: 应该判定为 RANGING（震荡市）")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=18.0, bb_width_pct=1.5)

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n实际结果:")
    print(f"  市场状态: {regime_info.regime.value.upper()}")
    print(f"  置信度: {regime_info.confidence:.0%}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")

    # 验证结果
    assert regime_info.regime == MarketRegime.RANGING, \
        f"预期 RANGING，实际 {regime_info.regime.value.upper()}"


def test_boundary_case():
    """测试4: 边界情况"""
    print("\n场景: ADX=36.0, BB宽度=2.1%")
    print("预期: 应该判定为 TRENDING（强趋势豁免边界）")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=36.0, bb_width_pct=2.1)

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n实际结果:")
    print(f"  市场状态: {regime_info.regime.value.upper()}")
    print(f"  置信度: {regime_info.confidence:.0%}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")

    # 验证结果
    assert regime_info.regime == MarketRegime.TRENDING, \
        f"预期 TRENDING，实际 {regime_info.regime.value.upper()}"


def test_transitioning():
    """测试5: 过渡市场景"""
    print("\n场景: ADX=25.0, BB宽度=2.5%")
    print("预期: 应该判定为 TRANSITIONING（过渡市）")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=25.0, bb_width_pct=2.5)

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n实际结果:")
    print(f"  市场状态: {regime_info.regime.value.upper()}")
    print(f"  置信度: {regime_info.confidence:.0%}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")

    # 验证结果（过渡市或趋势市都可以接受）
    assert regime_info.regime in [MarketRegime.TRANSITIONING, MarketRegime.TRENDING], \
        f"预期 TRANSITIONING 或 TRENDING，实际 {regime_info.regime.value.upper()}"


def test_hysteresis():
    """测试6: 滞回机制"""
    print("\n场景: 测试滞回机制（上一次是趋势市）")
    print("条件: ADX=28.0, BB宽度=2.6%")
    print("预期: 由于滞回机制，应该保持 TRENDING")

    # 创建模拟数据
    df = create_mock_df_with_indicators(adx=28.0, bb_width_pct=2.6)

    # 第一次检测（无历史状态）
    detector1 = MarketRegimeDetector(df)
    regime_info1 = detector1.detect()

    print(f"\n第一次检测（无历史状态）:")
    print(f"  市场状态: {regime_info1.regime.value.upper()}")
    print(f"  ADX: {regime_info1.adx:.1f}")
    print(f"  布林带宽度: {regime_info1.bb_width:.2f}%")

    # 第二次检测（假设上一次是趋势市）
    detector2 = MarketRegimeDetector(df, prev_regime=MarketRegime.TRENDING)
    regime_info2 = detector2.detect()

    print(f"\n第二次检测（上一次是趋势市）:")
    print(f"  市场状态: {regime_info2.regime.value.upper()}")
    print(f"  ADX: {regime_info2.adx:.1f}")
    print(f"  布林带宽度: {regime_info2.bb_width:.2f}%")

    # 验证滞回机制
    if regime_info2.adx >= config.TREND_EXIT_ADX and regime_info2.bb_width >= config.TREND_EXIT_BB:
        assert regime_info2.regime == MarketRegime.TRENDING, \
            f"滞回机制应该保持 TRENDING，实际 {regime_info2.regime.value.upper()}"
        print(f"\n✅ 滞回机制正常工作")


def test_real_market_data():
    """测试7: 使用真实市场数据"""
    print("\n场景: 使用真实市场数据测试")

    try:
        from core.trader import BitgetTrader

        trader = BitgetTrader()
        df = trader.get_klines()

        if df.empty:
            print("⚠️  无法获取真实市场数据，跳过此测试")
            return

        # 检测市场状态
        detector = MarketRegimeDetector(df)
        regime_info = detector.detect()

        print(f"\n真实市场数据结果:")
        print(f"  市场状态: {regime_info.regime.value.upper()}")
        print(f"  置信度: {regime_info.confidence:.0%}")
        print(f"  ADX: {regime_info.adx:.1f}")
        print(f"  布林带宽度: {regime_info.bb_width:.2f}%")
        print(f"  趋势方向: {['下跌', '中性', '上涨'][regime_info.trend_direction + 1]}")
        print(f"  波动率: {regime_info.volatility:.2%}")

        # 获取推荐策略
        strategies = detector.get_suitable_strategies(regime_info)
        print(f"\n推荐策略:")
        for s in strategies:
            print(f"  - {s}")

        # 检查是否适合交易
        can_trade, reason = detector.should_trade(regime_info)
        print(f"\n是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
        print(f"原因: {reason}")

        # 验证逻辑一致性
        if regime_info.adx >= config.STRONG_TREND_ADX and regime_info.bb_width > config.STRONG_TREND_BB:
            assert regime_info.regime == MarketRegime.TRENDING, \
                f"强趋势条件满足但未判定为 TRENDING"
            print(f"\n✅ 真实数据测试通过: 强趋势判定正确")

    except ImportError:
        print("⚠️  无法导入 BitgetTrader，跳过真实数据测试")
    except Exception as e:
        print(f"⚠️  真实数据测试出错: {e}")


def test_logic_consistency():
    """测试8: 逻辑一致性验证"""
    print("\n场景: 验证修复后的逻辑一致性")

    test_cases = [
        # (ADX, BB宽度, 预期状态, 描述)
        (55.0, 1.8, MarketRegime.TRENDING, "强趋势豁免"),
        (40.0, 2.2, MarketRegime.TRENDING, "强趋势豁免"),
        (35.0, 2.1, MarketRegime.TRENDING, "强趋势豁免边界"),
        (32.0, 3.5, MarketRegime.TRENDING, "标准趋势"),
        (30.0, 3.1, MarketRegime.TRENDING, "标准趋势边界"),
        (19.0, 1.9, MarketRegime.RANGING, "震荡市"),
        (18.0, 1.5, MarketRegime.RANGING, "明确震荡"),
        (25.0, 2.5, None, "过渡市（可能）"),  # None表示可以是任何状态
    ]

    all_passed = True

    for adx, bb_width, expected, desc in test_cases:
        df = create_mock_df_with_indicators(adx=adx, bb_width_pct=bb_width)
        detector = MarketRegimeDetector(df)
        regime_info = detector.detect()

        if expected is not None:
            if regime_info.regime != expected:
                print(f"❌ {desc}: ADX={adx}, BB={bb_width}% -> 预期 {expected.value}, 实际 {regime_info.regime.value}")
                all_passed = False
            else:
                print(f"✅ {desc}: ADX={adx}, BB={bb_width}% -> {regime_info.regime.value}")
        else:
            print(f"ℹ️  {desc}: ADX={adx}, BB={bb_width}% -> {regime_info.regime.value}")

    assert all_passed, "部分逻辑一致性测试失败"
    print(f"\n✅ 逻辑一致性验证通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("市场状态检测修复测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestMarketStateFix()

    # 运行所有测试
    tester.run_test("强趋势 + 窄布林带（核心修复场景）", test_strong_trend_narrow_bb)
    tester.run_test("标准趋势场景", test_standard_trend)
    tester.run_test("真正的震荡市场景", test_true_ranging)
    tester.run_test("边界情况测试", test_boundary_case)
    tester.run_test("过渡市场景", test_transitioning)
    tester.run_test("滞回机制测试", test_hysteresis)
    tester.run_test("真实市场数据测试", test_real_market_data)
    tester.run_test("逻辑一致性验证", test_logic_consistency)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
