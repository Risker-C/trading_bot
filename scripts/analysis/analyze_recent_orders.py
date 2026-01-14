#!/usr/bin/env python3
"""
分析最近的开单情况
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DB_PATH = config.DB_PATH


def analyze_recent_orders(days=7):
    """分析最近N天的开单情况"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 计算时间范围
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    print("=" * 80)
    print(f"📊 最近 {days} 天开单情况分析")
    print("=" * 80)
    print(f"分析时间范围: {start_date} 至今")
    print("=" * 80)

    # 1. 查询开单总数
    cursor.execute("""
        SELECT COUNT(*) FROM trades
        WHERE action = 'open' AND created_at >= ?
    """, (start_date,))
    total_opens = cursor.fetchone()[0]

    print(f"\n📈 开单总数: {total_opens}")

    if total_opens == 0:
        print("\n⚠️  最近没有开单记录")
        conn.close()
        return

    # 2. 按方向统计
    cursor.execute("""
        SELECT side, COUNT(*) as count
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        GROUP BY side
    """, (start_date,))

    print("\n📊 开单方向分布:")
    for row in cursor.fetchall():
        side, count = row
        percentage = (count / total_opens) * 100
        print(f"  {side.upper()}: {count} 单 ({percentage:.1f}%)")

    # 3. 按状态统计
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        GROUP BY status
    """, (start_date,))

    print("\n📋 开单状态分布:")
    for row in cursor.fetchall():
        status, count = row
        percentage = (count / total_opens) * 100
        print(f"  {status}: {count} 单 ({percentage:.1f}%)")

    # 4. 按交易对统计
    cursor.execute("""
        SELECT symbol, COUNT(*) as count
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        GROUP BY symbol
        ORDER BY count DESC
    """, (start_date,))

    print("\n💱 开单交易对分布:")
    for row in cursor.fetchall():
        symbol, count = row
        percentage = (count / total_opens) * 100
        print(f"  {symbol}: {count} 单 ({percentage:.1f}%)")

    # 5. 按策略统计
    cursor.execute("""
        SELECT strategy, COUNT(*) as count
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        GROUP BY strategy
        ORDER BY count DESC
    """, (start_date,))

    print("\n🎯 开单策略分布:")
    for row in cursor.fetchall():
        strategy, count = row
        percentage = (count / total_opens) * 100
        print(f"  {strategy}: {count} 单 ({percentage:.1f}%)")

    # 6. 每日开单统计
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """, (start_date,))

    print("\n📅 每日开单统计:")
    daily_data = cursor.fetchall()
    for row in daily_data:
        date, count = row
        print(f"  {date}: {count} 单")

    # 7. 最近10笔开单详情
    cursor.execute("""
        SELECT
            created_at,
            symbol,
            side,
            amount,
            price,
            value_usdt,
            strategy,
            reason,
            status
        FROM trades
        WHERE action = 'open' AND created_at >= ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (start_date,))

    print("\n📝 最近10笔开单详情:")
    print("-" * 80)
    recent_orders = cursor.fetchall()
    for order in recent_orders:
        created_at, symbol, side, amount, price, value_usdt, strategy, reason, status = order
        print(f"\n时间: {created_at}")
        print(f"交易对: {symbol} | 方向: {side.upper()} | 数量: {amount:.6f}")
        print(f"价格: ${price:.2f} | 价值: ${value_usdt:.2f}")
        print(f"策略: {strategy} | 状态: {status}")
        if reason:
            print(f"原因: {reason}")

    # 8. 统计已平仓订单的盈亏情况
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
            AVG(pnl) as avg_pnl,
            SUM(pnl) as total_pnl,
            MAX(pnl) as max_pnl,
            MIN(pnl) as min_pnl
        FROM trades
        WHERE action = 'close' AND created_at >= ? AND pnl IS NOT NULL
    """, (start_date,))

    result = cursor.fetchone()
    if result and result[0] > 0:
        total_closed, wins, losses, avg_pnl, total_pnl, max_pnl, min_pnl = result
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        print("\n" + "=" * 80)
        print("💰 已平仓订单盈亏统计:")
        print("-" * 80)
        print(f"平仓总数: {total_closed} 单")
        print(f"盈利单数: {wins} 单 | 亏损单数: {losses} 单")
        print(f"胜率: {win_rate:.1f}%")
        print(f"总盈亏: ${total_pnl:.2f}")
        print(f"平均盈亏: ${avg_pnl:.2f}")
        print(f"最大盈利: ${max_pnl:.2f}")
        print(f"最大亏损: ${min_pnl:.2f}")

    conn.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    # 默认分析最近7天，可以通过命令行参数修改
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    analyze_recent_orders(days)
