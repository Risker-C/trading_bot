#!/usr/bin/env python3
"""
测试 RiskManager.record_trade_result 方法
验证交易记录和统计功能是否正常工作
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk_manager import RiskManager


def print_status(risk_manager, prefix=""):
    """打印当前统计状态"""
    m = risk_manager.metrics
    print(f"{prefix}总交易={m.total_trades}, 胜率={m.win_rate:.1%}, "
          f"连胜={m.consecutive_wins}, 连亏={m.consecutive_losses}")


def test_record_profit():
    """测试记录盈利交易"""
    print("\n测试1: 记录盈利交易")
    rm = RiskManager()

    # 记录初始状态
    initial_total = rm.metrics.total_trades
    initial_wins = rm.metrics.winning_trades
    initial_losses = rm.metrics.losing_trades
    initial_pnl = rm.metrics.total_pnl

    print_status(rm, "初始状态: ")

    # 记录一笔盈利
    rm.record_trade_result(10.50)
    print(f"记录盈利: +10.50")

    print_status(rm, "更新后: ")

    # 验证相对变化
    assert rm.metrics.total_trades == initial_total + 1, f"总交易数应增加1，实际从{initial_total}变为{rm.metrics.total_trades}"
    assert rm.metrics.winning_trades == initial_wins + 1, f"盈利交易数应增加1，实际从{initial_wins}变为{rm.metrics.winning_trades}"
    assert rm.metrics.losing_trades == initial_losses, f"亏损交易数应不变，实际从{initial_losses}变为{rm.metrics.losing_trades}"
    assert rm.metrics.consecutive_wins == 1, "连胜应为1"
    assert rm.metrics.consecutive_losses == 0, "连亏应为0"
    assert abs(rm.metrics.total_pnl - (initial_pnl + 10.50)) < 0.01, f"总盈亏应增加10.50，实际从{initial_pnl}变为{rm.metrics.total_pnl}"

    print("✅ 测试通过")
    return rm


def test_record_loss(rm):
    """测试记录亏损交易"""
    print("\n测试2: 记录亏损交易")

    # 记录初始状态
    initial_total = rm.metrics.total_trades
    initial_wins = rm.metrics.winning_trades
    initial_losses = rm.metrics.losing_trades
    initial_pnl = rm.metrics.total_pnl

    # 记录一笔亏损
    rm.record_trade_result(-5.25)
    print(f"记录亏损: -5.25")

    print_status(rm, "更新后: ")

    # 验证相对变化
    assert rm.metrics.total_trades == initial_total + 1, f"总交易数应增加1"
    assert rm.metrics.winning_trades == initial_wins, f"盈利交易数应不变"
    assert rm.metrics.losing_trades == initial_losses + 1, f"亏损交易数应增加1"
    assert rm.metrics.consecutive_wins == 0, "连胜应为0"
    assert rm.metrics.consecutive_losses == 1, "连亏应为1"
    assert abs(rm.metrics.total_pnl - (initial_pnl - 5.25)) < 0.01, f"总盈亏应减少5.25"
    assert rm.last_loss_time is not None, "应记录亏损时间"

    print("✅ 测试通过")
    return rm


def test_consecutive_wins(rm):
    """测试连续盈利统计"""
    print("\n测试3: 连续盈利统计")

    # 记录初始状态
    initial_total = rm.metrics.total_trades
    initial_wins = rm.metrics.winning_trades

    # 记录连续盈利
    rm.record_trade_result(8.00)
    print(f"记录盈利: +8.00")
    rm.record_trade_result(12.00)
    print(f"记录盈利: +12.00")

    print_status(rm, "更新后: ")
    print(f"最大连胜={rm.metrics.max_consecutive_wins}")

    # 验证相对变化
    assert rm.metrics.total_trades == initial_total + 2, f"总交易数应增加2"
    assert rm.metrics.winning_trades == initial_wins + 2, f"盈利交易数应增加2"
    assert rm.metrics.consecutive_wins == 2, "连胜应为2"
    assert rm.metrics.consecutive_losses == 0, "连亏应为0"
    assert rm.metrics.max_consecutive_wins >= 2, "最大连胜应>=2"

    print("✅ 测试通过")
    return rm


def test_consecutive_losses(rm):
    """测试连续亏损统计"""
    print("\n测试4: 连续亏损统计")

    # 记录初始状态
    initial_total = rm.metrics.total_trades
    initial_losses = rm.metrics.losing_trades

    # 记录连续亏损
    rm.record_trade_result(-3.00)
    print(f"记录亏损: -3.00")
    rm.record_trade_result(-4.50)
    print(f"记录亏损: -4.50")
    rm.record_trade_result(-2.00)
    print(f"记录亏损: -2.00")

    print_status(rm, "更新后: ")
    print(f"最大连亏={rm.metrics.max_consecutive_losses}")

    # 验证相对变化
    assert rm.metrics.total_trades == initial_total + 3, f"总交易数应增加3"
    assert rm.metrics.losing_trades == initial_losses + 3, f"亏损交易数应增加3"
    assert rm.metrics.consecutive_wins == 0, "连胜应为0"
    assert rm.metrics.consecutive_losses == 3, "连亏应为3"
    assert rm.metrics.max_consecutive_losses >= 3, "最大连亏应>=3"

    print("✅ 测试通过")
    return rm


def test_average_pnl(rm):
    """测试平均盈亏计算"""
    print("\n测试5: 平均盈亏计算")

    print(f"平均盈利: {rm.metrics.avg_win:.2f}")
    print(f"平均亏损: {rm.metrics.avg_loss:.2f}")
    print(f"盈亏比: {rm.metrics.profit_factor:.2f}")

    # 验证基本逻辑
    if rm.metrics.winning_trades > 0:
        assert rm.metrics.avg_win > 0, f"有盈利交易时，平均盈利应>0，实际为{rm.metrics.avg_win}"

    if rm.metrics.losing_trades > 0:
        assert rm.metrics.avg_loss < 0, f"有亏损交易时，平均亏损应<0，实际为{rm.metrics.avg_loss}"

    if rm.metrics.winning_trades > 0 and rm.metrics.losing_trades > 0:
        assert rm.metrics.profit_factor > 0, "有盈利和亏损时，盈亏比应>0"

    print("✅ 测试通过")
    return rm


def test_kelly_calculation(rm):
    """测试Kelly公式计算"""
    print("\n测试6: Kelly公式计算")

    # 记录初始交易数
    initial_total = rm.metrics.total_trades

    # 添加更多交易以确保有足够的数据计算Kelly
    # Kelly计算需要至少10笔交易
    trades_needed = max(0, 10 - initial_total)
    if trades_needed > 0:
        print(f"添加{trades_needed}笔交易以满足Kelly计算要求")
        for i in range(trades_needed):
            rm.record_trade_result(5.00)  # 添加盈利交易

    print(f"总交易数: {rm.metrics.total_trades}")
    print(f"胜率: {rm.metrics.win_rate:.1%}")
    print(f"Kelly分数: {rm.metrics.kelly_fraction:.2%}")

    # 验证
    assert rm.metrics.total_trades >= 10, f"总交易数应>=10，实际为{rm.metrics.total_trades}"
    assert 0 <= rm.metrics.kelly_fraction <= 0.25, f"Kelly分数应在0-25%之间，实际为{rm.metrics.kelly_fraction:.2%}"

    print("✅ 测试通过")
    return rm


def test_daily_stats(rm):
    """测试日内统计"""
    print("\n测试7: 日内统计")

    print(f"日内交易: {rm.daily_trades}")
    print(f"日内盈亏: {rm.daily_pnl:.2f}")
    print(f"日内亏损: {rm.daily_loss:.2f}")

    # 验证日内盈亏已更新（daily_trades在开仓时更新，这里只测试record_trade_result的功能）
    assert rm.daily_pnl != 0, "日内盈亏应已更新"
    assert rm.daily_loss != 0, "日内亏损应已更新"

    # 重置日内统计
    rm.reset_daily_stats()
    print("重置日内统计后:")
    print(f"日内交易: {rm.daily_trades}")
    print(f"日内盈亏: {rm.daily_pnl:.2f}")
    print(f"日内亏损: {rm.daily_loss:.2f}")

    assert rm.daily_trades == 0, "重置后日内交易数应为0"
    assert rm.daily_pnl == 0, "重置后日内盈亏应为0"
    assert rm.daily_loss == 0, "重置后日内亏损应为0"

    print("✅ 测试通过")


def test_trade_history(rm):
    """测试交易历史记录"""
    print("\n测试8: 交易历史记录")

    print(f"历史记录数: {len(rm.trade_history)}")

    # 验证
    assert len(rm.trade_history) > 0, "应有交易历史记录"

    # 检查最后一条记录
    last_trade = rm.trade_history[-1]
    assert 'time' in last_trade, "记录应包含时间"
    assert 'pnl' in last_trade, "记录应包含盈亏"

    print(f"最后一笔交易: {last_trade}")
    print("✅ 测试通过")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("测试 RiskManager.record_trade_result 方法")
    print("=" * 60)

    try:
        # 按顺序运行测试
        rm = test_record_profit()
        rm = test_record_loss(rm)
        rm = test_consecutive_wins(rm)
        rm = test_consecutive_losses(rm)
        rm = test_average_pnl(rm)
        rm = test_kelly_calculation(rm)
        test_daily_stats(rm)
        test_trade_history(rm)

        print("\n" + "=" * 60)
        print("所有测试通过! ✅")
        print("=" * 60)

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
    sys.exit(main())
