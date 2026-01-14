#!/usr/bin/env python3
"""
分析不同策略的胜率表现
"""

import sqlite3
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.settings import settings as config

DB_PATH = config.DB_PATH


def analyze_strategy_performance():
    """分析每个策略的表现"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 80)
    print("📊 策略胜率分析")
    print("=" * 80)

    # 从signals表获取策略信息，关联trades表获取盈亏
    # 思路：通过时间匹配信号和交易
    cursor.execute("""
        SELECT
            s.strategy,
            s.signal,
            COUNT(DISTINCT s.id) as signal_count
        FROM signals s
        GROUP BY s.strategy, s.signal
        ORDER BY signal_count DESC
    """)

    print("\n📈 信号生成统计:")
    print("-" * 80)
    signal_stats = cursor.fetchall()
    for strategy, signal, count in signal_stats:
        print(f"{strategy:20s} | {signal:10s} | {count:4d} 次")

    # 分析每个策略对应的交易结果
    print("\n" + "=" * 80)
    print("💰 策略交易结果分析")
    print("=" * 80)

    # 获取所有已平仓的交易（直接从close记录获取pnl）
    cursor.execute("""
        SELECT
            created_at,
            side,
            pnl,
            pnl_percent
        FROM trades
        WHERE action = 'close'
        AND pnl IS NOT NULL
        ORDER BY created_at DESC
    """)

    close_trades = cursor.fetchall()
    print(f"\n找到 {len(close_trades)} 笔已平仓交易")

    # 关联信号和交易
    strategy_results = defaultdict(lambda: {
        'total': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl': 0,
        'pnls': [],
        'win_pnls': [],
        'loss_pnls': []
    })

    matched_count = 0
    for trade in close_trades:
        close_time, side, pnl, pnl_percent = trade

        # 查找对应的开仓信号（在平仓前查找最近的反向信号）
        # 如果是close long，则查找之前的long信号
        # 如果是close short，则查找之前的short信号
        signal_side = 'long' if side == 'buy' else 'short'

        cursor.execute("""
            SELECT strategy, signal, reason
            FROM signals
            WHERE signal = ?
            AND created_at < ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (signal_side, close_time))

        signal_info = cursor.fetchone()

        if signal_info:
            strategy, signal, reason = signal_info
            key = f"{strategy}_{signal}"

            strategy_results[key]['total'] += 1
            strategy_results[key]['total_pnl'] += pnl
            strategy_results[key]['pnls'].append(pnl)

            if pnl > 0:
                strategy_results[key]['wins'] += 1
                strategy_results[key]['win_pnls'].append(pnl)
            else:
                strategy_results[key]['losses'] += 1
                strategy_results[key]['loss_pnls'].append(pnl)

            matched_count += 1

    print(f"成功关联 {matched_count} 笔交易到策略")

    # 输出结果
    print("\n策略表现排名:")
    print("-" * 80)
    print(f"{'策略':<30s} | {'交易数':>6s} | {'胜率':>8s} | {'总盈亏':>10s} | {'平均盈亏':>10s}")
    print("-" * 80)

    # 按总盈亏排序
    sorted_strategies = sorted(
        strategy_results.items(),
        key=lambda x: x[1]['total_pnl'],
        reverse=True
    )

    for strategy_key, stats in sorted_strategies:
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            avg_pnl = stats['total_pnl'] / stats['total']

            print(f"{strategy_key:<30s} | {stats['total']:>6d} | {win_rate:>7.1f}% | ${stats['total_pnl']:>9.2f} | ${avg_pnl:>9.2f}")

    # 详细分析每个策略
    print("\n" + "=" * 80)
    print("📊 策略详细分析")
    print("=" * 80)

    for strategy_key, stats in sorted_strategies:
        if stats['total'] > 0:
            win_rate = (stats['wins'] / stats['total']) * 100
            avg_pnl = stats['total_pnl'] / stats['total']
            avg_win = sum(stats['win_pnls']) / len(stats['win_pnls']) if stats['win_pnls'] else 0
            avg_loss = sum(stats['loss_pnls']) / len(stats['loss_pnls']) if stats['loss_pnls'] else 0
            profit_factor = abs(sum(stats['win_pnls']) / sum(stats['loss_pnls'])) if stats['loss_pnls'] and sum(stats['loss_pnls']) != 0 else 0

            print(f"\n{strategy_key}:")
            print(f"  交易数: {stats['total']} | 胜: {stats['wins']} | 负: {stats['losses']}")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  总盈亏: ${stats['total_pnl']:.2f} | 平均: ${avg_pnl:.2f}")
            print(f"  平均盈利: ${avg_win:.2f} | 平均亏损: ${avg_loss:.2f}")
            if profit_factor > 0:
                print(f"  盈亏比: {profit_factor:.2f}")

    conn.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_strategy_performance()
