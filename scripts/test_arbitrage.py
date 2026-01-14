#!/usr/bin/env python3
"""
套利引擎测试脚本

测试内容：
1. 配置验证
2. 组件初始化
3. 价差监控
4. 机会检测
5. 风险管理
6. 持仓追踪
7. 数据库记录
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings as config
from utils.logger_utils import get_logger, db
from exchange.manager import ExchangeManager

logger = get_logger("test_arbitrage")


class TestArbitrage:
    """套利引擎测试类"""

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
    print("检查套利配置参数...")

    # 检查必需的配置项
    required_configs = [
        'ARBITRAGE_SYMBOL',
        'ARBITRAGE_EXCHANGES',
        'MIN_SPREAD_THRESHOLD',
        'MIN_NET_PROFIT_THRESHOLD',
        'ARBITRAGE_POSITION_SIZE',
    ]

    for config_name in required_configs:
        assert hasattr(config, config_name), f"缺少配置项: {config_name}"
        print(f"  ✓ {config_name} = {getattr(config, config_name)}")

    # 验证配置值的合理性
    assert config.MIN_SPREAD_THRESHOLD > 0, "MIN_SPREAD_THRESHOLD 必须大于0"
    assert config.MIN_NET_PROFIT_THRESHOLD > 0, "MIN_NET_PROFIT_THRESHOLD 必须大于0"
    assert config.ARBITRAGE_POSITION_SIZE > 0, "ARBITRAGE_POSITION_SIZE 必须大于0"
    assert len(config.ARBITRAGE_EXCHANGES) >= 2, "至少需要2个交易所"

    print("配置验证通过")


def test_component_initialization():
    """测试2: 组件初始化"""
    print("初始化套利引擎组件...")

    # 初始化交易所管理器
    exchange_manager = ExchangeManager()
    exchange_manager.initialize()
    print("  ✓ ExchangeManager 初始化成功")

    # 创建套利配置
    arbitrage_config = {
        "symbol": config.ARBITRAGE_SYMBOL,
        "exchanges": config.ARBITRAGE_EXCHANGES,
        "monitor_interval": 1,
        "min_spread_threshold": config.MIN_SPREAD_THRESHOLD,
        "min_net_profit_threshold": config.MIN_NET_PROFIT_THRESHOLD,
        "arbitrage_position_size": config.ARBITRAGE_POSITION_SIZE,
    }

    # 初始化各个组件
    from arbitrage.spread_monitor import SpreadMonitor
    from arbitrage.opportunity_detector import OpportunityDetector
    from arbitrage.arbitrage_risk_manager import ArbitrageRiskManager
    from arbitrage.execution_coordinator import ExecutionCoordinator
    from arbitrage.position_tracker import CrossExchangePositionTracker

    spread_monitor = SpreadMonitor(exchange_manager, arbitrage_config)
    print("  ✓ SpreadMonitor 初始化成功")

    opportunity_detector = OpportunityDetector(exchange_manager, arbitrage_config)
    print("  ✓ OpportunityDetector 初始化成功")

    risk_manager = ArbitrageRiskManager(exchange_manager, arbitrage_config)
    print("  ✓ ArbitrageRiskManager 初始化成功")

    execution_coordinator = ExecutionCoordinator(exchange_manager, arbitrage_config)
    print("  ✓ ExecutionCoordinator 初始化成功")

    position_tracker = CrossExchangePositionTracker(exchange_manager, arbitrage_config)
    print("  ✓ CrossExchangePositionTracker 初始化成功")

    print("所有组件初始化成功")


def test_database_tables():
    """测试3: 数据库表验证"""
    print("验证套利数据库表...")

    conn = db._get_conn()
    cursor = conn.cursor()

    # 检查表是否存在
    required_tables = [
        'arbitrage_spreads',
        'arbitrage_opportunities',
        'arbitrage_trades'
    ]

    for table_name in required_tables:
        cursor.execute(f"""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='{table_name}'
        """)
        result = cursor.fetchone()
        assert result is not None, f"表 {table_name} 不存在"
        print(f"  ✓ 表 {table_name} 存在")

        # 获取表结构
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print(f"    列数: {len(columns)}")

    conn.close()
    print("数据库表验证通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("套利引擎测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestArbitrage()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("组件初始化", test_component_initialization)
    tester.run_test("数据库表验证", test_database_tables)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
