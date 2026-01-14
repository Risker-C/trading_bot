#!/usr/bin/env python3
"""
对比不同数据源的布林带计算
"""
from core.trader import BitgetTrader
from strategies.indicators import IndicatorCalculator
from strategies.market_regime import MarketRegimeDetector
from config.settings import settings as config

def compare_data_sources():
    """对比数据源"""
    print("=" * 70)
    print("数据源对比分析")
    print("=" * 70)

    trader = BitgetTrader()

    # 方式1: 直接获取K线(诊断工具的方式)
    print("\n【方式1】直接获取K线:")
    df1 = trader.get_klines()
    print(f"  K线数量: {len(df1)}")
    print(f"  时间范围: {df1.index[0]} 至 {df1.index[-1]}")
    print(f"  最新价格: {df1['close'].iloc[-1]:.2f}")

    ind1 = IndicatorCalculator(df1)
    bb1 = ind1.bollinger_bands(config.BB_PERIOD, config.BB_STD_DEV)
    bandwidth1 = bb1['bandwidth'].iloc[-1]
    print(f"  布林带宽度: {bandwidth1:.2f}%")

    # 方式2: 通过MarketRegimeDetector(机器人的方式)
    print("\n【方式2】通过MarketRegimeDetector:")
    df2 = trader.get_klines()
    print(f"  K线数量: {len(df2)}")
    print(f"  时间范围: {df2.index[0]} 至 {df2.index[-1]}")
    print(f"  最新价格: {df2['close'].iloc[-1]:.2f}")

    detector = MarketRegimeDetector(df2)
    regime_info = detector.detect()
    print(f"  布林带宽度: {regime_info.bb_width:.2f}%")
    print(f"  ADX: {regime_info.adx:.1f}")
    print(f"  市场状态: {regime_info.regime.value}")

    # 对比
    print("\n【对比结果】:")
    if abs(bandwidth1 - regime_info.bb_width) < 0.01:
        print(f"  ✅ 两种方式计算结果一致: {bandwidth1:.2f}%")
    else:
        print(f"  ❌ 两种方式计算结果不一致!")
        print(f"     方式1: {bandwidth1:.2f}%")
        print(f"     方式2: {regime_info.bb_width:.2f}%")
        print(f"     差异: {abs(bandwidth1 - regime_info.bb_width):.2f}%")

    # 检查数据是否相同
    print("\n【数据一致性检查】:")
    if df1.equals(df2):
        print(f"  ✅ 两次获取的K线数据完全相同")
    else:
        print(f"  ⚠️  两次获取的K线数据不同")
        if len(df1) != len(df2):
            print(f"     数量不同: {len(df1)} vs {len(df2)}")
        if not df1.index.equals(df2.index):
            print(f"     时间索引不同")
        if not df1['close'].equals(df2['close']):
            print(f"     收盘价不同")
            # 显示差异
            diff = (df1['close'] - df2['close']).abs()
            if diff.max() > 0:
                print(f"     最大差异: {diff.max():.2f}")

    # 显示详细的布林带计算
    print("\n【详细计算】:")
    print(f"  上轨: {bb1['upper'].iloc[-1]:.2f}")
    print(f"  中轨: {bb1['middle'].iloc[-1]:.2f}")
    print(f"  下轨: {bb1['lower'].iloc[-1]:.2f}")
    print(f"  带宽公式: (upper-lower)/middle*100")
    print(f"  = ({bb1['upper'].iloc[-1]:.2f} - {bb1['lower'].iloc[-1]:.2f}) / {bb1['middle'].iloc[-1]:.2f} * 100")
    print(f"  = {bandwidth1:.2f}%")

    # 检查是否有NaN或异常值
    print("\n【数据质量检查】:")
    if df1['close'].isna().any():
        print(f"  ⚠️  收盘价包含NaN值")
    if (df1['close'] <= 0).any():
        print(f"  ⚠️  收盘价包含非正值")
    if bb1['bandwidth'].isna().any():
        print(f"  ⚠️  带宽包含NaN值")

    nan_count = bb1['bandwidth'].isna().sum()
    if nan_count > 0:
        print(f"  ⚠️  带宽序列中有 {nan_count} 个NaN值")
    else:
        print(f"  ✅ 数据质量正常")

    # 显示带宽的历史变化
    print("\n【带宽历史变化】(最近10个值):")
    recent_bandwidth = bb1['bandwidth'].tail(10)
    for i, (idx, bw) in enumerate(recent_bandwidth.items(), 1):
        print(f"  {i:2d}. {idx} | {bw:6.2f}%")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    compare_data_sources()
