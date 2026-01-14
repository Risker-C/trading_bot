"""
测试 Claude AI 集成和趋势过滤器
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from ai.claude_analyzer import get_claude_analyzer
from strategies.trend_filter import get_trend_filter
from strategies.strategies import Signal, TradeSignal
import config


def create_test_dataframe(trend="down", length=100):
    """
    创建测试数据

    Args:
        trend: "up" (上涨), "down" (下跌), "sideways" (震荡)
        length: 数据长度
    """
    dates = pd.date_range(end=datetime.now(), periods=length, freq='15min')

    if trend == "down":
        # 下跌趋势
        close = np.linspace(100, 85, length) + np.random.randn(length) * 0.5
    elif trend == "up":
        # 上涨趋势
        close = np.linspace(85, 100, length) + np.random.randn(length) * 0.5
    else:
        # 震荡
        close = 90 + np.sin(np.linspace(0, 4*np.pi, length)) * 5 + np.random.randn(length) * 0.5

    df = pd.DataFrame({
        'timestamp': dates,
        'open': close + np.random.randn(length) * 0.2,
        'high': close + abs(np.random.randn(length)) * 0.5,
        'low': close - abs(np.random.randn(length)) * 0.5,
        'close': close,
        'volume': np.random.randint(1000, 2000, length)
    })

    return df


def test_trend_filter():
    """测试趋势过滤器"""
    print("=" * 60)
    print("测试 1: 趋势过滤器")
    print("=" * 60)

    trend_filter = get_trend_filter()

    # 测试场景 1: 强下跌趋势中的做多信号（应该被拒绝）
    print("\n场景 1: 强下跌趋势中的做多信号")
    print("-" * 60)

    df = create_test_dataframe(trend="down")
    signal = TradeSignal(Signal.LONG, "test", "测试做多信号")

    indicators = {
        'rsi': 25,
        'macd': -600,
        'macd_histogram': -50,
        'ema_short': 87,
        'ema_long': 92,
        'adx': 35,
        'plus_di': 15,
        'minus_di': 35,
        'bb_percent_b': 0.1,
    }

    passed, reason = trend_filter.check_signal(df, signal, indicators)
    print(f"信号: {signal.signal.value} ({signal.reason})")
    print(f"结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    print(f"原因: {reason}")

    # 获取趋势摘要
    summary = trend_filter.get_trend_summary(indicators)
    print(f"\n趋势摘要:")
    print(f"  综合趋势: {summary['overall_trend']}")
    print(f"  EMA趋势: {summary['ema_trend']}")
    print(f"  MACD趋势: {summary['macd_trend']}")
    print(f"  趋势强度: {summary['trend_strength']}")
    print(f"  RSI状态: {summary['rsi_status']}")

    assert not passed, "强下跌趋势中的做多信号应该被拒绝"
    print("\n✅ 测试通过: 强下跌趋势中的做多信号被正确拒绝")

    # 测试场景 2: 强上涨趋势中的做多信号（应该通过）
    print("\n" + "=" * 60)
    print("场景 2: 强上涨趋势中的做多信号")
    print("-" * 60)

    df = create_test_dataframe(trend="up")
    signal = TradeSignal(Signal.LONG, "test", "测试做多信号")

    indicators = {
        'rsi': 55,
        'macd': 300,
        'macd_histogram': 50,
        'ema_short': 92,
        'ema_long': 87,
        'adx': 30,
        'plus_di': 35,
        'minus_di': 15,
        'bb_percent_b': 0.6,
    }

    passed, reason = trend_filter.check_signal(df, signal, indicators)
    print(f"信号: {signal.signal.value} ({signal.reason})")
    print(f"结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    print(f"原因: {reason}")

    summary = trend_filter.get_trend_summary(indicators)
    print(f"\n趋势摘要:")
    print(f"  综合趋势: {summary['overall_trend']}")
    print(f"  趋势强度: {summary['trend_strength']}")
    print(f"  RSI状态: {summary['rsi_status']}")

    assert passed, "强上涨趋势中的做多信号应该通过"
    print("\n✅ 测试通过: 强上涨趋势中的做多信号被正确通过")

    # 测试场景 3: RSI 极度超卖时的做多信号（应该被拒绝）
    print("\n" + "=" * 60)
    print("场景 3: RSI 极度超卖时的做多信号")
    print("-" * 60)

    df = create_test_dataframe(trend="down")
    signal = TradeSignal(Signal.LONG, "test", "RSI超卖做多")

    indicators = {
        'rsi': 15,  # 极度超卖
        'macd': -200,
        'macd_histogram': -30,
        'ema_short': 88,
        'ema_long': 90,
        'adx': 22,
        'plus_di': 20,
        'minus_di': 25,
        'bb_percent_b': 0.05,
    }

    passed, reason = trend_filter.check_signal(df, signal, indicators)
    print(f"信号: {signal.signal.value} ({signal.reason})")
    print(f"RSI: {indicators['rsi']}")
    print(f"结果: {'✅ 通过' if passed else '❌ 拒绝'}")
    print(f"原因: {reason}")

    assert not passed, "RSI极度超卖时的做多信号应该被拒绝"
    print("\n✅ 测试通过: RSI极度超卖时的做多信号被正确拒绝")

    print("\n" + "=" * 60)
    print("✅ 趋势过滤器测试全部通过")
    print("=" * 60)


def test_claude_analyzer():
    """测试 Claude 分析器"""
    print("\n" + "=" * 60)
    print("测试 2: Claude AI 分析器")
    print("=" * 60)

    analyzer = get_claude_analyzer()

    if not analyzer.enabled:
        print("\n⚠️  Claude 分析器未启用")
        print("原因可能是:")
        print("  1. ENABLE_CLAUDE_ANALYSIS = False")
        print("  2. 未配置 CLAUDE_API_KEY")
        print("  3. anthropic 库未安装")
        print("\n跳过 Claude 分析器测试")
        return

    print(f"\n✅ Claude 分析器已启用")
    print(f"   模型: {analyzer.model}")

    # 测试场景: 强下跌趋势中的做多信号
    print("\n场景: 强下跌趋势中的做多信号")
    print("-" * 60)

    df = create_test_dataframe(trend="down", length=100)
    current_price = df['close'].iloc[-1]

    signal = TradeSignal(
        Signal.LONG,
        "bollinger_breakthrough",
        "价格连续3根K线突破布林带下轨",
        strength=0.7,
        confidence=0.6
    )

    indicators = {
        'rsi': 14.24,
        'macd': -659,
        'macd_signal': -550,
        'macd_histogram': -109,
        'ema_short': current_price - 2,
        'ema_long': current_price + 1,
        'bb_upper': current_price + 3,
        'bb_middle': current_price + 1,
        'bb_lower': current_price - 2,
        'bb_percent_b': 0.074,
        'adx': 35.2,
        'plus_di': 12.5,
        'minus_di': 38.7,
        'volume_ratio': 1.2,
        'trend_direction': -1,
        'trend_strength': 0.8,
    }

    print(f"当前价格: {current_price:.2f}")
    print(f"信号: {signal.signal.value} - {signal.reason}")
    print(f"信号强度: {signal.strength:.2f}")
    print(f"置信度: {signal.confidence:.2f}")
    print(f"\n技术指标:")
    print(f"  RSI: {indicators['rsi']:.2f} (极度超卖)")
    print(f"  MACD: {indicators['macd']:.2f} (强烈空头)")
    print(f"  EMA趋势: {'下跌' if indicators['ema_short'] < indicators['ema_long'] else '上涨'}")
    print(f"  ADX: {indicators['adx']:.2f} (强趋势)")
    print(f"  DI方向: {'看跌' if indicators['minus_di'] > indicators['plus_di'] else '看涨'}")

    print(f"\n正在调用 Claude API 进行分析...")
    print("(这可能需要几秒钟...)")

    try:
        passed, reason, details = analyzer.analyze_signal(
            df, current_price, signal, indicators
        )

        print(f"\n{'='*60}")
        print("Claude 分析结果:")
        print(f"{'='*60}")
        print(f"决策: {details.get('decision', 'N/A')}")
        print(f"置信度: {details.get('confidence', 0):.2f}")
        print(f"趋势: {details.get('trend', 'N/A')}")
        print(f"风险等级: {details.get('risk_level', 'N/A')}")
        print(f"原因: {details.get('reason', reason)}")

        if details.get('warnings'):
            print(f"\n警告:")
            for warning in details['warnings']:
                print(f"  ⚠️  {warning}")

        print(f"\n最终决策: {'✅ 执行' if passed else '❌ 拒绝'}")

        print("\n✅ Claude 分析器测试完成")

    except Exception as e:
        print(f"\n❌ Claude 分析失败: {e}")
        print("请检查:")
        print("  1. API Key 是否正确")
        print("  2. 网络连接是否正常")
        print("  3. API 配额是否充足")


def test_integration():
    """测试完整集成流程"""
    print("\n" + "=" * 60)
    print("测试 3: 完整集成流程")
    print("=" * 60)

    trend_filter = get_trend_filter()
    analyzer = get_claude_analyzer()

    # 模拟完整的信号处理流程
    print("\n模拟信号处理流程:")
    print("-" * 60)

    df = create_test_dataframe(trend="down", length=100)
    current_price = df['close'].iloc[-1]

    signal = TradeSignal(
        Signal.LONG,
        "rsi_divergence",
        "RSI超卖(25.3)且底背离",
        strength=0.8,
        confidence=0.7
    )

    indicators = {
        'rsi': 25.3,
        'macd': -450,
        'macd_histogram': -80,
        'ema_short': current_price - 1.5,
        'ema_long': current_price + 0.5,
        'adx': 32,
        'plus_di': 18,
        'minus_di': 32,
        'bb_percent_b': 0.15,
    }

    print(f"1️⃣  策略生成信号: {signal.signal.value} - {signal.reason}")

    # 步骤 1: 趋势过滤
    print(f"\n2️⃣  趋势过滤检查...")
    trend_pass, trend_reason = trend_filter.check_signal(df, signal, indicators)
    print(f"   结果: {'✅ 通过' if trend_pass else '❌ 拒绝'}")
    print(f"   原因: {trend_reason}")

    if not trend_pass:
        print(f"\n❌ 信号被趋势过滤器拒绝，不执行交易")
        print("\n✅ 集成流程测试完成（信号被正确过滤）")
        return

    # 步骤 2: Claude 分析
    if analyzer.enabled:
        print(f"\n3️⃣  Claude AI 分析...")
        try:
            claude_pass, claude_reason, claude_details = analyzer.analyze_signal(
                df, current_price, signal, indicators
            )
            print(f"   结果: {'✅ 通过' if claude_pass else '❌ 拒绝'}")
            print(f"   原因: {claude_reason}")

            if not claude_pass:
                print(f"\n❌ 信号被 Claude 分析拒绝，不执行交易")
                print("\n✅ 集成流程测试完成（信号被正确过滤）")
                return

            print(f"\n✅ 信号通过所有检查，可以执行交易")

        except Exception as e:
            print(f"   ⚠️  Claude 分析失败: {e}")
            print(f"   使用默认行为: {config.CLAUDE_FAILURE_MODE}")
    else:
        print(f"\n3️⃣  Claude AI 分析未启用，跳过")

    print("\n✅ 集成流程测试完成")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Claude AI 集成测试")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 显示配置
    print(f"\n当前配置:")
    print(f"  趋势过滤器: {'启用' if getattr(config, 'ENABLE_TREND_FILTER', True) else '禁用'}")
    print(f"  Claude 分析: {'启用' if getattr(config, 'ENABLE_CLAUDE_ANALYSIS', False) else '禁用'}")
    if hasattr(config, 'CLAUDE_MODEL'):
        print(f"  Claude 模型: {config.CLAUDE_MODEL}")

    try:
        # 测试 1: 趋势过滤器
        test_trend_filter()

        # 测试 2: Claude 分析器
        test_claude_analyzer()

        # 测试 3: 完整集成
        test_integration()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
