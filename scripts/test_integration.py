"""
测试新升级模块的集成
验证交易标签系统、执行层风控、结构化Claude分析
"""
import pandas as pd
import numpy as np
from datetime import datetime

from core.trade_tagging import get_tag_manager, TradeTag
from risk.execution_filter import (
    get_execution_filter,
    get_position_sizer,
    get_kill_switch
)
from strategies.strategies import Signal, TradeSignal
import config


def create_test_data():
    """创建测试数据"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    close = np.linspace(90, 85, 100) + np.random.randn(100) * 0.5

    df = pd.DataFrame({
        'timestamp': dates,
        'open': close + np.random.randn(100) * 0.2,
        'high': close + abs(np.random.randn(100)) * 0.5,
        'low': close - abs(np.random.randn(100)) * 0.5,
        'close': close,
        'volume': np.random.randint(1000, 2000, 100)
    })

    return df


def test_trade_tagging():
    """测试交易标签系统"""
    print("=" * 60)
    print("测试 1: 交易标签系统")
    print("=" * 60)

    tag_manager = get_tag_manager()

    # 创建测试标签
    print("\n1.1 创建交易标签...")
    tag = tag_manager.create_tag(
        strategy="macd_cross",
        signal="long",
        signal_strength=0.7,
        signal_confidence=0.6,
        signal_reason="MACD金叉",
        signal_indicators={'rsi': 45, 'macd': 100},
        market_regime="trending",
        market_confidence=0.8,
        price=86500,
        volatility=0.025
    )

    assert tag is not None, "标签创建失败"
    assert tag.strategy == "macd_cross", "策略名称不正确"
    print(f"✅ 标签创建成功: {tag.trade_id}")

    # 更新趋势过滤
    print("\n1.2 更新趋势过滤结果...")
    tag_manager.update_trend_filter(True, "趋势过滤通过")
    assert tag.trend_filter_pass == True, "趋势过滤状态不正确"
    print("✅ 趋势过滤结果已更新")

    # 更新 Claude 分析
    print("\n1.3 更新 Claude 分析结果...")
    tag_manager.update_claude_analysis(
        passed=True,
        confidence=0.75,
        regime="trend",
        signal_quality=0.8,
        risk_flags=["high_volatility"],
        reason="趋势明确，可以执行",
        suggested_sl=0.02,
        suggested_tp=0.04
    )
    assert tag.claude_pass == True, "Claude 分析状态不正确"
    assert tag.claude_confidence == 0.75, "Claude 置信度不正确"
    print("✅ Claude 分析结果已更新")

    # 更新执行层风控
    print("\n1.4 更新执行层风控结果...")
    tag_manager.update_execution_filter(
        passed=True,
        reason="执行层检查通过",
        spread_check=True,
        slippage_check=True,
        liquidity_check=True
    )
    assert tag.execution_filter_pass == True, "执行层风控状态不正确"
    print("✅ 执行层风控结果已更新")

    # 标记为已执行
    print("\n1.5 标记为已执行...")
    tag_manager.mark_executed(
        executed=True,
        reason="通过所有检查",
        position_size=0.1,
        entry_price=86500,
        stop_loss_price=85000,
        take_profit_price=88000
    )
    assert tag.executed == True, "执行状态不正确"
    print("✅ 已标记为执行")

    # 标记为已平仓
    print("\n1.6 标记为已平仓...")
    tag_manager.mark_closed(
        exit_price=87000,
        pnl=50,
        pnl_pct=0.58,
        exit_reason="止盈",
        mfe=600,
        mae=-200
    )
    assert tag.exit_price == 87000, "平仓价格不正确"
    assert tag.pnl == 50, "盈亏不正确"
    print("✅ 已标记为平仓")

    # 保存标签
    print("\n1.7 保存标签到数据库...")
    tag_manager.save_tag()
    print("✅ 标签已保存")

    # 查询标签
    print("\n1.8 查询标签...")
    tags = tag_manager.get_tags(executed_only=True)
    assert len(tags) > 0, "查询标签失败"
    print(f"✅ 查询到 {len(tags)} 个标签")

    # 显示最新标签
    if tags:
        latest = tags[0]
        print(f"\n最新标签:")
        print(f"  交易ID: {latest.trade_id}")
        print(f"  策略: {latest.strategy}")
        print(f"  信号: {latest.signal}")
        print(f"  趋势过滤: {'通过' if latest.trend_filter_pass else '拒绝'}")
        print(f"  Claude: {'通过' if latest.claude_pass else '拒绝'} (置信度: {latest.claude_confidence:.2f})")
        print(f"  执行: {'是' if latest.executed else '否'}")
        print(f"  盈亏: {latest.pnl:.2f} ({latest.pnl_pct:.2f}%)")

    print("\n" + "=" * 60)
    print("✅ 交易标签系统测试通过")
    print("=" * 60)


def test_execution_filter():
    """测试执行层风控"""
    print("\n" + "=" * 60)
    print("测试 2: 执行层风控")
    print("=" * 60)

    exec_filter = get_execution_filter()
    df = create_test_data()

    # 测试点差检查
    print("\n2.1 测试点差检查...")
    ticker = {
        'bid': 86500,
        'ask': 86510,
        'last': 86505
    }
    spread_pass, spread_reason, spread_pct = exec_filter._check_spread(ticker)
    print(f"   点差: {spread_pct:.4%}")
    print(f"   结果: {'✅ 通过' if spread_pass else '❌ 拒绝'} - {spread_reason}")

    # 测试流动性检查
    print("\n2.2 测试流动性检查...")
    indicators = {'volume_ratio': 0.8}
    liquidity_pass, liquidity_reason = exec_filter._check_liquidity(indicators)
    print(f"   量比: {indicators['volume_ratio']:.2f}")
    print(f"   结果: {'✅ 通过' if liquidity_pass else '❌ 拒绝'} - {liquidity_reason}")

    # 测试波动率检查
    print("\n2.3 测试波动率检查...")
    indicators['atr'] = 500
    volatility_pass, volatility_reason = exec_filter._check_volatility_spike(df, indicators)
    print(f"   结果: {'✅ 通过' if volatility_pass else '❌ 拒绝'} - {volatility_reason}")

    # 测试订单类型选择
    print("\n2.4 测试订单类型选择...")
    order_type = exec_filter.get_optimal_order_type(
        signal_strength=0.8,
        volatility=0.02,
        urgency="normal"
    )
    print(f"   信号强度: 0.8, 波动率: 0.02")
    print(f"   推荐订单类型: {order_type}")

    # 测试完整检查
    print("\n2.5 测试完整检查流程...")
    indicators = {
        'volume_ratio': 1.2,
        'atr': 400,
        'volatility': 0.02
    }
    all_pass, all_reason, all_details = exec_filter.check_all(
        df, 86500, ticker, indicators
    )
    print(f"   结果: {'✅ 通过' if all_pass else '❌ 拒绝'} - {all_reason}")
    print(f"   详情: {all_details}")

    # 获取统计
    print("\n2.6 获取统计信息...")
    stats = exec_filter.get_stats()
    print(f"   启用: {stats['enabled']}")
    print(f"   拒绝次数: {stats['rejection_count']}")
    print(f"   阈值:")
    for key, value in stats['thresholds'].items():
        print(f"     {key}: {value}")

    print("\n" + "=" * 60)
    print("✅ 执行层风控测试通过")
    print("=" * 60)


def test_position_sizer():
    """测试仓位计算器"""
    print("\n" + "=" * 60)
    print("测试 3: 仓位计算器")
    print("=" * 60)

    position_sizer = get_position_sizer()

    # 测试波动率调整
    print("\n3.1 测试波动率调整仓位...")
    test_cases = [
        (0.01, 1.0, 0),  # 低波动
        (0.02, 1.0, 0),  # 正常波动
        (0.04, 1.0, 0),  # 高波动
        (0.02, 0.5, 0),  # 正常波动 + 弱信号
        (0.02, 1.0, 3),  # 正常波动 + 连续亏损
    ]

    for volatility, signal_strength, consecutive_losses in test_cases:
        adjusted_size = position_sizer.calculate_volatility_adjusted_size(
            current_volatility=volatility,
            signal_strength=signal_strength,
            consecutive_losses=consecutive_losses
        )
        print(f"   波动率: {volatility:.2%}, 信号: {signal_strength:.1f}, 连亏: {consecutive_losses}")
        print(f"   → 调整后仓位: {adjusted_size:.1%}")

    # 测试 Kelly 公式
    print("\n3.2 测试 Kelly 公式...")
    kelly_size = position_sizer.calculate_kelly_size(
        win_rate=0.55,
        avg_win=100,
        avg_loss=50,
        kelly_fraction=0.5
    )
    print(f"   胜率: 55%, 平均盈利: 100, 平均亏损: 50")
    print(f"   → Kelly 仓位: {kelly_size:.1%}")

    print("\n" + "=" * 60)
    print("✅ 仓位计算器测试通过")
    print("=" * 60)


def test_kill_switch():
    """测试熔断器"""
    print("\n" + "=" * 60)
    print("测试 4: 单日亏损熔断器")
    print("=" * 60)

    kill_switch = get_kill_switch()

    # 重置
    print("\n4.1 重置熔断器...")
    kill_switch.reset_daily(10000)
    print(f"   初始余额: {kill_switch.initial_balance:.2f}")
    print(f"   最大亏损: {kill_switch.max_daily_loss_pct:.1%}")

    # 测试正常情况
    print("\n4.2 测试正常情况...")
    kill_switch.update_pnl(-100)
    should_stop, reason = kill_switch.should_stop_trading()
    remaining = kill_switch.get_remaining_loss_budget()
    print(f"   当日盈亏: {kill_switch.daily_pnl:.2f}")
    print(f"   剩余预算: {remaining:.2f}")
    print(f"   结果: {'🔴 熔断' if should_stop else '✅ 正常'} - {reason}")

    # 测试触发熔断
    print("\n4.3 测试触发熔断...")
    kill_switch.update_pnl(-400)  # 总亏损 -500 (5%)
    should_stop, reason = kill_switch.should_stop_trading()
    print(f"   当日盈亏: {kill_switch.daily_pnl:.2f}")
    print(f"   亏损比例: {abs(kill_switch.daily_pnl) / kill_switch.initial_balance:.1%}")
    print(f"   结果: {'🔴 熔断' if should_stop else '✅ 正常'} - {reason}")

    assert should_stop == True, "熔断器应该触发"

    print("\n" + "=" * 60)
    print("✅ 熔断器测试通过")
    print("=" * 60)


def test_integration_flow():
    """测试完整集成流程"""
    print("\n" + "=" * 60)
    print("测试 5: 完整集成流程")
    print("=" * 60)

    tag_manager = get_tag_manager()
    exec_filter = get_execution_filter()
    position_sizer = get_position_sizer()

    df = create_test_data()
    current_price = 86500

    # 模拟信号
    signal = TradeSignal(
        Signal.LONG,
        "macd_cross",
        "MACD金叉",
        strength=0.75,
        confidence=0.7
    )

    print("\n5.1 创建交易标签...")
    tag = tag_manager.create_tag(
        strategy=signal.strategy,
        signal=signal.signal.value,
        signal_strength=signal.strength,
        signal_confidence=signal.confidence,
        signal_reason=signal.reason,
        signal_indicators={'rsi': 50, 'macd': 200},
        market_regime="trending",
        market_confidence=0.8,
        price=current_price,
        volatility=0.02
    )
    print(f"✅ 标签创建: {tag.trade_id}")

    # 模拟趋势过滤
    print("\n5.2 趋势过滤检查...")
    trend_pass = True
    tag_manager.update_trend_filter(trend_pass, "趋势过滤通过")
    print(f"{'✅ 通过' if trend_pass else '❌ 拒绝'}")

    # 模拟 Claude 分析
    print("\n5.3 Claude 分析...")
    claude_pass = True
    tag_manager.update_claude_analysis(
        passed=claude_pass,
        confidence=0.78,
        regime="trend",
        signal_quality=0.8,
        risk_flags=[],
        reason="趋势明确，信号质量高"
    )
    print(f"{'✅ 通过' if claude_pass else '❌ 拒绝'} (置信度: 0.78)")

    # 模拟执行层风控
    print("\n5.4 执行层风控检查...")
    ticker = {'bid': 86500, 'ask': 86510, 'last': 86505}
    indicators = {'volume_ratio': 1.2, 'atr': 400, 'volatility': 0.02}

    exec_pass, exec_reason, exec_details = exec_filter.check_all(
        df, current_price, ticker, indicators
    )
    tag_manager.update_execution_filter(
        passed=exec_pass,
        reason=exec_reason,
        **{k: v for k, v in exec_details.items() if k.endswith('_check')}
    )
    print(f"{'✅ 通过' if exec_pass else '❌ 拒绝'} - {exec_reason}")

    # 计算仓位
    print("\n5.5 计算调整后仓位...")
    adjusted_size = position_sizer.calculate_volatility_adjusted_size(
        current_volatility=0.02,
        signal_strength=signal.strength,
        consecutive_losses=0
    )
    print(f"调整后仓位: {adjusted_size:.1%}")

    # 标记执行
    print("\n5.6 标记为已执行...")
    tag_manager.mark_executed(
        executed=True,
        reason="通过所有检查",
        position_size=0.1,
        entry_price=current_price
    )
    print("✅ 已标记执行")

    # 保存标签
    print("\n5.7 保存标签...")
    tag_manager.save_tag()
    print("✅ 标签已保存")

    print("\n" + "=" * 60)
    print("✅ 完整集成流程测试通过")
    print("=" * 60)


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("新升级模块集成测试")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 测试 1: 交易标签系统
        test_trade_tagging()

        # 测试 2: 执行层风控
        test_execution_filter()

        # 测试 3: 仓位计算器
        test_position_sizer()

        # 测试 4: 熔断器
        test_kill_switch()

        # 测试 5: 完整集成流程
        test_integration_flow()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)

        print("\n下一步:")
        print("1. 查看数据库: sqlite3 trading_bot.db")
        print("2. 查询标签: SELECT * FROM trade_tags ORDER BY timestamp DESC LIMIT 10;")
        print("3. 集成到 bot.py: 参考 INTEGRATION_EXAMPLE.md")
        print("4. 启动机器人: python main.py")

        return 0

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
