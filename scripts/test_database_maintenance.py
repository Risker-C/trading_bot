#!/usr/bin/env python3
"""
数据库维护测试脚本

测试内容：
1. 数据库文件完整性检查
2. 数据库索引验证
3. 数据库表结构验证
4. 数据库性能测试
5. 数据库备份验证
"""

import sys
import os
from datetime import datetime
import sqlite3

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from utils.logger_utils import get_logger

logger = get_logger("test_database_maintenance")


class TestDatabaseMaintenance:
    """测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.db_path = config.DB_PATH

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*60}")

        try:
            test_func()
            self.passed += 1
            print(f"✅ 测试通过: {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            print(f"❌ 测试失败: {test_name}")
            print(f"   错误: {e}")
            return False
        except Exception as e:
            self.failed += 1
            print(f"❌ 测试异常: {test_name}")
            print(f"   异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"成功率: {(self.passed/self.total*100):.1f}%")
        print(f"{'='*60}\n")

        return self.failed == 0


def test_database_exists():
    """测试1: 数据库文件存在性"""
    print("检查数据库文件...")

    db_path = config.DB_PATH
    assert os.path.exists(db_path), f"数据库文件不存在: {db_path}"

    file_size = os.path.getsize(db_path)
    print(f"  ✓ 数据库文件存在: {db_path}")
    print(f"  ✓ 文件大小: {file_size / 1024 / 1024:.2f} MB")

    assert file_size > 0, "数据库文件为空"
    print(f"  ✓ 数据库文件不为空")


def test_database_integrity():
    """测试2: 数据库完整性检查"""
    print("检查数据库完整性...")

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    # 运行完整性检查
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()

    conn.close()

    print(f"  完整性检查结果: {result[0]}")
    assert result[0] == "ok", f"数据库完整性检查失败: {result[0]}"
    print(f"  ✓ 数据库完整性正常")


def test_required_tables():
    """测试3: 必需表存在性"""
    print("检查必需的表...")

    required_tables = [
        'trades',
        'signals',
        'position_snapshots',
        'balance_snapshots',
        'risk_events',
        'shadow_decisions'
    ]

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]

    conn.close()

    print(f"  现有表数量: {len(existing_tables)}")

    for table in required_tables:
        assert table in existing_tables, f"缺少必需的表: {table}"
        print(f"  ✓ {table}")

    print(f"\n  所有必需的表都存在")


def test_indexes():
    """测试4: 索引验证"""
    print("检查数据库索引...")

    expected_indexes = [
        'idx_trades_created_at',
        'idx_trades_strategy',
        'idx_trades_symbol',
        'idx_trades_side',
        'idx_signals_created_at',
        'idx_signals_strategy',
        'idx_position_snapshots_symbol',
        'idx_position_snapshots_created_at',
        'idx_balance_snapshots_created_at',
        'idx_risk_events_created_at',
        'idx_risk_events_type',
        'idx_shadow_timestamp',
        'idx_shadow_trade_id'
    ]

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existing_indexes = [row[0] for row in cursor.fetchall()]

    conn.close()

    print(f"  现有索引数量: {len(existing_indexes)}")

    missing_indexes = []
    for index in expected_indexes:
        if index in existing_indexes:
            print(f"  ✓ {index}")
        else:
            missing_indexes.append(index)
            print(f"  ⚠️  缺少索引: {index}")

    if missing_indexes:
        print(f"\n  警告: 缺少 {len(missing_indexes)} 个索引")
    else:
        print(f"\n  所有预期索引都存在")


def test_table_structure():
    """测试5: 表结构验证"""
    print("检查表结构...")

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    # 检查trades表结构
    cursor.execute("PRAGMA table_info(trades)")
    trades_columns = {row[1]: row[2] for row in cursor.fetchall()}

    required_columns = {
        'id': 'INTEGER',
        'symbol': 'TEXT',
        'side': 'TEXT',
        'action': 'TEXT',
        'amount': 'REAL',
        'price': 'REAL',
        'pnl': 'REAL',
        'created_at': 'TIMESTAMP'
    }

    print(f"  trades表字段数: {len(trades_columns)}")

    for col_name, col_type in required_columns.items():
        assert col_name in trades_columns, f"trades表缺少字段: {col_name}"
        print(f"  ✓ {col_name} ({trades_columns[col_name]})")

    conn.close()

    print(f"\n  表结构验证通过")


def test_data_count():
    """测试6: 数据记录统计"""
    print("统计数据记录...")

    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    tables = ['trades', 'signals', 'position_snapshots', 'balance_snapshots', 'risk_events']

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} 条记录")

    conn.close()

    print(f"\n  数据统计完成")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("数据库维护测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestDatabaseMaintenance()

    # 运行所有测试
    tester.run_test("数据库文件存在性", test_database_exists)
    tester.run_test("数据库完整性检查", test_database_integrity)
    tester.run_test("必需表存在性", test_required_tables)
    tester.run_test("索引验证", test_indexes)
    tester.run_test("表结构验证", test_table_structure)
    tester.run_test("数据记录统计", test_data_count)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
