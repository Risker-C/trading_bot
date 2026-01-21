"""
SQLite to Supabase 数据迁移脚本

使用方法:
    export SUPABASE_URL="https://ooqortvtyswxruzldvjw.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="sb_secret_Wv2wqMOSYu-GlqchGQN5Iw_Lw9w3hUM"
    python scripts/migrate_sqlite_to_supabase.py
"""
import sqlite3
import os
import sys
from typing import List, Dict, Optional
from supabase import create_client, Client

# 依赖顺序(先父表后子表,避免外键约束错误)
MIGRATION_ORDER = [
    # 策略表 (无依赖)
    'strategy_versions',
    'parameter_sets',
    'kline_datasets',
    'backtest_runs',
    'optimization_jobs',
    'optimization_results',
    'backtest_reports',

    # 核心回测表
    'backtest_sessions',
    'backtest_klines',
    'backtest_events',
    'backtest_trades',
    'backtest_positions',
    'backtest_metrics',
    'backtest_equity_curve',

    # 历史与AI表
    'backtest_session_summaries',
    'backtest_ai_reports',
    'backtest_change_requests',
    'backtest_audit_logs',
]


def check_table_exists(sqlite_conn: sqlite3.Connection, table_name: str) -> bool:
    """检查 SQLite 表是否存在"""
    cursor = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    supabase_client: Client,
    table_name: str,
    chunk_size: int = 500,
    bytea_columns: Optional[List[str]] = None
):
    """
    迁移单个表

    Args:
        sqlite_conn: SQLite 连接
        supabase_client: Supabase 客户端
        table_name: 表名
        chunk_size: 批量插入大小
        bytea_columns: BLOB 字段列表(需要转换为 bytea hex)
    """
    bytea_columns = bytea_columns or []

    print(f"📦 迁移 {table_name}...")

    # 检查表是否存在
    if not check_table_exists(sqlite_conn, table_name):
        print(f"  ⚠️  {table_name}: 表不存在,跳过")
        return

    # 从 SQLite 读取所有数据
    cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    if not rows:
        print(f"  ✓ {table_name}: 0 行 (空表)")
        return

    # 转换为字典列表
    records = []
    for row in rows:
        record = dict(zip(columns, row))

        # BLOB 字段转 hex 格式
        for col in bytea_columns:
            if col in record and record[col]:
                # PostgreSQL bytea 格式: '\x' + hex string
                if isinstance(record[col], bytes):
                    record[col] = '\\x' + record[col].hex()

        records.append(record)

    # 批量插入
    total = len(records)
    for i in range(0, total, chunk_size):
        batch = records[i:i+chunk_size]
        try:
            supabase_client.table(table_name).insert(batch).execute()
            print(f"  ✓ 已插入 {min(i+chunk_size, total)}/{total} 行")
        except Exception as e:
            print(f"  ✗ 批次 {i}-{i+len(batch)} 插入失败: {e}")
            # 尝试逐行插入以找出问题
            for idx, record in enumerate(batch):
                try:
                    supabase_client.table(table_name).insert(record).execute()
                except Exception as row_err:
                    print(f"    ✗ 行 {i+idx} 失败: {row_err}")
                    print(f"       数据: {record}")

    print(f"  ✅ {table_name}: {total} 行迁移完成\n")


def validate_migration(
    sqlite_conn: sqlite3.Connection,
    supabase_client: Client,
    table_name: str
) -> bool:
    """
    验证迁移结果

    Returns:
        True if counts match, False otherwise
    """
    # 检查表是否存在
    if not check_table_exists(sqlite_conn, table_name):
        print(f"  ⚠️  {table_name}: SQLite 表不存在,跳过验证")
        return True

    # SQLite 行数
    sqlite_count = sqlite_conn.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]

    # Supabase 行数
    try:
        response = supabase_client.table(table_name).select('*', count='exact').execute()
        supabase_count = response.count if hasattr(response, 'count') else len(response.data)
    except Exception as e:
        print(f"  ✗ {table_name}: Supabase 查询失败 - {e}")
        return False

    # 对比
    if sqlite_count == supabase_count:
        print(f"  ✓ {table_name}: {sqlite_count} 行一致")
        return True
    else:
        print(f"  ✗ {table_name}: 不一致 (SQLite={sqlite_count}, Supabase={supabase_count})")
        return False


def main():
    """主函数"""
    print("=" * 70)
    print("  SQLite → Supabase 数据迁移工具")
    print("=" * 70)
    print()

    # 检查环境变量
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("❌ 错误: 缺少环境变量")
        print("请设置:")
        print("  export SUPABASE_URL='...'")
        print("  export SUPABASE_SERVICE_ROLE_KEY='...'")
        sys.exit(1)

    # 检查 SQLite 数据库文件
    db_path = 'backtest.db'
    if not os.path.exists(db_path):
        print(f"❌ 错误: 找不到 SQLite 数据库文件: {db_path}")
        sys.exit(1)

    print(f"📂 SQLite 数据库: {db_path}")
    print(f"🌐 Supabase URL: {supabase_url}")
    print()

    # 连接 SQLite
    print("🔌 连接 SQLite...")
    sqlite_conn = sqlite3.connect(db_path)
    print("  ✓ SQLite 连接成功\n")

    # 连接 Supabase
    print("🔌 连接 Supabase...")
    try:
        supabase = create_client(supabase_url, supabase_key)
        print("  ✓ Supabase 连接成功\n")
    except Exception as e:
        print(f"  ✗ Supabase 连接失败: {e}")
        sqlite_conn.close()
        sys.exit(1)

    # 开始迁移
    print("=" * 70)
    print("  开始数据迁移")
    print("=" * 70)
    print()

    failed_tables = []

    for table in MIGRATION_ORDER:
        try:
            # K线数据集包含 BLOB 字段
            bytea_cols = ['data'] if table == 'kline_datasets' else []
            migrate_table(sqlite_conn, supabase, table, chunk_size=500, bytea_columns=bytea_cols)
        except Exception as e:
            print(f"  ❌ {table} 迁移失败: {e}\n")
            failed_tables.append(table)

    # 验证迁移结果
    print("=" * 70)
    print("  验证迁移结果")
    print("=" * 70)
    print()

    validation_failed = []

    for table in MIGRATION_ORDER:
        if not validate_migration(sqlite_conn, supabase, table):
            validation_failed.append(table)

    # 关闭连接
    sqlite_conn.close()

    # 汇总报告
    print()
    print("=" * 70)
    print("  迁移完成报告")
    print("=" * 70)
    print()

    if failed_tables:
        print(f"❌ 迁移失败的表 ({len(failed_tables)}):")
        for table in failed_tables:
            print(f"  - {table}")
        print()

    if validation_failed:
        print(f"⚠️  验证失败的表 ({len(validation_failed)}):")
        for table in validation_failed:
            print(f"  - {table}")
        print()

    if not failed_tables and not validation_failed:
        print("✅ 所有表迁移成功！")
        print(f"   共迁移 {len(MIGRATION_ORDER)} 个表")
        print()
        sys.exit(0)
    else:
        print("❌ 迁移过程中遇到问题,请检查上述错误")
        print()
        sys.exit(1)


if __name__ == '__main__':
    main()
