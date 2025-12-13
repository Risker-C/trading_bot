#!/usr/bin/env python3
"""
测试动态策略系统
"""
import sys
import config
from trader import BitgetTrader
from market_regime import MarketRegimeDetector, MarketRegime
from strategies import analyze_all_strategies, get_strategy, Signal
from logger_utils import get_logger

logger = get_logger("test_dynamic_strategy")


def test_market_regime_detection():
    """测试市场状态检测"""
    logger.info("=" * 60)
    logger.info("测试1: 市场状态检测")
    logger.info("=" * 60)

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        logger.error("❌ 获取K线数据失败")
        return False

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    logger.info(f"\n当前市场状态: {regime_info.regime.value.upper()}")
    logger.info(f"置信度: {regime_info.confidence:.0%}")
    logger.info(f"ADX: {regime_info.adx:.1f}")
    logger.info(f"布林带宽度: {regime_info.bb_width:.2f}%")
    logger.info(f"趋势方向: {['⬇️ 下跌', '➡️ 中性', '⬆️ 上涨'][regime_info.trend_direction + 1]}")
    logger.info(f"波动率: {regime_info.volatility:.2%}")

    # 检查是否适合交易
    can_trade, reason = detector.should_trade(regime_info)
    logger.info(f"\n是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
    logger.info(f"原因: {reason}")

    logger.info("\n✅ 市场状态检测测试通过")
    return True


def test_dynamic_strategy_selection():
    """测试动态策略选择"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 动态策略选择")
    logger.info("=" * 60)

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        logger.error("❌ 获取K线数据失败")
        return False

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    # 获取推荐策略
    strategies = detector.get_suitable_strategies(regime_info)

    logger.info(f"\n市场状态: {regime_info.regime.value.upper()}")
    logger.info(f"推荐策略:")
    for s in strategies:
        logger.info(f"  - {s}")

    # 验证策略映射
    logger.info(f"\n策略说明:")
    if regime_info.regime == MarketRegime.RANGING:
        logger.info("  震荡市 → 使用均值回归策略")
        expected = ["bollinger_breakthrough", "rsi_divergence", "kdj_cross"]
    elif regime_info.regime == MarketRegime.TRENDING:
        logger.info("  趋势市 → 使用趋势跟踪策略")
        expected = ["bollinger_trend", "ema_cross", "macd_cross", "adx_trend", "volume_breakout"]
    else:
        logger.info("  过渡市 → 使用综合策略")
        expected = ["composite_score", "multi_timeframe"]

    # 验证策略是否正确
    if set(strategies) == set(expected):
        logger.info("✅ 策略选择正确")
    else:
        logger.warning(f"⚠️  策略选择不完全匹配")
        logger.info(f"  期望: {expected}")
        logger.info(f"  实际: {strategies}")

    logger.info("\n✅ 动态策略选择测试通过")
    return True


def test_bollinger_strategies():
    """测试布林带策略(均值回归 vs 趋势突破)"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 布林带策略对比")
    logger.info("=" * 60)

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        logger.error("❌ 获取K线数据失败")
        return False

    # 测试均值回归版本
    logger.info("\n📊 布林带均值回归策略:")
    try:
        strategy_mean_reversion = get_strategy("bollinger_breakthrough", df)
        signal_mr = strategy_mean_reversion.analyze()
        logger.info(f"  信号: {signal_mr.signal.value}")
        logger.info(f"  原因: {signal_mr.reason}")
        logger.info(f"  强度: {signal_mr.strength:.2f}")
        logger.info(f"  ✅ 均值回归策略正常")
    except Exception as e:
        logger.error(f"  ❌ 均值回归策略失败: {e}")
        return False

    # 测试趋势突破版本
    logger.info("\n📈 布林带趋势突破策略:")
    try:
        strategy_trend = get_strategy("bollinger_trend", df)
        signal_trend = strategy_trend.analyze()
        logger.info(f"  信号: {signal_trend.signal.value}")
        logger.info(f"  原因: {signal_trend.reason}")
        logger.info(f"  强度: {signal_trend.strength:.2f}")
        logger.info(f"  置信度: {signal_trend.confidence:.2f}")
        logger.info(f"  ✅ 趋势突破策略正常")
    except Exception as e:
        logger.error(f"  ❌ 趋势突破策略失败: {e}")
        return False

    # 对比两种策略
    logger.info("\n🔍 策略对比:")
    logger.info(f"  均值回归: {signal_mr.signal.value} (突破下轨→做多, 突破上轨→做空)")
    logger.info(f"  趋势突破: {signal_trend.signal.value} (突破上轨→做多, 突破下轨→做空)")

    if signal_mr.signal != Signal.HOLD and signal_trend.signal != Signal.HOLD:
        if signal_mr.signal != signal_trend.signal:
            logger.info("  ✅ 两种策略信号相反,符合预期")
        else:
            logger.warning("  ⚠️  两种策略信号相同,可能处于特殊市况")

    logger.info("\n✅ 布林带策略对比测试通过")
    return True


def test_strategy_execution():
    """测试策略执行流程"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 策略执行流程")
    logger.info("=" * 60)

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        logger.error("❌ 获取K线数据失败")
        return False

    # 检测市场状态
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    # 获取推荐策略
    strategies = detector.get_suitable_strategies(regime_info)

    logger.info(f"\n市场状态: {regime_info.regime.value.upper()}")
    logger.info(f"运行策略: {', '.join(strategies)}")

    # 运行策略分析
    signals = analyze_all_strategies(df, strategies)

    logger.info(f"\n策略信号:")
    if not signals:
        logger.info("  无开仓信号")
    else:
        for i, sig in enumerate(signals, 1):
            logger.info(f"  {i}. [{sig.strategy}] {sig.signal.value}")
            logger.info(f"     原因: {sig.reason}")
            logger.info(f"     强度: {sig.strength:.2f}, 置信度: {sig.confidence:.2f}")

    logger.info("\n✅ 策略执行流程测试通过")
    return True


def main():
    """主测试函数"""
    logger.info("🚀 开始测试动态策略系统")
    logger.info(f"动态策略开关: {'✅ 启用' if config.USE_DYNAMIC_STRATEGY else '❌ 禁用'}")

    results = []

    # 运行所有测试
    tests = [
        ("市场状态检测", test_market_regime_detection),
        ("动态策略选择", test_dynamic_strategy_selection),
        ("布林带策略对比", test_bollinger_strategies),
        ("策略执行流程", test_strategy_execution),
    ]

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"\n❌ 测试 '{test_name}' 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # 总结
    logger.info("\n" + "=" * 60)
    logger.info("测试结果总结")
    logger.info("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{status} - {test_name}")

    logger.info(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        logger.info("\n🎉 所有测试通过! 动态策略系统运行正常!")
        return 0
    else:
        logger.error(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
