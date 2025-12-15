#!/usr/bin/env python3
"""
数据库迁移脚本：添加 highest_price 和 lowest_price 字段
"""
import sqlite3
import os

DB_PATH = "/root/trading_bot/trading_bot.db"

def migrate():
    """执行数据库迁移"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(position_snapshots)")
        columns = [col[1] for col in cursor.fetchall()]

        print(f"📋 当前 position_snapshots 表字段: {columns}")

        # 添加 highest_price 字段
        if 'highest_price' not in columns:
            print("➕ 添加 highest_price 字段...")
            cursor.execute('''
                ALTER TABLE position_snapshots
                ADD COLUMN highest_price REAL DEFAULT 0
            ''')
            print("✅ highest_price 字段添加成功")
        else:
            print("⏭️  highest_price 字段已存在，跳过")

        # 添加 lowest_price 字段
        if 'lowest_price' not in columns:
            print("➕ 添加 lowest_price 字段...")
            cursor.execute('''
                ALTER TABLE position_snapshots
                ADD COLUMN lowest_price REAL DEFAULT 0
            ''')
            print("✅ lowest_price 字段添加成功")
        else:
            print("⏭️  lowest_price 字段已存在，跳过")

        # 添加 entry_time 字段（持仓开始时间）
        if 'entry_time' not in columns:
            print("➕ 添加 entry_time 字段...")
            cursor.execute('''
                ALTER TABLE position_snapshots
                ADD COLUMN entry_time TIMESTAMP
            ''')
            print("✅ entry_time 字段添加成功")
        else:
            print("⏭️  entry_time 字段已存在，跳过")

        conn.commit()

        # 验证迁移结果
        cursor.execute("PRAGMA table_info(position_snapshots)")
        new_columns = [col[1] for col in cursor.fetchall()]
        print(f"\n📋 迁移后 position_snapshots 表字段: {new_columns}")

        print("\n✅ 数据库迁移完成！")
        return True

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 开始数据库迁移")
    print("=" * 60)
    migrate()
