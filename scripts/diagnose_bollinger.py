#!/usr/bin/env python3
"""
布林带宽度诊断工具
"""
import pandas as pd
from trader import BitgetTrader
from indicators import IndicatorCalculator
import config

def diagnose_bollinger_bands():
    """诊断布林带计算"""
    print("=" * 70)
    print("布林带宽度诊断")
    print("=" * 70)

    # 获取数据
    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    print(f"\n数据信息:")
    print(f"  K线数量: {len(df)}")
    print(f"  时间范围: {df.index[0]} 至 {df.index[-1]}")
    print(f"  当前价格: {df['close'].iloc[-1]:.2f} USDT")

    # 计算布林带
    ind = IndicatorCalculator(df)
    bb = ind.bollinger_bands(period=config.BB_PERIOD, std_dev=config.BB_STD_DEV)

    # 获取最新值
    latest_idx = -1
    close = df['close'].iloc[latest_idx]
    upper = bb['upper'].iloc[latest_idx]
    middle = bb['middle'].iloc[latest_idx]
    lower = bb['lower'].iloc[latest_idx]
    bandwidth = bb['bandwidth'].iloc[latest_idx]

    print(f"\n布林带参数:")
    print(f"  周期: {config.BB_PERIOD}")
    print(f"  标准差倍数: {config.BB_STD_DEV}")

    print(f"\n布林带数值 (最新):")
    print(f"  上轨 (upper):  {upper:.2f} USDT")
    print(f"  中轨 (middle): {middle:.2f} USDT")
    print(f"  下轨 (lower):  {lower:.2f} USDT")
    print(f"  收盘价:        {close:.2f} USDT")

    print(f"\n计算明细:")
    band_range = upper - lower
    print(f"  上下轨距离: {band_range:.2f} USDT")
    print(f"  距离/中轨:   {band_range/middle:.4f} ({band_range/middle*100:.2f}%)")
    print(f"  带宽(公式):  (upper-lower)/middle*100 = {bandwidth:.2f}%")

    # 计算标准差
    close_series = df['close'].tail(config.BB_PERIOD)
    std = close_series.std()
    mean = close_series.mean()

    print(f"\n标准差分析:")
    print(f"  {config.BB_PERIOD}根K线的均值: {mean:.2f} USDT")
    print(f"  {config.BB_PERIOD}根K线的标准差: {std:.2f} USDT")
    print(f"  标准差/均值: {std/mean:.4f} ({std/mean*100:.2f}%)")
    print(f"  理论带宽: 2 * 2 * (std/mean) * 100 = {4*std/mean*100:.2f}%")

    # 验证计算
    expected_upper = mean + config.BB_STD_DEV * std
    expected_lower = mean - config.BB_STD_DEV * std
    expected_bandwidth = (expected_upper - expected_lower) / mean * 100

    print(f"\n验证计算:")
    print(f"  理论上轨: {expected_upper:.2f} USDT")
    print(f"  理论下轨: {expected_lower:.2f} USDT")
    print(f"  理论带宽: {expected_bandwidth:.2f}%")

    # 判断是否异常
    print(f"\n诊断结果:")
    if abs(bandwidth - expected_bandwidth) < 1:
        print(f"  ✅ 带宽计算正确")
    else:
        print(f"  ⚠️  带宽计算可能有误差")
        print(f"     实际: {bandwidth:.2f}%")
        print(f"     理论: {expected_bandwidth:.2f}%")
        print(f"     差异: {abs(bandwidth - expected_bandwidth):.2f}%")

    if bandwidth > 50:
        print(f"  ⚠️  带宽 {bandwidth:.2f}% 非常高,市场处于极端波动状态")
        print(f"     这可能是:")
        print(f"     1. 市场真的在暴涨/暴跌")
        print(f"     2. 数据异常(跳空、错误数据)")
        print(f"     3. 周期设置不当")
    elif bandwidth > 10:
        print(f"  ⚠️  带宽 {bandwidth:.2f}% 较高,市场波动较大")
    elif bandwidth < 2:
        print(f"  ℹ️  带宽 {bandwidth:.2f}% 很窄,市场处于低波动状态")
    else:
        print(f"  ✅ 带宽 {bandwidth:.2f}% 正常")

    # 显示最近几根K线的价格波动
    print(f"\n最近10根K线价格:")
    recent_closes = df['close'].tail(10)
    for i, (idx, price) in enumerate(recent_closes.items(), 1):
        change = (price - recent_closes.iloc[i-2]) / recent_closes.iloc[i-2] * 100 if i > 1 else 0
        print(f"  {i:2d}. {idx} | {price:10.2f} USDT | 变化: {change:+6.2f}%")

    # 计算最大单根K线波动
    max_change = 0
    for i in range(1, len(recent_closes)):
        change = abs((recent_closes.iloc[i] - recent_closes.iloc[i-1]) / recent_closes.iloc[i-1] * 100)
        if change > max_change:
            max_change = change

    print(f"\n最近10根K线最大单根波动: {max_change:.2f}%")

    if max_change > 5:
        print(f"  ⚠️  单根K线波动超过5%,市场极端波动")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    diagnose_bollinger_bands()
