#!/usr/bin/env python3
"""
生产环境数据库诊断脚本
用于检查后端 API 是否正确读取数据库
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger_utils import TradeDatabase
from apps.api.services.trade_service import TradeService
from apps.api.services.statistics_service import StatisticsService
import asyncio
import json


async def diagnose():
    """诊断数据库连接和数据"""

    print("=" * 60)
    print("生产环境数据库诊断")
    print("=" * 60)

    # 1. 检查数据库路径
    db = TradeDatabase()
    print(f"\n✓ 数据库文件路径: {db.db_file}")
    print(f"✓ 数据库文件存在: {os.path.exists(db.db_file)}")

    if os.path.exists(db.db_file):
        file_size = os.path.getsize(db.db_file)
        print(f"✓ 数据库文件大小: {file_size / 1024:.2f} KB")

    # 2. 检查交易数据
    print("\n" + "-" * 60)
    print("检查交易数据")
    print("-" * 60)

    trade_service = TradeService(db)
    trades = await trade_service.list_trades(limit=5)

    print(f"✓ 交易记录数量(前5条): {len(trades)}")

    if trades:
        print("\n最近一条交易:")
        trade = trades[0]
        print(f"  - ID: {trade.id}")
        print(f"  - Symbol: {trade.symbol}")
        print(f"  - Side: {trade.side}")
        print(f"  - Price: ${trade.price}")
        print(f"  - Amount: {trade.amount}")
        print(f"  - PnL: ${trade.pnl}")
        print(f"  - Timestamp: {trade.timestamp}")
    else:
        print("⚠️  数据库中没有交易记录!")

    # 3. 检查统计数据
    print("\n" + "-" * 60)
    print("检查统计数据")
    print("-" * 60)

    stats_service = StatisticsService(db)
    daily_stats = stats_service.get_daily_statistics()

    print("\n每日统计数据:")
    print(json.dumps(daily_stats, indent=2, ensure_ascii=False))

    # 4. 检查字段映射
    print("\n" + "-" * 60)
    print("前端期望的字段检查")
    print("-" * 60)

    expected_fields = [
        'total_pnl',
        'today_profit',  # 前端期望但后端可能没有
        'win_rate',
        'pnl_trend',     # 前端期望但后端可能没有
        'win_rate_trend', # 前端期望但后端可能没有
        'position_status', # 前端期望但后端可能没有
        'pnl_history',   # 前端期望但后端可能没有
    ]

    for field in expected_fields:
        exists = field in daily_stats
        status = "✓" if exists else "✗"
        print(f"{status} {field}: {'存在' if exists else '缺失'}")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose())
