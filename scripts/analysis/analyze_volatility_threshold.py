"""
分析当前波动率阈值设置是否合理
使用 Claude Policy Analyzer 进行专业评估
"""
import sys
import asyncio
from datetime import datetime
import pandas as pd

import config
from core.trader import BitgetTrader
from strategies.market_regime import MarketRegimeDetector
from ai.claude_policy_analyzer import ClaudePolicyAnalyzer
from ai.policy_layer import TradingContext, MarketRegime as PolicyMarketRegime
from utils.logger_utils import get_logger, db

logger = get_logger("volatility_analysis")


async def analyze_volatility_threshold():
    """分析波动率阈值设置"""

    print("=" * 80)
    print("波动率阈值分析")
    print("=" * 80)
    print()

    # 1. 获取当前市场数据
    print("📊 正在获取市场数据...")
    trader = BitgetTrader()

    # 获取K线数据
    df = trader.get_klines(
        symbol=config.SYMBOL,
        timeframe=config.TIMEFRAME,
        limit=500
    )

    if df is None or len(df) == 0:
        print("❌ 无法获取市场数据")
        return

    current_price = df['close'].iloc[-1]
    print(f"✅ 当前价格: {current_price:.2f} USDT")
    print()

    # 2. 检测市场状态
    print("🔍 正在检测市场状态...")
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"市场状态: {regime_info.regime.value}")
    print(f"趋势方向: {regime_info.trend_direction}")
    print(f"波动率: {regime_info.volatility:.2%}")
    print(f"ADX: {regime_info.adx:.1f}")
    print(f"置信度: {regime_info.confidence:.0%}")
    print()

    # 3. 检查当前配置
    print("⚙️  当前配置:")
    print(f"HIGH_VOLATILITY_THRESHOLD: {config.HIGH_VOLATILITY_THRESHOLD:.2%}")
    print(f"极端波动阈值 (1.5倍): {config.HIGH_VOLATILITY_THRESHOLD * 1.5:.2%}")
    print()

    # 4. 判断是否能交易
    can_trade, reason = detector.should_trade(regime_info)
    print(f"是否可以交易: {'✅ 是' if can_trade else '❌ 否'}")
    print(f"原因: {reason}")
    print()

    # 5. 获取历史交易数据
    print("📈 正在加载历史交易数据...")
    recent_trades = db.get_trades(limit=50)

    # 计算统计数据
    if recent_trades:
        winning_trades = [t for t in recent_trades if t['pnl'] > 0]
        win_rate = len(winning_trades) / len(recent_trades) * 100
        total_pnl = sum(t['pnl'] for t in recent_trades)
        print(f"历史交易: {len(recent_trades)}笔")
        print(f"胜率: {win_rate:.1f}%")
        print(f"总盈亏: {total_pnl:.2f} USDT")
    else:
        win_rate = 0
        total_pnl = 0
        print("暂无历史交易数据")
    print()

    # 6. 构建交易上下文
    print("🤖 正在调用 Claude Policy Analyzer 进行分析...")
    print()

    # 获取技术指标
    from strategies.indicators import IndicatorCalculator
    calc = IndicatorCalculator(df)

    # 计算所需的技术指标
    macd_data = calc.macd()
    bb_data = calc.bollinger_bands()
    adx_data = calc.adx()

    indicators = {
        'rsi': calc.rsi(14),
        'macd': macd_data['macd'],
        'macd_signal': macd_data['signal'],
        'macd_histogram': macd_data['histogram'],
        'ema_short': calc.ema(9),
        'ema_long': calc.ema(21),
        'bb_upper': bb_data['upper'],
        'bb_middle': bb_data['middle'],
        'bb_lower': bb_data['lower'],
        'bb_percent_b': bb_data['percent_b'],
        'adx': adx_data['adx'],
        'plus_di': adx_data['plus_di'],
        'minus_di': adx_data['minus_di'],
        'volume_ratio': calc.volume_ratio(),
        'atr': calc.atr()
    }

    # 计算历史交易统计
    from ai.policy_layer import RiskMode

    if recent_trades:
        winning_trades_list = [t for t in recent_trades if t['pnl'] > 0]
        losing_trades_list = [t for t in recent_trades if t['pnl'] < 0]
        avg_win_val = sum(t['pnl'] for t in winning_trades_list) / len(winning_trades_list) if winning_trades_list else 0
        avg_loss_val = sum(t['pnl'] for t in losing_trades_list) / len(losing_trades_list) if losing_trades_list else 0
        recent_pnl_val = sum(t['pnl'] for t in recent_trades[-10:])
    else:
        avg_win_val = 0
        avg_loss_val = 0
        recent_pnl_val = 0

    # 构建上下文
    context = TradingContext(
        # A. 历史交易状态
        recent_trades_count=len(recent_trades) if recent_trades else 0,
        win_rate=win_rate / 100,
        recent_pnl=recent_pnl_val,
        consecutive_losses=0,
        consecutive_wins=0,
        avg_win=avg_win_val,
        avg_loss=avg_loss_val,

        # B. 当前持仓状态
        has_position=False,
        position_side=None,
        position_amount=0,
        entry_price=0,
        current_price=current_price,
        unrealized_pnl=0,
        unrealized_pnl_pct=0,
        holding_time_minutes=0,
        current_stop_loss=0,
        current_take_profit=0,

        # C. 实时市场结构
        market_regime=PolicyMarketRegime.TREND if regime_info.regime.value == 'TRENDING' else PolicyMarketRegime.CHOP,
        trend_direction=regime_info.trend_direction,
        volatility=regime_info.volatility,
        adx=regime_info.adx,
        volume_ratio=indicators['volume_ratio'].iloc[-1] if len(indicators['volume_ratio']) > 0 else 1.0,

        # D. 系统状态
        current_risk_mode=RiskMode.NORMAL,
        daily_pnl=0,
        daily_trades=0
    )

    # 7. 调用 Claude 分析
    analyzer = ClaudePolicyAnalyzer()

    if not analyzer.enabled:
        print("❌ Claude Policy Analyzer 未启用")
        print("请检查配置:")
        print("  - ENABLE_CLAUDE_ANALYSIS")
        print("  - CLAUDE_API_KEY")
        return

    try:
        decision = await asyncio.to_thread(
            analyzer.analyze_for_policy,
            context=context,
            df=df,
            indicators=indicators
        )

        if decision:
            print("=" * 80)
            print("📋 Claude 分析结果")
            print("=" * 80)
            print()
            print(f"市场制度: {decision.regime.value}")
            print(f"制度置信度: {decision.regime_confidence:.0%}")
            print(f"风控模式: {decision.risk_mode.value}")
            print()
            print("参数建议:")
            print(f"  止损: {decision.stop_loss_pct:.2%} (当前: {config.STOP_LOSS_PERCENT:.2%})")
            print(f"  止盈: {decision.take_profit_pct:.2%} (当前: {config.TAKE_PROFIT_PERCENT:.2%})")
            print(f"  移动止损: {decision.trailing_stop_pct:.2%} (当前: {config.TRAILING_STOP_PERCENT:.2%})")
            print(f"  仓位倍数: {decision.position_multiplier:.2f}")
            print()
            print(f"决策置信度: {decision.confidence:.0%}")
            print(f"有效期: {decision.ttl_minutes} 分钟")
            print()
            print(f"理由: {decision.reason}")
            print()

            # 8. 分析建议
            print("=" * 80)
            print("💡 波动率阈值调整建议")
            print("=" * 80)
            print()

            current_threshold = config.HIGH_VOLATILITY_THRESHOLD * 1.5
            current_volatility = regime_info.volatility

            print(f"当前波动率: {current_volatility:.2%}")
            print(f"极端波动阈值: {current_threshold:.2%}")
            print(f"差距: {(current_volatility - current_threshold):.2%}")
            print()

            if current_volatility > current_threshold:
                print("⚠️  当前波动率超过极端阈值，系统拒绝交易")
                print()
                print("分析:")
                print(f"1. Claude 建议的仓位倍数: {decision.position_multiplier:.2f}")
                print(f"2. Claude 建议的止损: {decision.stop_loss_pct:.2%}")
                print(f"3. Claude 建议的风控模式: {decision.risk_mode.value}")
                print()

                if decision.position_multiplier < 0.5:
                    print("✅ Claude 也认为当前市场风险过高，建议减少仓位")
                    print("   结论: 当前波动率阈值设置合理，不建议调整")
                elif decision.position_multiplier >= 1.0:
                    print("⚠️  Claude 认为可以正常交易")
                    print("   可能的原因:")
                    print("   - 强趋势市场，虽然波动大但方向明确")
                    print("   - Claude 建议通过调整止损和仓位来适应高波动")
                    print()
                    print("   建议方案:")
                    print("   方案1: 保持当前阈值，等待波动率回落")
                    print(f"   方案2: 提高阈值到 {current_volatility * 1.1:.2%}，但同时:")
                    print(f"         - 使用 Claude 建议的止损: {decision.stop_loss_pct:.2%}")
                    print(f"         - 使用 Claude 建议的仓位倍数: {decision.position_multiplier:.2f}")
                    print(f"         - 降低杠杆到 5x 或更低")
                else:
                    print("⚡ Claude 建议谨慎交易（仓位倍数 < 1.0）")
                    print("   结论: 可以适度提高阈值，但需要配合风控调整")
                    print()
                    print("   建议:")
                    print(f"   - 将 HIGH_VOLATILITY_THRESHOLD 从 {config.HIGH_VOLATILITY_THRESHOLD:.2%} 提高到 {config.HIGH_VOLATILITY_THRESHOLD * 1.3:.2%}")
                    print(f"   - 极端波动阈值将变为: {config.HIGH_VOLATILITY_THRESHOLD * 1.3 * 1.5:.2%}")
                    print(f"   - 同时采用 Claude 建议的参数调整")
            else:
                print("✅ 当前波动率在正常范围内")
                print("   波动率阈值设置合理")

        else:
            print("❌ Claude 分析失败")

    except Exception as e:
        print(f"❌ 分析过程出错: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("分析完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(analyze_volatility_threshold())
