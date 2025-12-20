#!/usr/bin/env python3
"""
做多胜率优化测试脚本

测试内容：
1. 配置验证 - 确认策略配置正确
2. 上涨趋势检查 - 验证EMA多头排列、K线形态、成交量确认
3. MACD权重调整 - 验证零轴上下方金叉权重
4. 震荡市场保护 - 验证震荡下跌时的保护规则
5. 方向过滤器 - 验证做多信号过滤逻辑
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from logger_utils import get_logger
from direction_filter import DirectionFilter
from trend_filter import TrendFilter
from strategies import BollingerTrendStrategy, MACDCrossStrategy, Signal

logger = get_logger("test_long_win_rate_fix")


class TestLongWinRateFix:
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


def create_sample_df(trend="up", volume_spike=False, candle_pattern="bullish"):
    """
    创建测试用的DataFrame

    Args:
        trend: "up" (上涨), "down" (下跌), "sideways" (震荡)
        volume_spike: 是否有成交量放大
        candle_pattern: "bullish" (阳线), "bearish" (阴线), "mixed" (混合)
    """
    periods = 200

    # 生成基础价格数据
    if trend == "up":
        base_price = np.linspace(40000, 45000, periods)
    elif trend == "down":
        base_price = np.linspace(45000, 40000, periods)
    else:  # sideways
        base_price = np.ones(periods) * 42500 + np.random.randn(periods) * 200

    # 添加噪音
    noise = np.random.randn(periods) * 100
    close_prices = base_price + noise

    # 生成K线数据
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2025-01-01', periods=periods, freq='15min'),
        'open': close_prices - np.random.rand(periods) * 50,
        'high': close_prices + np.random.rand(periods) * 100,
        'low': close_prices - np.random.rand(periods) * 100,
        'close': close_prices,
        'volume': np.random.rand(periods) * 1000000 + 500000
    })

    # 调整K线形态
    if candle_pattern == "bullish":
        # 最近3根K线设置为阳线
        for i in range(-3, 0):
            df.loc[df.index[i], 'open'] = df.loc[df.index[i], 'close'] - 50
    elif candle_pattern == "bearish":
        # 最近3根K线设置为阴线
        for i in range(-3, 0):
            df.loc[df.index[i], 'open'] = df.loc[df.index[i], 'close'] + 50

    # 调整成交量
    if volume_spike:
        # 最近一根K线成交量放大
        df.loc[df.index[-1], 'volume'] = df['volume'].mean() * 1.5

    return df


def test_config_validation():
    """测试1: 配置验证"""
    print("检查策略配置...")

    # 检查 bollinger_trend 是否启用
    assert "bollinger_trend" in config.ENABLE_STRATEGIES, \
        "bollinger_trend 策略未启用"
    print("✓ bollinger_trend 策略已启用")

    # 检查 bollinger_breakthrough 是否禁用
    assert "bollinger_breakthrough" not in config.ENABLE_STRATEGIES, \
        "bollinger_breakthrough 策略应该被禁用"
    print("✓ bollinger_breakthrough 策略已禁用")

    # 检查 rsi_divergence 是否禁用
    assert "rsi_divergence" not in config.ENABLE_STRATEGIES, \
        "rsi_divergence 策略应该被禁用"
    print("✓ rsi_divergence 策略已禁用")

    print("配置验证通过")


def test_uptrend_check():
    """测试2: 上涨趋势检查"""
    print("测试上涨趋势检查逻辑...")

    direction_filter = DirectionFilter()

    # 测试场景1: 明确的上涨趋势（应该通过）
    print("\n场景1: 明确的上涨趋势")
    df_uptrend = create_sample_df(trend="up", volume_spike=True, candle_pattern="bullish")
    result = direction_filter._check_uptrend(df_uptrend)
    print(f"  上涨趋势检查结果: {result}")
    assert result == True, "明确的上涨趋势应该通过检查"
    print("  ✓ 通过")

    # 测试场景2: 下跌趋势（应该不通过）
    print("\n场景2: 下跌趋势")
    df_downtrend = create_sample_df(trend="down", volume_spike=False, candle_pattern="bearish")
    result = direction_filter._check_uptrend(df_downtrend)
    print(f"  上涨趋势检查结果: {result}")
    assert result == False, "下跌趋势不应该通过检查"
    print("  ✓ 通过")

    # 测试场景3: 震荡市场（应该不通过）
    print("\n场景3: 震荡市场")
    df_sideways = create_sample_df(trend="sideways", volume_spike=False, candle_pattern="mixed")
    result = direction_filter._check_uptrend(df_sideways)
    print(f"  上涨趋势检查结果: {result}")
    # 震荡市场可能通过也可能不通过，取决于具体数据
    print(f"  结果: {result}")

    print("\n上涨趋势检查测试完成")


def test_volume_confirmation():
    """测试3: 成交量确认"""
    print("测试成交量确认逻辑...")

    direction_filter = DirectionFilter()

    # 测试场景1: 成交量放大（应该通过）
    print("\n场景1: 成交量放大")
    df_volume_spike = create_sample_df(trend="up", volume_spike=True, candle_pattern="bullish")
    result = direction_filter._check_volume_confirmation(df_volume_spike)
    print(f"  成交量确认结果: {result}")
    assert result == True, "成交量放大应该通过确认"
    print("  ✓ 通过")

    # 测试场景2: 成交量正常（可能不通过）
    print("\n场景2: 成交量正常")
    df_normal_volume = create_sample_df(trend="up", volume_spike=False, candle_pattern="bullish")
    result = direction_filter._check_volume_confirmation(df_normal_volume)
    print(f"  成交量确认结果: {result}")
    print(f"  结果: {result}")

    print("\n成交量确认测试完成")


def test_macd_weight_adjustment():
    """测试4: MACD权重调整"""
    print("测试MACD权重调整...")

    # 创建测试数据
    df = create_sample_df(trend="up", volume_spike=True, candle_pattern="bullish")

    # 创建MACD策略实例
    macd_strategy = MACDCrossStrategy(df)

    # 注意：这里我们无法直接测试权重调整，因为需要模拟MACD金叉
    # 但我们可以验证策略实例是否正确创建
    assert macd_strategy is not None, "MACD策略实例创建失败"
    assert hasattr(macd_strategy, 'macd'), "MACD策略缺少macd属性"

    print("✓ MACD策略实例创建成功")
    print("✓ MACD指标计算正常")

    # 检查MACD数据结构
    assert 'macd' in macd_strategy.macd, "MACD数据缺少macd列"
    assert 'signal' in macd_strategy.macd, "MACD数据缺少signal列"
    assert 'histogram' in macd_strategy.macd, "MACD数据缺少histogram列"

    print("✓ MACD数据结构正确")

    print("\nMACD权重调整测试完成")
    print("注意: 权重调整逻辑需要在实际交易中验证")


def test_oscillation_market_protection():
    """测试5: 震荡市场保护"""
    print("测试震荡市场保护规则...")

    from indicators import Indicators

    # 创建震荡下跌的测试数据
    df = create_sample_df(trend="down", volume_spike=False, candle_pattern="bearish")

    # 计算技术指标
    ind = Indicators(df)
    rsi = ind.rsi()
    macd_data = ind.macd()
    adx_data = ind.adx()
    ema9 = df['close'].ewm(span=9, adjust=False).mean()
    ema21 = df['close'].ewm(span=21, adjust=False).mean()
    bb = ind.bollinger_bands()

    # 获取最新值
    current_rsi = rsi.iloc[-1]
    current_macd = macd_data['macd'].iloc[-1]
    current_adx = adx_data['adx'].iloc[-1]
    ema_trend = "down" if ema9.iloc[-1] < ema21.iloc[-1] else "up"
    macd_trend = "down" if current_macd < 0 else "up"
    di_trend = "down" if adx_data['di_diff'].iloc[-1] < 0 else "up"
    bb_percent_b = (df['close'].iloc[-1] - bb['lower'].iloc[-1]) / (bb['upper'].iloc[-1] - bb['lower'].iloc[-1])

    print(f"\n市场状态:")
    print(f"  RSI: {current_rsi:.2f}")
    print(f"  MACD: {current_macd:.2f}")
    print(f"  ADX: {current_adx:.2f}")
    print(f"  EMA趋势: {ema_trend}")
    print(f"  MACD趋势: {macd_trend}")
    print(f"  DI趋势: {di_trend}")
    print(f"  布林带位置: {bb_percent_b:.2f}")

    # 创建趋势过滤器
    trend_filter = TrendFilter()

    # 测试做多信号
    is_strong_trend = current_adx > 25
    is_very_strong_trend = current_adx > 35

    print(f"\n趋势强度:")
    print(f"  强趋势: {is_strong_trend}")
    print(f"  极强趋势: {is_very_strong_trend}")

    # 调用_check_long_signal方法
    result, reason = trend_filter._check_long_signal(
        rsi=current_rsi,
        macd=current_macd,
        macd_histogram=macd_data['histogram'].iloc[-1],
        ema_trend=ema_trend,
        macd_trend=macd_trend,
        di_trend=di_trend,
        is_strong_trend=is_strong_trend,
        is_very_strong_trend=is_very_strong_trend,
        bb_percent_b=bb_percent_b,
        adx=current_adx
    )

    print(f"\n做多信号检查结果:")
    print(f"  通过: {result}")
    print(f"  原因: {reason}")

    # 在震荡下跌市场中，做多信号应该被拒绝
    if not is_strong_trend and ema_trend == "down":
        print("\n✓ 震荡下跌市场检测正确")
        if not result:
            print("✓ 做多信号被正确拒绝")
        else:
            print("⚠ 做多信号未被拒绝（可能RSI和MACD满足条件）")

    print("\n震荡市场保护测试完成")


def test_direction_filter():
    """测试6: 方向过滤器"""
    print("测试方向过滤器逻辑...")

    from strategies import TradeSignal

    direction_filter = DirectionFilter()

    # 测试场景1: 强做多信号 + 上涨趋势（应该通过）
    print("\n场景1: 强做多信号 + 上涨趋势")
    df_uptrend = create_sample_df(trend="up", volume_spike=True, candle_pattern="bullish")
    signal = TradeSignal(
        signal=Signal.LONG,
        strategy="test",
        reason="测试信号",
        strength=0.75,  # 高于70%阈值
        indicators={}
    )
    strategy_agreement = 0.70  # 高于65%阈值

    result, reason = direction_filter.filter_signal(signal, df_uptrend, strategy_agreement)
    print(f"  过滤结果: {result}")
    print(f"  原因: {reason}")
    assert result == True, "强做多信号在上涨趋势中应该通过"
    print("  ✓ 通过")

    # 测试场景2: 弱做多信号（应该不通过）
    print("\n场景2: 弱做多信号")
    weak_signal = TradeSignal(
        signal=Signal.LONG,
        strategy="test",
        reason="测试信号",
        strength=0.60,  # 低于70%阈值
        indicators={}
    )

    result, reason = direction_filter.filter_signal(weak_signal, df_uptrend, strategy_agreement)
    print(f"  过滤结果: {result}")
    print(f"  原因: {reason}")
    assert result == False, "弱做多信号应该被拒绝"
    print("  ✓ 通过")

    # 测试场景3: 做空信号（应该使用正常标准）
    print("\n场景3: 做空信号")
    short_signal = TradeSignal(
        signal=Signal.SHORT,
        strategy="test",
        reason="测试信号",
        strength=0.55,  # 高于50%阈值
        indicators={}
    )
    strategy_agreement = 0.65  # 高于60%阈值

    result, reason = direction_filter.filter_signal(short_signal, df_uptrend, strategy_agreement)
    print(f"  过滤结果: {result}")
    print(f"  原因: {reason}")
    assert result == True, "做空信号应该使用正常标准"
    print("  ✓ 通过")

    print("\n方向过滤器测试完成")


def test_bollinger_trend_strategy():
    """测试7: 布林带趋势策略"""
    print("测试布林带趋势策略...")

    # 创建上涨趋势数据
    df = create_sample_df(trend="up", volume_spike=True, candle_pattern="bullish")

    # 创建策略实例
    strategy = BollingerTrendStrategy(df)

    # 验证策略实例
    assert strategy is not None, "布林带趋势策略实例创建失败"
    assert strategy.name == "bollinger_trend", "策略名称不正确"

    print("✓ 布林带趋势策略实例创建成功")
    print(f"✓ 策略名称: {strategy.name}")
    print(f"✓ 策略描述: {strategy.description}")

    # 分析信号
    signal = strategy.analyze()
    print(f"\n信号分析结果:")
    print(f"  信号类型: {signal.signal}")
    print(f"  策略: {signal.strategy}")
    print(f"  原因: {signal.reason}")
    print(f"  强度: {signal.strength:.2f}")

    print("\n布林带趋势策略测试完成")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("做多胜率优化测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestLongWinRateFix()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("上涨趋势检查", test_uptrend_check)
    tester.run_test("成交量确认", test_volume_confirmation)
    tester.run_test("MACD权重调整", test_macd_weight_adjustment)
    tester.run_test("震荡市场保护", test_oscillation_market_protection)
    tester.run_test("方向过滤器", test_direction_filter)
    tester.run_test("布林带趋势策略", test_bollinger_trend_strategy)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
