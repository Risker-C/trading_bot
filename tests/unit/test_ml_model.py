"""
测试 ML 模型是否能正常工作
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("="*80)
print("测试 ML 信号预测器")
print("="*80)

# 1. 导入模块
print("\n[1/5] 导入模块...")
try:
    from ai.ml_predictor import get_ml_predictor
    from strategies.strategies import TradeSignal, Signal
    from ai.feature_engineer import FeatureEngineer
    print("✅ 模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

# 2. 初始化 ML 预测器
print("\n[2/5] 初始化 ML 预测器...")
try:
    predictor = get_ml_predictor()
    print(f"✅ ML 预测器初始化成功")
    print(f"   模型路径: {predictor.model_path}")
    print(f"   运行模式: {predictor.mode}")
    print(f"   模型已加载: {predictor.model is not None}")

    if predictor.model is not None:
        print(f"   模型类型: {type(predictor.model).__name__}")
        print(f"   特征数量: {len(predictor.feature_names) if predictor.feature_names else 'unknown'}")
except Exception as e:
    print(f"❌ ML 预测器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 创建模拟数据
print("\n[3/5] 创建模拟 K 线数据...")
try:
    # 创建足够长的历史数据（至少100条）
    dates = pd.date_range(end=datetime.now(), periods=200, freq='15min')

    # 生成模拟价格数据
    base_price = 95000
    price_changes = np.random.randn(200).cumsum() * 100
    closes = base_price + price_changes

    df = pd.DataFrame({
        'timestamp': dates,
        'open': closes + np.random.randn(200) * 50,
        'high': closes + np.abs(np.random.randn(200)) * 100,
        'low': closes - np.abs(np.random.randn(200)) * 100,
        'close': closes,
        'volume': np.random.uniform(100, 1000, 200)
    })

    # 添加基本技术指标
    df['rsi'] = 50 + np.random.randn(200) * 10
    df['macd'] = np.random.randn(200) * 50
    df['macd_signal'] = df['macd'] + np.random.randn(200) * 10
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    df['atr'] = np.abs(np.random.randn(200)) * 200 + 300
    df['adx'] = 20 + np.abs(np.random.randn(200)) * 15
    df['plus_di'] = 15 + np.abs(np.random.randn(200)) * 10
    df['minus_di'] = 15 + np.abs(np.random.randn(200)) * 10
    df['bb_upper'] = closes + 1000
    df['bb_middle'] = closes
    df['bb_lower'] = closes - 1000
    df['bb_percent_b'] = 0.5 + np.random.randn(200) * 0.2
    df['ema_short'] = closes + np.random.randn(200) * 100
    df['ema_long'] = closes + np.random.randn(200) * 200
    df['volume_ratio'] = 1.0 + np.random.randn(200) * 0.3

    print(f"✅ 模拟数据创建成功")
    print(f"   数据行数: {len(df)}")
    print(f"   列数: {len(df.columns)}")
    print(f"   最新价格: {df['close'].iloc[-1]:.2f}")

except Exception as e:
    print(f"❌ 数据创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 创建测试信号
print("\n[4/5] 创建测试信号...")
try:
    test_signals = [
        TradeSignal(Signal.LONG, "macd_cross", "MACD金叉", strength=0.75, confidence=0.8),
        TradeSignal(Signal.SHORT, "rsi_overbought", "RSI超买", strength=0.65, confidence=0.7),
        TradeSignal(Signal.LONG, "ema_cross", "EMA金叉", strength=0.55, confidence=0.6),
    ]

    print(f"✅ 测试信号创建成功")
    print(f"   信号数量: {len(test_signals)}")
    for i, sig in enumerate(test_signals, 1):
        print(f"   信号{i}: {sig.strategy} - {sig.signal.value} (强度={sig.strength:.2f})")

except Exception as e:
    print(f"❌ 信号创建失败: {e}")
    sys.exit(1)

# 5. 测试预测功能
print("\n[5/5] 测试 ML 预测功能...")
print("-" * 80)

if predictor.model is None:
    print("⚠️  ML 模型未加载，无法进行预测测试")
    print("   请检查模型文件是否存在: models/signal_quality_v1.pkl")
    sys.exit(1)

try:
    # 测试单个信号预测
    print("\n测试 1: 单个信号预测")
    for i, signal in enumerate(test_signals, 1):
        print(f"\n信号 {i}: {signal.strategy} ({signal.signal.value})")

        try:
            quality_score = predictor.predict_signal_quality(df, signal)

            if quality_score is None:
                print(f"  ❌ 预测失败: 返回 None")
            else:
                print(f"  ✅ 预测成功")
                print(f"     质量分数: {quality_score:.4f} ({quality_score*100:.2f}%)")
                print(f"     是否通过阈值(0.6): {'✅ 是' if quality_score >= 0.6 else '❌ 否'}")

        except Exception as e:
            print(f"  ❌ 预测出错: {e}")
            import traceback
            traceback.print_exc()

    # 测试批量过滤
    print("\n" + "-" * 80)
    print("测试 2: 批量信号过滤")

    try:
        filtered_signals, predictions = predictor.filter_signals(test_signals, df, threshold=0.6)

        print(f"\n✅ 批量过滤成功")
        print(f"   原始信号数: {len(test_signals)}")
        print(f"   过滤后信号数: {len(filtered_signals)}")
        print(f"   过滤率: {(1 - len(filtered_signals)/len(test_signals))*100:.1f}%")

        print(f"\n预测详情:")
        for pred in predictions:
            quality = pred.get('quality_score')
            if quality is None:
                quality_str = "None (预测失败)"
            else:
                quality_str = f"{quality:.4f} ({quality*100:.2f}%)"

            print(f"   {pred['strategy']:20s} | 质量: {quality_str:25s} | 通过: {pred['passed']}")

    except Exception as e:
        print(f"❌ 批量过滤失败: {e}")
        import traceback
        traceback.print_exc()

    # 显示统计信息
    print("\n" + "-" * 80)
    print("统计信息:")
    stats = predictor.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")

except Exception as e:
    print(f"\n❌ 测试过程出错: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ 测试完成")
print("="*80)

# 诊断建议
print("\n📋 诊断结果:")
if predictor.model is not None:
    if predictor.stats['total_predictions'] > 0:
        avg_quality = predictor.stats['avg_quality_score']
        if avg_quality > 0:
            print("✅ ML 模型工作正常")
            print(f"   平均质量分数: {avg_quality:.4f} ({avg_quality*100:.2f}%)")
            print(f"\n💡 建议:")
            if avg_quality >= 0.6:
                print("   - ML 模型表现良好，可以考虑切换到 filter 模式")
                print("   - 修改 config.py: ML_MODE = 'filter'")
            else:
                print("   - ML 模型预测质量偏低，建议继续在 shadow 模式下观察")
                print("   - 或者考虑重新训练模型")
        else:
            print("⚠️  所有预测都失败了（返回 None）")
            print("   可能的原因:")
            print("   1. 特征提取失败")
            print("   2. 模型与当前数据不兼容")
            print("   3. 缺少必要的技术指标")
    else:
        print("⚠️  没有进行任何预测")
else:
    print("❌ ML 模型未加载")
