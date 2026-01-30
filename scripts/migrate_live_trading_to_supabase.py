"""
实时交易数据库迁移脚本：SQLite -> Supabase

将 trading_bot.db 中的 8 个表迁移到 Supabase，表名添加 live_ 前缀。
"""
import os
import sys
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.adapters.storage.supabase_client import get_supabase_client
from utils.logger_utils import get_logger

_logger = get_logger("migration")


class LiveTradingMigration:
    """实时交易数据迁移器"""

    # 表映射：SQLite -> Supabase
    TABLE_MAPPING = {
        "trades": "live_trades",
        "signals": "live_signals",
        "position_snapshots": "live_position_snapshots",
        "balance_snapshots": "live_balance_snapshots",
        "equity_curve": "live_equity_curve",
        "risk_events": "live_risk_events",
        "daily_stats": "live_daily_stats",
        "risk_metrics": "live_risk_metrics"
    }

    def __init__(self, sqlite_db_path: str = "trading_bot.db"):
        self.sqlite_db_path = sqlite_db_path
        self.supabase_client = get_supabase_client()
        self.stats = {table: {"migrated": 0, "failed": 0} for table in self.TABLE_MAPPING.keys()}

    def _get_sqlite_conn(self):
        """获取 SQLite 连接"""
        if not os.path.exists(self.sqlite_db_path):
            raise FileNotFoundError(f"SQLite database not found: {self.sqlite_db_path}")
        return sqlite3.connect(self.sqlite_db_path)

    def _convert_timestamp_to_ms(self, timestamp_str: str) -> int:
        """将 SQLite TIMESTAMP 字符串转换为毫秒时间戳"""
        if not timestamp_str:
            return int(datetime.now().timestamp() * 1000)
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except ValueError:
            try:
                dt = datetime.fromisoformat(timestamp_str)
                return int(dt.timestamp() * 1000)
            except ValueError:
                _logger.warning("Failed to parse timestamp: %s, using current time", timestamp_str)
                return int(datetime.now().timestamp() * 1000)

    def _prepare_record(self, table_name: str, columns: List[str], row: tuple) -> Dict[str, Any]:
        """准备单条记录（转换类型）"""
        record = dict(zip(columns, row))

        # 移除 SQLite 的 id（Supabase 会自动生成）
        if "id" in record:
            del record["id"]

        # 转换 created_at 为毫秒时间戳
        if "created_at" in record and record["created_at"]:
            record["created_at"] = self._convert_timestamp_to_ms(record["created_at"])

        # 转换 filled_time 为 timestamptz（如果存在）
        if "filled_time" in record and record["filled_time"]:
            try:
                dt = datetime.fromisoformat(record["filled_time"])
                record["filled_time"] = dt.isoformat()
            except (ValueError, TypeError):
                record["filled_time"] = None

        # 转换 entry_time 为毫秒时间戳（如果存在且为字符串）
        if "entry_time" in record and record["entry_time"]:
            if isinstance(record["entry_time"], str):
                record["entry_time"] = self._convert_timestamp_to_ms(record["entry_time"])

        # 处理 signals 表的 indicators 字段（JSON 字符串 -> dict）
        if table_name == "signals" and "indicators" in record:
            if isinstance(record["indicators"], str):
                try:
                    record["indicators"] = json.loads(record["indicators"])
                except (json.JSONDecodeError, TypeError):
                    record["indicators"] = {}

        return record

    def _check_supabase_existing_data(self, supabase_table: str) -> int:
        """检查 Supabase 表中已有数据量"""
        try:
            result = (
                self.supabase_client.table(supabase_table)
                .select("id", count="exact")
                .execute()
            )
            count = result.count if hasattr(result, 'count') else len(result.data or [])
            return count
        except Exception as e:
            _logger.warning("Failed to check existing data in %s: %s", supabase_table, e)
            return 0

    def _clear_supabase_table(self, supabase_table: str) -> bool:
        """清空 Supabase 表（用于重新迁移）"""
        try:
            _logger.warning("Clearing all data in %s...", supabase_table)
            # Supabase 不支持 TRUNCATE，需要删除所有行
            # 使用 RPC 或直接 SQL 更高效，这里使用批量删除
            result = self.supabase_client.table(supabase_table).select("id").execute()
            if result.data:
                ids = [row["id"] for row in result.data]
                # 分批删除
                batch_size = 1000
                for i in range(0, len(ids), batch_size):
                    batch_ids = ids[i:i + batch_size]
                    self.supabase_client.table(supabase_table).delete().in_("id", batch_ids).execute()
                _logger.info("Cleared %d rows from %s", len(ids), supabase_table)
            return True
        except Exception as e:
            _logger.error("Failed to clear table %s: %s", supabase_table, e)
            return False

    def migrate_table(self, sqlite_table: str, chunk_size: int = 500, skip_if_exists: bool = True) -> bool:
        """
        迁移单个表

        Args:
            sqlite_table: SQLite 表名
            chunk_size: 批量插入大小
            skip_if_exists: 如果 Supabase 表已有数据，是否跳过迁移（防止重复）
        """
        supabase_table = self.TABLE_MAPPING[sqlite_table]
        _logger.info("Migrating %s -> %s", sqlite_table, supabase_table)

        try:
            # 检查 Supabase 表是否已有数据
            existing_count = self._check_supabase_existing_data(supabase_table)
            if existing_count > 0:
                if skip_if_exists:
                    _logger.warning("⚠️ Table %s already has %d rows, skipping migration to prevent duplicates",
                                    supabase_table, existing_count)
                    _logger.warning("   Use --force to clear and re-migrate")
                    return False
                else:
                    _logger.warning("⚠️ Table %s has %d existing rows, will be cleared before migration",
                                    supabase_table, existing_count)
                    if not self._clear_supabase_table(supabase_table):
                        _logger.error("Failed to clear table, aborting migration")
                        return False

            conn = self._get_sqlite_conn()
            cursor = conn.cursor()

            # 获取总行数
            cursor.execute(f"SELECT COUNT(*) FROM {sqlite_table}")
            total_rows = cursor.fetchone()[0]

            if total_rows == 0:
                _logger.info("Table %s is empty, skipping", sqlite_table)
                conn.close()
                return True

            _logger.info("Total rows to migrate: %d", total_rows)

            # 读取所有数据
            cursor.execute(f"SELECT * FROM {sqlite_table}")
            columns = [desc[0] for desc in cursor.description]

            # 分批迁移
            migrated = 0
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break

                # 转换记录
                records = [self._prepare_record(sqlite_table, columns, row) for row in rows]

                # 批量插入 Supabase
                try:
                    result = self.supabase_client.table(supabase_table).insert(records).execute()
                    batch_count = len(result.data) if result.data else 0
                    migrated += batch_count
                    self.stats[sqlite_table]["migrated"] += batch_count
                    _logger.info("Migrated %d/%d rows", migrated, total_rows)
                except Exception as e:
                    _logger.error("Failed to insert batch: %s", e)
                    self.stats[sqlite_table]["failed"] += len(records)
                    # 继续迁移下一批

            conn.close()

            # 验证行数
            supabase_result = (
                self.supabase_client.table(supabase_table)
                .select("id", count="exact")
                .execute()
            )
            supabase_count = supabase_result.count if hasattr(supabase_result, 'count') else len(supabase_result.data or [])

            if supabase_count == total_rows:
                _logger.info("✅ Migration successful: %d rows", supabase_count)
                return True
            else:
                _logger.warning("⚠️ Row count mismatch: SQLite=%d, Supabase=%d", total_rows, supabase_count)
                return False

        except Exception as e:
            _logger.error("Failed to migrate table %s: %s", sqlite_table, e)
            return False

    def backup_sqlite_db(self):
        """备份 SQLite 数据库"""
        if not os.path.exists(self.sqlite_db_path):
            _logger.warning("SQLite database not found, skipping backup")
            return None

        backup_path = f"{self.sqlite_db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            import shutil
            shutil.copy2(self.sqlite_db_path, backup_path)
            _logger.info("✅ Backup created: %s", backup_path)
            return backup_path
        except Exception as e:
            _logger.error("Failed to create backup: %s", e)
            return None

    def run_migration(self, tables: List[str] = None, force: bool = False):
        """
        运行完整迁移

        Args:
            tables: 要迁移的表列表（None 表示全部）
            force: 是否强制清空并重新迁移（即使表中已有数据）
        """
        _logger.info("=" * 60)
        _logger.info("Live Trading Database Migration: SQLite -> Supabase")
        _logger.info("=" * 60)

        # 备份数据库
        backup_path = self.backup_sqlite_db()
        if not backup_path:
            _logger.warning("⚠️ Proceeding without backup")

        # 选择要迁移的表
        tables_to_migrate = tables or list(self.TABLE_MAPPING.keys())

        # 先检查所有表的数据量
        _logger.info("=" * 60)
        _logger.info("Pre-migration Check")
        _logger.info("=" * 60)

        conn = self._get_sqlite_conn()
        cursor = conn.cursor()

        for table in tables_to_migrate:
            if table not in self.TABLE_MAPPING:
                continue

            # SQLite 数据量
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = cursor.fetchone()[0]

            # Supabase 数据量
            supabase_table = self.TABLE_MAPPING[table]
            supabase_count = self._check_supabase_existing_data(supabase_table)

            _logger.info("%s: SQLite=%d, Supabase=%d", table, sqlite_count, supabase_count)

            if supabase_count > 0 and not force:
                _logger.warning("⚠️ %s already has data in Supabase, will skip to prevent duplicates", table)

        conn.close()

        # 如果不是强制模式且有表已有数据，询问用户
        if not force:
            _logger.info("=" * 60)
            _logger.info("Migration will skip tables with existing data to prevent duplicates")
            _logger.info("Use --force to clear and re-migrate all tables")
            _logger.info("=" * 60)

        # 迁移每个表
        success_count = 0
        for table in tables_to_migrate:
            if table not in self.TABLE_MAPPING:
                _logger.warning("Unknown table: %s, skipping", table)
                continue

            if self.migrate_table(table, skip_if_exists=not force):
                success_count += 1

        # 打印统计信息
        _logger.info("=" * 60)
        _logger.info("Migration Summary")
        _logger.info("=" * 60)
        for table, stats in self.stats.items():
            if stats["migrated"] > 0 or stats["failed"] > 0:
                _logger.info("%s: migrated=%d, failed=%d",
                             table, stats["migrated"], stats["failed"])

        _logger.info("=" * 60)
        _logger.info("Total: %d/%d tables migrated successfully",
                     success_count, len(tables_to_migrate))
        _logger.info("=" * 60)

        if backup_path:
            _logger.info("Backup saved at: %s", backup_path)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate live trading data from SQLite to Supabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 安全模式：跳过已有数据的表（推荐）
  python migrate_live_trading_to_supabase.py --db trading_bot.db

  # 强制模式：清空并重新迁移所有表（危险！）
  python migrate_live_trading_to_supabase.py --db trading_bot.db --force

  # 仅迁移指定表
  python migrate_live_trading_to_supabase.py --db trading_bot.db --tables signals balance_snapshots

  # 预检查模式：仅查看数据量，不执行迁移
  python migrate_live_trading_to_supabase.py --db trading_bot.db --dry-run
        """
    )
    parser.add_argument("--db", default="trading_bot.db", help="SQLite database path")
    parser.add_argument("--tables", nargs="+", help="Specific tables to migrate (default: all)")
    parser.add_argument("--no-backup", action="store_true", help="Skip database backup")
    parser.add_argument("--force", action="store_true",
                        help="Force clear and re-migrate tables even if they have existing data (DANGEROUS!)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only check data counts, do not perform migration")

    args = parser.parse_args()

    # 创建迁移器
    migrator = LiveTradingMigration(args.db)

    # 如果不需要备份，跳过备份步骤
    if args.no_backup:
        migrator.backup_sqlite_db = lambda: None

    # 如果是 dry-run 模式，只执行预检查
    if args.dry_run:
        _logger.info("=" * 60)
        _logger.info("DRY RUN MODE - Data Count Check Only")
        _logger.info("=" * 60)

        tables_to_check = args.tables or list(migrator.TABLE_MAPPING.keys())

        conn = migrator._get_sqlite_conn()
        cursor = conn.cursor()

        _logger.info("")
        _logger.info("%-25s %10s %10s", "Table", "SQLite", "Supabase")
        _logger.info("-" * 60)

        for table in tables_to_check:
            if table not in migrator.TABLE_MAPPING:
                continue

            # SQLite 数据量
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = cursor.fetchone()[0]

            # Supabase 数据量
            supabase_table = migrator.TABLE_MAPPING[table]
            supabase_count = migrator._check_supabase_existing_data(supabase_table)

            status = ""
            if supabase_count > 0:
                status = " ⚠️ HAS DATA"
            elif sqlite_count > 0:
                status = " ✅ READY"
            else:
                status = " ⊘ EMPTY"

            _logger.info("%-25s %10d %10d%s", table, sqlite_count, supabase_count, status)

        conn.close()

        _logger.info("-" * 60)
        _logger.info("")
        _logger.info("Legend:")
        _logger.info("  ✅ READY     - SQLite has data, Supabase is empty, safe to migrate")
        _logger.info("  ⚠️ HAS DATA  - Supabase already has data, will skip unless --force")
        _logger.info("  ⊘ EMPTY      - Both SQLite and Supabase are empty, nothing to migrate")
        _logger.info("")
        _logger.info("To perform migration: remove --dry-run flag")
        _logger.info("To force re-migrate:  add --force flag (will clear existing data!)")
        return

    # 运行迁移
    migrator.run_migration(args.tables, force=args.force)


if __name__ == "__main__":
    main()
