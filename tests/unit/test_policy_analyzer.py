"""
测试 Claude Policy Analyzer
"""
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 导入必要的模块
from ai.claude_policy_analyzer import get_claude_policy_analyzer
from ai.policy_layer import TradingContext, MarketRegime, RiskMode

print("="*80)
print("测试 Claude Policy Analyzer")
print("="*80)

# 1. 初始化 Policy Analyzer
print("\n[1/4] 初始化 Policy Analyzer...")
analyzer = get_claude_policy_analyzer()

if not analyzer.enabled:
    print("❌ Policy Analyzer 未启用")
    print("可能的原因:")
    print("  - ENABLE_CLAUDE_ANALYSIS = False")
    print("  - CLAUDE_API_KEY 未配置")
    print("  - anthropic 库未安装")
    sys.exit(1)

print("✅ Policy Analyzer 初始化成功")
print(f"   模型: {analyzer.model}")
print(f"   端点: {analyzer.base_url or '默认端点'}")

# 2. 构建模拟数据
print("\n[2/4] 构建模拟交易数据...")

# 创建模拟 K线数据
dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
df = pd.DataFrame({
    'timestamp': dates,
    'open': np.random.uniform(95000, 96000, 100),
    'high': np.random.uniform(96000, 97000, 100),
    'low': np.random.uniform(94000, 95000, 100),
    'close': np.random.uniform(95000, 96000, 100),
    'volume': np.random.uniform(100, 1000, 100)
})

# 创建模拟技术指标
indicators = {
    'rsi': pd.Series([55.0] * 100),
    'macd': pd.Series([100.0] * 100),
    'macd_signal': pd.Series([95.0] * 100),
    'macd_histogram': pd.Series([5.0] * 100),
    'ema_short': pd.Series([95500.0] * 100),
    'ema_long': pd.Series([95000.0] * 100),
    'bb_upper': pd.Series([96500.0] * 100),
    'bb_middle': pd.Series([95500.0] * 100),
    'bb_lower': pd.Series([94500.0] * 100),
    'bb_percent_b': pd.Series([0.5] * 100),
    'adx': pd.Series([30.0] * 100),
    'plus_di': pd.Series([25.0] * 100),
    'minus_di': pd.Series([20.0] * 100),
    'volume_ratio': pd.Series([1.2] * 100),
    'atr': pd.Series([500.0] * 100)
}

# 创建模拟交易上下文
context = TradingContext(
    # 历史交易数据
    recent_trades_count=20,
    win_rate=0.55,
    recent_pnl=150.0,
    consecutive_losses=1,
    consecutive_wins=2,
    avg_win=80.0,
    avg_loss=-50.0,
    current_risk_mode=RiskMode.NORMAL,

    # 持仓信息
    has_position=True,
    position_side='long',
    position_amount=0.01,
    entry_price=95000.0,
    current_price=95500.0,
    unrealized_pnl=5.0,
    unrealized_pnl_pct=0.53,
    holding_time_minutes=45,
    current_stop_loss=93100.0,
    current_take_profit=98800.0,

    # 市场状态
    market_regime=MarketRegime.TREND,
    trend_direction=1,
    volatility=0.015,

    # 今日统计
    daily_pnl=200.0,
    daily_trades=5
)

print("✅ 模拟数据构建完成")
print(f"   K线数据: {len(df)} 条")
print(f"   当前价格: {context.current_price:.2f} USDT")
print(f"   持仓状态: {context.position_side.upper() if context.has_position else '无持仓'}")

# 3. 调用 Policy Analyzer
print("\n[3/4] 调用 Claude Policy Analyzer...")
print("⏳ 正在分析市场状态和策略参数...")

try:
    decision = analyzer.analyze_for_policy(context, df, indicators)

    if not decision:
        print("❌ Policy 分析失败")
        print("   可能是 API 调用出错或响应解析失败")
        sys.exit(1)

    print("✅ Policy 分析成功!")

except Exception as e:
    print(f"❌ Policy 分析出错: {e}")
    import traceback
    print("\n详细错误:")
    traceback.print_exc()
    sys.exit(1)

# 4. 显示分析结果
print("\n[4/4] 分析结果:")
print("="*80)
print(f"市场制度: {decision.regime.value}")
print(f"制度置信度: {decision.regime_confidence:.2%}")
print(f"分析置信度: {decision.confidence:.2%}")
print(f"\n建议风控模式: {decision.suggested_risk_mode.value if decision.suggested_risk_mode else '无调整'}")

if decision.suggested_stop_loss_pct:
    print(f"建议止损: {decision.suggested_stop_loss_pct:.2%}")
else:
    print("建议止损: 无调整")

if decision.suggested_take_profit_pct:
    print(f"建议止盈: {decision.suggested_take_profit_pct:.2%}")
else:
    print("建议止盈: 无调整")

if decision.suggested_trailing_stop_pct:
    print(f"建议追踪止损: {decision.suggested_trailing_stop_pct:.2%}")
else:
    print("建议追踪止损: 无调整")

if decision.enable_trailing_stop is not None:
    print(f"启用追踪止损: {'是' if decision.enable_trailing_stop else '否'}")

if decision.suggested_position_multiplier:
    print(f"建议仓位倍数: {decision.suggested_position_multiplier:.2f}x")
else:
    print("建议仓位倍数: 无调整")

print(f"\n分析有效期: {decision.ttl_minutes} 分钟")
print(f"\n分析理由:")
print(f"  {decision.reason}")

print("\n" + "="*80)
print("✅ 测试完成！Policy Analyzer 工作正常")
print("="*80)
