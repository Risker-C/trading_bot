#!/usr/bin/env python3
"""
详细诊断：检查技术指标值和策略评分
"""
import sys
sys.path.insert(0, '/root/trading_bot')

from trader import BitgetTrader
from indicators import IndicatorCalculator
import config

def main():
    print("=" * 60)
    print("技术指标详细诊断")
    print("=" * 60)

    # 获取市场数据
    trader = BitgetTrader()
    df = trader.get_klines(config.SYMBOL, config.TIMEFRAME, config.KLINE_LIMIT)
    current_price = df['close'].iloc[-1]

    ind = IndicatorCalculator(df)

    print(f"\n当前价格: {current_price:.2f} USDT")
    print(f"K线周期: {config.TIMEFRAME}")

    # RSI
    print("\n" + "=" * 60)
    print("1. RSI 指标")
    print("=" * 60)
    rsi = ind.rsi().iloc[-1]
    print(f"RSI: {rsi:.2f}")
    if rsi < 30:
        print("  → 超卖 (< 30) - 强烈看多信号")
    elif rsi < 40:
        print("  → 偏低 (30-40) - 看多信号")
    elif rsi > 70:
        print("  → 超买 (> 70) - 强烈看空信号")
    elif rsi > 60:
        print("  → 偏高 (60-70) - 看空信号")
    else:
        print("  → 中性 (40-60) - 无明确信号")

    # MACD
    print("\n" + "=" * 60)
    print("2. MACD 指标")
    print("=" * 60)
    macd = ind.macd()
    macd_line = macd['macd'].iloc[-1]
    signal_line = macd['signal'].iloc[-1]
    hist = macd['histogram'].iloc[-1]
    hist_prev = macd['histogram'].iloc[-2]

    print(f"MACD: {macd_line:.2f}")
    print(f"Signal: {signal_line:.2f}")
    print(f"Histogram: {hist:.2f} (前值: {hist_prev:.2f})")

    if hist > 0 and hist > hist_prev:
        print("  → 柱状图为正且增长 - 强烈看多")
    elif hist > 0:
        print("  → 柱状图为正但减弱 - 看多")
    elif hist < 0 and hist < hist_prev:
        print("  → 柱状图为负且下降 - 强烈看空")
    elif hist < 0:
        print("  → 柱状图为负但收敛 - 看空")
    else:
        print("  → 中性")

    # EMA
    print("\n" + "=" * 60)
    print("3. EMA 指标")
    print("=" * 60)
    ema_short = ind.ema(9).iloc[-1]
    ema_long = ind.ema(21).iloc[-1]

    print(f"EMA(9): {ema_short:.2f}")
    print(f"EMA(21): {ema_long:.2f}")
    print(f"差值: {ema_short - ema_long:.2f} ({(ema_short/ema_long - 1)*100:.2f}%)")

    if ema_short > ema_long:
        print("  → 短期均线在上 - 看多")
    else:
        print("  → 短期均线在下 - 看空")

    # 趋势
    print("\n" + "=" * 60)
    print("4. 趋势指标")
    print("=" * 60)
    trend_dir = ind.trend_direction().iloc[-1]
    trend_str = ind.trend_strength().iloc[-1]

    print(f"趋势方向: {trend_dir:.2f} ({'看多' if trend_dir > 0 else '看空' if trend_dir < 0 else '中性'})")
    print(f"趋势强度: {trend_str:.2f}")

    # ADX
    print("\n" + "=" * 60)
    print("5. ADX 指标")
    print("=" * 60)
    adx_data = ind.adx()
    adx = adx_data['adx'].iloc[-1]
    plus_di = adx_data['plus_di'].iloc[-1]
    minus_di = adx_data['minus_di'].iloc[-1]

    print(f"ADX: {adx:.2f}")
    print(f"+DI: {plus_di:.2f}")
    print(f"-DI: {minus_di:.2f}")

    if adx > 25:
        if plus_di > minus_di:
            print(f"  → 趋势强劲 (ADX > 25) 且 +DI > -DI - 看多")
        else:
            print(f"  → 趋势强劲 (ADX > 25) 且 -DI > +DI - 看空")
    else:
        print(f"  → 趋势较弱 (ADX < 25) - 震荡市")

    # 布林带
    print("\n" + "=" * 60)
    print("6. 布林带指标")
    print("=" * 60)
    bb = ind.bollinger_bands()
    bb_upper = bb['upper'].iloc[-1]
    bb_middle = bb['middle'].iloc[-1]
    bb_lower = bb['lower'].iloc[-1]
    percent_b = bb['percent_b'].iloc[-1]

    print(f"上轨: {bb_upper:.2f}")
    print(f"中轨: {bb_middle:.2f}")
    print(f"下轨: {bb_lower:.2f}")
    print(f"当前价格: {current_price:.2f}")
    print(f"%B: {percent_b:.2f}")

    if percent_b < 0:
        print("  → 价格低于下轨 - 强烈看多")
    elif percent_b < 0.2:
        print("  → 价格接近下轨 - 看多")
    elif percent_b > 1:
        print("  → 价格高于上轨 - 强烈看空")
    elif percent_b > 0.8:
        print("  → 价格接近上轨 - 看空")
    else:
        print("  → 价格在中间区域 - 中性")

    # KDJ
    print("\n" + "=" * 60)
    print("7. KDJ 指标")
    print("=" * 60)
    kdj = ind.kdj()
    k = kdj['k'].iloc[-1]
    d = kdj['d'].iloc[-1]
    j = kdj['j'].iloc[-1]

    print(f"K: {k:.2f}")
    print(f"D: {d:.2f}")
    print(f"J: {j:.2f}")

    if k < 20 and j < 0:
        print("  → K < 20 且 J < 0 - 强烈看多")
    elif k < 30:
        print("  → K < 30 - 看多")
    elif k > 80 and j > 100:
        print("  → K > 80 且 J > 100 - 强烈看空")
    elif k > 70:
        print("  → K > 70 - 看空")
    else:
        print("  → 中性")

    # MultiTimeframe 策略分析
    print("\n" + "=" * 60)
    print("8. MultiTimeframe 策略评分")
    print("=" * 60)

    # 计算各指标信号
    rsi_signal = 1 if rsi < 40 else (-1 if rsi > 60 else 0)
    macd_signal = 1 if hist > 0 else -1
    ema_signal = 1 if ema_short > ema_long else -1
    trend_signal = trend_dir

    print(f"RSI信号: {rsi_signal:+d} ({'看多' if rsi_signal > 0 else '看空' if rsi_signal < 0 else '中性'})")
    print(f"MACD信号: {macd_signal:+d} ({'看多' if macd_signal > 0 else '看空'})")
    print(f"EMA信号: {ema_signal:+d} ({'看多' if ema_signal > 0 else '看空'})")
    print(f"趋势信号: {trend_signal:+.2f} ({'看多' if trend_signal > 0 else '看空' if trend_signal < 0 else '中性'})")

    total_signal = rsi_signal + macd_signal + ema_signal + trend_signal
    direction = 1 if total_signal > 1 else (-1 if total_signal < -1 else 0)
    strength = abs(total_signal) / 4

    print(f"\n总信号: {total_signal:+.2f}")
    print(f"方向: {direction:+d} ({'看多' if direction > 0 else '看空' if direction < 0 else '中性'})")
    print(f"强度: {strength:.2f}")

    print(f"\n⚠️ 信号生成条件:")
    print(f"  - 需要 total_signal > 1 (看多) 或 < -1 (看空)")
    print(f"  - 需要 strength > 0.5 (即 |total_signal| > 2)")

    if direction == 0:
        print(f"\n❌ 无信号: total_signal = {total_signal:.2f}, 未达到阈值 (需要 > 1 或 < -1)")
    elif strength <= 0.5:
        print(f"\n❌ 无信号: 虽然方向明确 ({direction:+d}), 但强度不足 ({strength:.2f} <= 0.5)")
    else:
        print(f"\n✅ 会生成信号: 方向={direction:+d}, 强度={strength:.2f}")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
