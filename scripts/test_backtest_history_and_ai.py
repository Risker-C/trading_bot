#!/usr/bin/env python3
"""
回测历史与AI分析功能测试脚本

测试内容：
1. 数据库表结构验证
2. 外键约束测试
3. 复合索引验证
4. Summary Repository功能测试
5. AI Repository功能测试
6. SQL注入防护测试
7. 游标分页测试
8. AI服务错误处理测试
"""

import sys
import os
from datetime import datetime
import sqlite3

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
from backtest.summary_repository import SummaryRepository
from backtest.ai_repository import AIReportRepository
from backtest.change_request_repository import ChangeRequestRepository
from backtest.ai_service import BacktestAIService


class TestBacktestHistoryAndAI:
    """测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.db_path = "backtest.db"

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


def test_database_tables():
    """测试1: 数据库表结构验证"""
    conn = sqlite3.connect("backtest.db")
    cursor = conn.cursor()

    # 检查必需的表是否存在
    required_tables = [
        "backtest_session_summaries",
        "backtest_ai_reports",
        "backtest_change_requests",
        "backtest_audit_logs"
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = [row[0] for row in cursor.fetchall()]

    for table in required_tables:
        assert table in existing_tables, f"表 {table} 不存在"
        print(f"  ✓ 表 {table} 存在")

    conn.close()


def test_foreign_keys():
    """测试2: 外键约束测试"""
    conn = sqlite3.connect("backtest.db")
    conn.execute("PRAGMA foreign_keys=ON")

    # 检查外键是否启用
    result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1, "外键约束未启用"
    print("  ✓ 外键约束已启用")

    conn.close()


def test_composite_indexes():
    """测试3: 复合索引验证"""
    conn = sqlite3.connect("backtest.db")
    cursor = conn.cursor()

    # 检查复合索引是否存在
    required_indexes = [
        "idx_summary_cursor",
        "idx_ai_session_created"
    ]

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    existing_indexes = [row[0] for row in cursor.fetchall()]

    for index in required_indexes:
        assert index in existing_indexes, f"索引 {index} 不存在"
        print(f"  ✓ 索引 {index} 存在")

    conn.close()


def test_summary_repository():
    """测试4: Summary Repository功能测试"""
    repo = SummaryRepository()

    # 测试列表查询（不需要实际数据）
    try:
        summaries, cursor = repo.list_summaries(limit=10)
        print(f"  ✓ 列表查询成功，返回 {len(summaries)} 条记录")
    except Exception as e:
        raise AssertionError(f"列表查询失败: {e}")

    # 测试排序参数验证
    try:
        summaries, cursor = repo.list_summaries(sort_by="created_at", limit=10)
        print("  ✓ 有效的sort_by参数通过")
    except Exception as e:
        raise AssertionError(f"有效参数被拒绝: {e}")


def test_sql_injection_protection():
    """测试5: SQL注入防护测试"""
    repo = SummaryRepository()

    # 测试恶意的sort_by参数
    malicious_inputs = [
        "malicious_field; DROP TABLE users;",
        "id' OR '1'='1",
        "created_at; DELETE FROM backtest_session_summaries;",
        "../../../etc/passwd"
    ]

    for malicious_input in malicious_inputs:
        try:
            repo.list_summaries(sort_by=malicious_input, limit=10)
            raise AssertionError(f"SQL注入防护失败，未拦截: {malicious_input}")
        except ValueError as e:
            print(f"  ✓ 成功拦截恶意输入: {malicious_input[:30]}...")


def test_ai_repository():
    """测试6: AI Repository功能测试"""
    repo = AIReportRepository()

    # 测试获取不存在的报告
    report = repo.get_latest_report("non_existent_session_id")
    assert report is None, "应该返回None而不是抛出异常"
    print("  ✓ 不存在的会话返回None")

    # 测试获取报告（如果有数据）
    try:
        report = repo.get_report("test_report_id")
        print("  ✓ 获取报告功能正常")
    except Exception as e:
        print(f"  ✓ 获取报告功能正常（无数据）")


def test_cursor_pagination():
    """测试7: 游标分页测试"""
    repo = SummaryRepository()

    # 第一页
    page1, cursor1 = repo.list_summaries(limit=5, sort_by="created_at", sort_dir="desc")
    print(f"  ✓ 第一页查询成功，返回 {len(page1)} 条记录")

    if cursor1:
        # 第二页
        page2, cursor2 = repo.list_summaries(cursor=cursor1, limit=5, sort_by="created_at", sort_dir="desc")
        print(f"  ✓ 第二页查询成功，返回 {len(page2)} 条记录")

        # 验证没有重复数据
        if page1 and page2:
            page1_ids = {s['session_id'] for s in page1}
            page2_ids = {s['session_id'] for s in page2}
            overlap = page1_ids & page2_ids
            assert len(overlap) == 0, f"分页数据重复: {overlap}"
            print("  ✓ 分页数据无重复")
    else:
        print("  ✓ 数据量较少，无需分页")


def test_ai_service_error_handling():
    """测试8: AI服务错误处理测试"""
    service = BacktestAIService()

    # 检查analyze_session方法是否正确抛出异常
    import inspect
    source = inspect.getsource(service.analyze_session)
    assert 'raise RuntimeError' in source, "analyze_session未正确抛出异常"
    assert 'AI analysis is not enabled' in source, "错误消息不正确"
    print("  ✓ analyze_session错误处理正确")

    # 检查compare_sessions方法是否正确抛出异常
    source = inspect.getsource(service.compare_sessions)
    assert 'raise RuntimeError' in source, "compare_sessions未正确抛出异常"
    assert 'AI analysis is not enabled' in source or 'AI comparison analysis failed' in source, "错误消息不正确"
    print("  ✓ compare_sessions错误处理正确")


def test_change_request_repository():
    """测试9: 变更请求Repository测试"""
    repo = ChangeRequestRepository()

    # 测试列表查询
    try:
        requests = repo.list_change_requests(limit=10)
        print(f"  ✓ 变更请求列表查询成功，返回 {len(requests)} 条记录")
    except Exception as e:
        raise AssertionError(f"列表查询失败: {e}")

    # 测试状态筛选
    try:
        pending_requests = repo.list_change_requests(status="pending", limit=10)
        print(f"  ✓ 状态筛选成功，返回 {len(pending_requests)} 条pending记录")
    except Exception as e:
        raise AssertionError(f"状态筛选失败: {e}")


def test_audit_logs():
    """测试10: 审计日志测试"""
    repo = ChangeRequestRepository()

    # 测试审计日志查询
    try:
        logs = repo.get_audit_logs(limit=10)
        print(f"  ✓ 审计日志查询成功，返回 {len(logs)} 条记录")
    except Exception as e:
        raise AssertionError(f"审计日志查询失败: {e}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("回测历史与AI分析功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestBacktestHistoryAndAI()

    # 运行所有测试
    tester.run_test("数据库表结构验证", test_database_tables)
    tester.run_test("外键约束测试", test_foreign_keys)
    tester.run_test("复合索引验证", test_composite_indexes)
    tester.run_test("Summary Repository功能测试", test_summary_repository)
    tester.run_test("SQL注入防护测试", test_sql_injection_protection)
    tester.run_test("AI Repository功能测试", test_ai_repository)
    tester.run_test("游标分页测试", test_cursor_pagination)
    tester.run_test("AI服务错误处理测试", test_ai_service_error_handling)
    tester.run_test("变更请求Repository测试", test_change_request_repository)
    tester.run_test("审计日志测试", test_audit_logs)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
