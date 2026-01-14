#!/usr/bin/env python3
"""
诊断脚本：检查为什么不做单

分析内容：
1. 市场状态检测
2. 策略信号生成
3. 各个过滤器状态
4. 配置参数检查
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings as config
from core.trader import BitgetTrader
from strategies.strategies import analyze_all_strategies, Signal
from strategies.market_regime import MarketRegimeDetector
from utils.logger_utils import get_logger

logger = get_logger("diagnose_no_trade")

def main():
    print("\n" + "="*60)
    print("诊断：为什么不做单")
    print("="*60)

    # 初始化交易器
    trader = BitgetTrader()

    # 获取K线数据
    print("\n1. 获取市场数据...")
    df = trader.get_klines()
    if df is None or df.empty:
        print("❌ 无法获取K线数据")
        return

    current_price = df['close'].iloc[-1]
    print(f"✓ 当前价格: {current_price:.2f}")
    print(f"✓ K线数量: {len(df)}")

    # 市场状态检测
    print("\n2. 市场状态检测...")
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"  市场状态: {regime_info.regime.value}")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")
    print(f"  波动率: {regime_info.volatility:.2%}")

    can_trade, trade_reason = detector.should_trade(regime_info)
    print(f"  是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
    print(f"  原因: {trade_reason}")

    if not can_trade:
        print("\n⚠️ 问题诊断：市场状态不适合交易")
        return

    # 动态策略选择
    print("\n3. 策略选择...")
    if config.USE_DYNAMIC_STRATEGY:
        selected_strategies = detector.get_suitable_strategies(regime_info)
        print(f"  动态策略: {', '.join(selected_strategies)}")
    else:
        selected_strategies = config.ENABLE_STRATEGIES
        print(f"  固定策略: {', '.join(selected_strategies)}")

    # 策略分析
    print("\n4. 策略信号分析...")
    signals = analyze_all_strategies(df, selected_strategies)

    print(f"  产生信号数量: {len(signals)}")

    if not signals:
        print("\n⚠️ 问题诊断：所有策略都没有产生信号")
        print("\n可能原因：")
        print("  1. 市场处于横盘整理，没有明确方向")
        print("  2. 技术指标没有达到策略的触发条件")
        print("  3. 策略参数设置过于严格")
        return

    # 显示信号详情
    for i, sig in enumerate(signals, 1):
        print(f"\n  信号 {i}:")
        print(f"    策略: {sig.strategy}")
        print(f"    方向: {sig.signal.value}")
        print(f"    强度: {sig.strength:.2f}")
        print(f"    置信度: {sig.confidence:.2f}")
        print(f"    原因: {sig.reason}")

    # 统计信号方向
    long_signals = sum(1 for s in signals if s.signal == Signal.LONG)
    short_signals = sum(1 for s in signals if s.signal == Signal.SHORT)
    strategy_agreement = max(long_signals, short_signals) / len(signals) if signals else 0

    print(f"\n5. 信号统计...")
    print(f"  做多信号: {long_signals}")
    print(f"  做空信号: {short_signals}")
    print(f"  策略一致性: {strategy_agreement:.2f}")

    # 检查共识条件
    print(f"\n6. 共识条件检查...")
    print(f"  MIN_STRATEGY_AGREEMENT: {config.MIN_STRATEGY_AGREEMENT} (要求)")
    print(f"  当前策略一致性: {strategy_agreement:.2f} ({'✅ 通过' if strategy_agreement >= config.MIN_STRATEGY_AGREEMENT else '❌ 不通过'})")

    # 检查信号强度
    max_strength = max([s.strength for s in signals]) if signals else 0
    print(f"\n  MIN_SIGNAL_STRENGTH: {config.MIN_SIGNAL_STRENGTH} (要求)")
    print(f"  最大信号强度: {max_strength:.2f} ({'✅ 通过' if max_strength >= config.MIN_SIGNAL_STRENGTH else '❌ 不通过'})")

    # 检查信号置信度
    max_confidence = max([s.confidence for s in signals]) if signals else 0
    print(f"\n  MIN_SIGNAL_CONFIDENCE: {config.MIN_SIGNAL_CONFIDENCE} (要求)")
    print(f"  最大置信度: {max_confidence:.2f} ({'✅ 通过' if max_confidence >= config.MIN_SIGNAL_CONFIDENCE else '❌ 不通过'})")

    # 总结
    print("\n" + "="*60)
    print("诊断总结")
    print("="*60)

    if not signals:
        print("❌ 策略没有产生任何信号")
    elif strategy_agreement < config.MIN_STRATEGY_AGREEMENT:
        print(f"❌ 策略一致性不足: {strategy_agreement:.2f} < {config.MIN_STRATEGY_AGREEMENT}")
    elif max_strength < config.MIN_SIGNAL_STRENGTH:
        print(f"❌ 信号强度不足: {max_strength:.2f} < {config.MIN_SIGNAL_STRENGTH}")
    elif max_confidence < config.MIN_SIGNAL_CONFIDENCE:
        print(f"❌ 信号置信度不足: {max_confidence:.2f} < {config.MIN_SIGNAL_CONFIDENCE}")
    else:
        print("✅ 信号满足基本条件，可能被后续过滤器拒绝")
        print("   建议查看日志中的趋势过滤、方向过滤、Claude分析记录")

    print("="*60)

if __name__ == "__main__":
    main()
