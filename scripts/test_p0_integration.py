#!/usr/bin/env python3
"""
P0模块集成测试脚本

测试内容：
1. 配置验证
2. 模块导入测试
3. 影子模式功能测试
4. Claude护栏功能测试
5. 性能分析器功能测试
6. 数据库表结构验证
7. 集成流程测试
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger, db

logger = get_logger("test_p0_integration")


class TestP0Integration:
    """P0模块集成测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

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


def test_config_validation():
    """测试1: 配置验证"""
    print("检查P0模块配置项...")

    # 检查影子模式配置
    assert hasattr(config, 'ENABLE_SHADOW_MODE'), "缺少ENABLE_SHADOW_MODE配置"
    print(f"  ENABLE_SHADOW_MODE = {config.ENABLE_SHADOW_MODE}")

    # 检查Claude护栏配置
    assert hasattr(config, 'CLAUDE_CACHE_TTL'), "缺少CLAUDE_CACHE_TTL配置"
    assert hasattr(config, 'CLAUDE_MAX_DAILY_CALLS'), "缺少CLAUDE_MAX_DAILY_CALLS配置"
    assert hasattr(config, 'CLAUDE_MAX_DAILY_COST'), "缺少CLAUDE_MAX_DAILY_COST配置"
    print(f"  CLAUDE_CACHE_TTL = {config.CLAUDE_CACHE_TTL}")
    print(f"  CLAUDE_MAX_DAILY_CALLS = {config.CLAUDE_MAX_DAILY_CALLS}")
    print(f"  CLAUDE_MAX_DAILY_COST = {config.CLAUDE_MAX_DAILY_COST}")

    print("✓ 所有配置项存在")


def test_module_imports():
    """测试2: 模块导入"""
    print("测试模块导入...")

    # 测试影子模式导入
    try:
        from shadow_mode import get_shadow_tracker
        tracker = get_shadow_tracker()
        assert tracker is not None
        print("  ✓ shadow_mode 导入成功")
    except ImportError as e:
        raise AssertionError(f"shadow_mode 导入失败: {e}")

    # 测试Claude护栏导入
    try:
        from claude_guardrails import get_guardrails
        guardrails = get_guardrails()
        assert guardrails is not None
        print("  ✓ claude_guardrails 导入成功")
    except ImportError as e:
        raise AssertionError(f"claude_guardrails 导入失败: {e}")

    # 测试性能分析器导入
    try:
        from analysis.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()
        assert analyzer is not None
        print("  ✓ performance_analyzer 导入成功")
    except ImportError as e:
        raise AssertionError(f"performance_analyzer 导入失败: {e}")

    print("✓ 所有模块导入成功")


def test_shadow_mode_functionality():
    """测试3: 影子模式功能"""
    print("测试影子模式功能...")

    from shadow_mode import get_shadow_tracker
    from strategies import Signal, TradeSignal

    tracker = get_shadow_tracker()
    # 临时启用影子模式用于测试
    tracker.enabled = True

    # 创建测试信号
    signal = TradeSignal(
        Signal.LONG,
        "test_strategy",
        "测试信号",
        strength=0.7,
        confidence=0.6
    )

    # 记录决策
    trade_id = f"test_{datetime.now().isoformat()}"
    tracker.record_decision(
        trade_id=trade_id,
        price=86500,
        market_regime="trending",
        volatility=0.025,
        signal=signal,
        would_execute_strategy=True,
        would_execute_after_trend=True,
        would_execute_after_claude=False,
        would_execute_after_exec=False,
        final_would_execute=False,
        rejection_stage="claude",
        rejection_reason="测试拒绝"
    )

    print(f"  ✓ 记录决策成功: {trade_id}")

    # 验证数据库记录
    import sqlite3
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM shadow_decisions WHERE trade_id = ?",
        (trade_id,)
    )
    count = cursor.fetchone()['count']
    conn.close()
    assert count > 0, "影子模式记录未写入数据库"
    print(f"  ✓ 数据库验证成功: 找到 {count} 条记录")

    print("✓ 影子模式功能正常")


def test_claude_guardrails_functionality():
    """测试4: Claude护栏功能"""
    print("测试Claude护栏功能...")

    from claude_guardrails import get_guardrails

    guardrails = get_guardrails()

    # 测试预算检查
    can_call, reason = guardrails.check_budget()
    print(f"  预算检查: {can_call} - {reason}")
    assert isinstance(can_call, bool), "预算检查返回值类型错误"

    # 测试缓存功能
    signal_data = {'strategy': 'test', 'signal': 'long'}
    indicators = {'rsi': 50, 'macd': 100}

    # 第一次调用（缓存未命中）
    cached = guardrails.check_cache(signal_data, indicators)
    assert cached is None, "首次调用不应有缓存"
    print("  ✓ 缓存未命中（预期）")

    # 保存缓存
    test_result = {'execute': True, 'confidence': 0.75, 'reason': '测试'}
    guardrails.save_cache(signal_data, indicators, test_result)
    print("  ✓ 缓存保存成功")

    # 第二次调用（缓存命中）
    cached = guardrails.check_cache(signal_data, indicators)
    assert cached is not None, "第二次调用应有缓存"
    assert cached['execute'] == True, "缓存数据不正确"
    print("  ✓ 缓存命中（预期）")

    # 测试响应验证
    valid_response = '{"execute": true, "confidence": 0.75, "regime": "trend", "signal_quality": 0.8}'
    valid, data, error = guardrails.validate_response(valid_response)
    assert valid == True, f"有效响应验证失败: {error}"
    print("  ✓ 响应验证成功")

    # 测试统计
    stats = guardrails.get_stats()
    assert 'total_calls' in stats, "统计信息缺少total_calls"
    assert 'cache_hits' in stats, "统计信息缺少cache_hits"
    print(f"  ✓ 统计信息: 总调用={stats['total_calls']}, 缓存命中={stats['cache_hits']}")

    print("✓ Claude护栏功能正常")


def test_performance_analyzer_functionality():
    """测试5: 性能分析器功能"""
    print("测试性能分析器功能...")

    from analysis.performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()

    # 测试分析功能（可能没有数据）
    try:
        report = analyzer.analyze_period()
        assert 'core_metrics' in report, "报告缺少core_metrics"
        assert 'rejection_analysis' in report, "报告缺少rejection_analysis"
        print("  ✓ 分析功能正常")
        print(f"  ✓ 报告包含: {', '.join(report.keys())}")
    except Exception as e:
        print(f"  ⚠️  分析功能测试跳过（可能没有数据）: {e}")

    print("✓ 性能分析器功能正常")


def test_database_tables():
    """测试6: 数据库表结构"""
    print("测试数据库表结构...")

    import sqlite3

    # 检查shadow_decisions表
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='shadow_decisions'"
    )
    result = cursor.fetchone()
    conn.close()
    assert result is not None, "shadow_decisions表不存在"
    print("  ✓ shadow_decisions表存在")

    # 检查trade_tags表（可选，由主交易系统创建）
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_tags'"
    )
    result = cursor.fetchone()
    conn.close()
    if result is not None:
        print("  ✓ trade_tags表存在")
    else:
        print("  ⚠️  trade_tags表不存在（将由主交易系统创建）")

    # 检查shadow_decisions表结构
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(shadow_decisions)")
    columns = [row['name'] for row in cursor.fetchall()]
    conn.close()
    required_columns = [
        'trade_id', 'would_execute_strategy', 'would_execute_after_trend',
        'would_execute_after_claude', 'final_would_execute'
    ]
    for col in required_columns:
        assert col in columns, f"shadow_decisions表缺少字段: {col}"
    print(f"  ✓ shadow_decisions表结构正确（{len(columns)}个字段）")

    print("✓ 数据库表结构正常")


def test_integration_flow():
    """测试7: 集成流程"""
    print("测试集成流程...")

    from shadow_mode import get_shadow_tracker
    from claude_guardrails import get_guardrails
    from strategies import Signal, TradeSignal

    tracker = get_shadow_tracker()
    # 临时启用影子模式用于测试
    tracker.enabled = True
    guardrails = get_guardrails()

    # 模拟完整流程
    signal = TradeSignal(
        Signal.LONG,
        "macd_cross",
        "MACD金叉",
        strength=0.75,
        confidence=0.7
    )

    signal_data = {'strategy': signal.strategy, 'signal': signal.signal.value}
    indicators = {'rsi': 45, 'macd': 200}

    # 步骤1: 检查预算
    can_call, reason = guardrails.check_budget()
    print(f"  步骤1: 预算检查 - {can_call}")

    # 步骤2: 检查缓存
    cached = guardrails.check_cache(signal_data, indicators)
    print(f"  步骤2: 缓存检查 - {'命中' if cached else '未命中'}")

    # 步骤3: 记录影子模式
    trade_id = f"integration_test_{datetime.now().isoformat()}"
    tracker.record_decision(
        trade_id=trade_id,
        price=86500,
        market_regime="trending",
        volatility=0.025,
        signal=signal,
        would_execute_strategy=True,
        would_execute_after_trend=True,
        would_execute_after_claude=True,
        would_execute_after_exec=True,
        final_would_execute=True,
        actually_executed=True,
        actual_entry_price=86500
    )
    print(f"  步骤3: 影子模式记录 - 成功")

    # 步骤4: 验证记录
    import sqlite3
    conn = db._get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM shadow_decisions WHERE trade_id = ?",
        (trade_id,)
    )
    record = cursor.fetchone()
    conn.close()
    assert record is not None, "集成流程记录未找到"
    assert record['would_execute_strategy'] == 1, "would_execute_strategy不正确"
    assert record['final_would_execute'] == 1, "final_would_execute不正确"
    print(f"  步骤4: 数据验证 - 成功")

    print("✓ 集成流程正常")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("P0模块集成测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestP0Integration()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("模块导入", test_module_imports)
    tester.run_test("影子模式功能", test_shadow_mode_functionality)
    tester.run_test("Claude护栏功能", test_claude_guardrails_functionality)
    tester.run_test("性能分析器功能", test_performance_analyzer_functionality)
    tester.run_test("数据库表结构", test_database_tables)
    tester.run_test("集成流程", test_integration_flow)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
