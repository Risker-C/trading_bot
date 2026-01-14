#!/usr/bin/env python3
"""
诊断脚本：检查为什么没有生成交易信号
"""
import sys
sys.path.insert(0, '/root/trading_bot')

from core.trader import BitgetTrader
from strategies.market_regime import MarketRegimeDetector
from strategies.strategies import analyze_all_strategies
from config.settings import settings as config

def main():
    print("=" * 60)
    print("交易信号诊断")
    print("=" * 60)

    # 获取市场数据
    trader = BitgetTrader()
    df = trader.get_klines(config.SYMBOL, config.TIMEFRAME, config.KLINE_LIMIT)
    current_price = df['close'].iloc[-1]

    print(f"\n当前价格: {current_price:.2f} USDT")
    print(f"K线数据: {len(df)} 根")

    # 检查市场状态
    print("\n" + "=" * 60)
    print("1. 市场状态检测")
    print("=" * 60)

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"市场状态: {regime_info.regime.value.upper()}")
    print(f"置信度: {regime_info.confidence:.2%}")
    print(f"波动率: {regime_info.volatility:.2%}")
    print(f"ADX: {regime_info.adx:.1f}")
    print(f"BB宽度: {regime_info.bb_width:.2%}")

    # 检查是否可交易
    print("\n" + "=" * 60)
    print("2. 交易许可检查")
    print("=" * 60)

    can_trade, reason = detector.should_trade(regime_info)
    print(f"是否可交易: {'✅ 是' if can_trade else '❌ 否'}")
    print(f"原因: {reason}")

    if not can_trade:
        print("\n⚠️ 市场状态不允许交易，这是无信号的原因！")
        return

    # 获取选定策略
    print("\n" + "=" * 60)
    print("3. 策略选择")
    print("=" * 60)

    if hasattr(config, 'USE_DYNAMIC_STRATEGY') and config.USE_DYNAMIC_STRATEGY:
        selected_strategies = detector.get_suitable_strategies(regime_info)
        print(f"动态策略选择: 启用")
    else:
        selected_strategies = config.ENABLE_STRATEGIES
        print(f"动态策略选择: 禁用")

    print(f"选定策略: {', '.join(selected_strategies)}")

    # 分析策略信号
    print("\n" + "=" * 60)
    print("4. 策略信号分析")
    print("=" * 60)

    signals = analyze_all_strategies(df, selected_strategies)
    print(f"生成信号数量: {len(signals)}")

    if not signals:
        print("\n⚠️ 策略未生成任何信号，这是无交易的原因！")
        print("可能原因:")
        print("  - 市场条件不满足任何策略的入场条件")
        print("  - 技术指标未达到信号阈值")
        return

    print("\n信号详情:")
    for sig in signals:
        print(f"  策略: {sig.strategy}")
        print(f"    信号: {sig.signal.value}")
        print(f"    强度: {sig.strength:.2f}")
        print(f"    置信度: {sig.confidence:.2f}")
        print(f"    原因: {sig.reason}")
        print()

    # 检查共识机制
    print("=" * 60)
    print("5. 共识机制检查")
    print("=" * 60)

    if hasattr(config, 'USE_CONSENSUS_SIGNAL') and config.USE_CONSENSUS_SIGNAL:
        print(f"共识信号: 启用")
        print(f"最小策略一致性: {config.MIN_STRATEGY_AGREEMENT:.0%}")
        print(f"最小信号强度: {config.MIN_SIGNAL_STRENGTH:.2f}")
        print(f"最小信号置信度: {config.MIN_SIGNAL_CONFIDENCE:.2f}")

        # 计算一致性
        from collections import Counter
        signal_types = [sig.signal for sig in signals]
        signal_counts = Counter(signal_types)

        print(f"\n信号统计:")
        for sig_type, count in signal_counts.items():
            agreement = count / len(signals)
            print(f"  {sig_type.value}: {count}/{len(signals)} ({agreement:.0%})")

        # 检查是否满足共识
        max_agreement = max(signal_counts.values()) / len(signals) if signals else 0

        print(f"\n最大一致性: {max_agreement:.0%}")
        if max_agreement < config.MIN_STRATEGY_AGREEMENT:
            print(f"❌ 未达到最小一致性要求 ({config.MIN_STRATEGY_AGREEMENT:.0%})")
            print("这可能是无交易的原因！")
        else:
            print(f"✅ 达到最小一致性要求")

        # 检查信号强度和置信度
        strong_signals = [s for s in signals if s.strength >= config.MIN_SIGNAL_STRENGTH and s.confidence >= config.MIN_SIGNAL_CONFIDENCE]
        print(f"\n满足强度和置信度要求的信号: {len(strong_signals)}/{len(signals)}")

        if not strong_signals:
            print("❌ 没有信号满足强度和置信度要求")
            print("这可能是无交易的原因！")
    else:
        print("共识信号: 禁用")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
