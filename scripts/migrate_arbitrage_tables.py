#!/usr/bin/env python3
"""
套利引擎数据库表迁移脚本

添加三个表:
1. arbitrage_spreads - 历史价差记录
2. arbitrage_opportunities - 检测到的套利机会
3. arbitrage_trades - 执行的套利交易
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_utils import get_logger, db

logger = get_logger("migrate_arbitrage")


def create_arbitrage_tables():
    """创建套利相关表"""
    conn = db._get_conn()
    cursor = conn.cursor()
    
    try:
        # 1. 创建价差历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_spreads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_a TEXT NOT NULL,
                exchange_b TEXT NOT NULL,
                symbol TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                spread_pct REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_spreads_timestamp 
            ON arbitrage_spreads(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_spreads_exchanges 
            ON arbitrage_spreads(exchange_a, exchange_b)
        """)
        
        logger.info("✅ 创建表: arbitrage_spreads")
        
        # 2. 创建套利机会表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                spread_pct REAL NOT NULL,
                gross_profit REAL NOT NULL,
                net_profit REAL NOT NULL,
                buy_exchange_fee REAL NOT NULL,
                sell_exchange_fee REAL NOT NULL,
                estimated_buy_slippage REAL NOT NULL,
                estimated_sell_slippage REAL NOT NULL,
                buy_orderbook_depth REAL,
                sell_orderbook_depth REAL,
                risk_score REAL,
                timestamp INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_opportunities_timestamp 
            ON arbitrage_opportunities(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_opportunities_net_profit 
            ON arbitrage_opportunities(net_profit DESC)
        """)
        
        logger.info("✅ 创建表: arbitrage_opportunities")
        
        # 3. 创建套利交易表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                buy_order_id TEXT,
                sell_order_id TEXT,
                buy_price REAL,
                sell_price REAL,
                expected_pnl REAL,
                actual_pnl REAL,
                failure_reason TEXT,
                buy_execution_time REAL,
                sell_execution_time REAL,
                total_execution_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                buy_executed_at TIMESTAMP,
                sell_executed_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_trades_created_at 
            ON arbitrage_trades(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_trades_status 
            ON arbitrage_trades(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_arbitrage_trades_exchanges 
            ON arbitrage_trades(buy_exchange, sell_exchange)
        """)
        
        logger.info("✅ 创建表: arbitrage_trades")
        
        conn.commit()
        logger.info("✅ 所有套利表创建成功")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建表失败: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def verify_tables():
    """验证表是否创建成功"""
    conn = db._get_conn()
    cursor = conn.cursor()
    
    try:
        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'arbitrage_%'
            ORDER BY name
        """)
        
        tables = cursor.fetchall()
        
        logger.info(f"找到 {len(tables)} 个套利表:")
        for table in tables:
            logger.info(f"  - {table[0]}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            logger.info(f"    列数: {len(columns)}")
        
        return len(tables) == 3
        
    except Exception as e:
        logger.error(f"验证表失败: {e}")
        return False
        
    finally:
        conn.close()


def main():
    """主函数"""
    print("\n" + "="*60)
    print("套利引擎数据库表迁移")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # 创建表
    success = create_arbitrage_tables()
    
    if not success:
        print("\n❌ 迁移失败")
        sys.exit(1)
    
    # 验证表
    verified = verify_tables()
    
    if not verified:
        print("\n❌ 验证失败")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ 迁移成功完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
