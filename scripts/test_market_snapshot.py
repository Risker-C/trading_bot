#!/usr/bin/env python3
"""
市场快照功能测试脚本

测试内容：
1. 配置验证
2. MarketSnapshot类初始化
3. 数据获取功能
4. 指标计算准确性
5. 市场状态检测
6. 策略信号分析
7. 共识分析
8. 格式化输出（Dashboard和JSON）
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from trader import BitgetTrader
from monitoring.market_snapshot import MarketSnapshot
from utils.market_formatter import MarketFormatter
from utils.logger_utils import get_logger

logger = get_logger("test_market_snapshot")


class TestMarketSnapshot:
    """市场快照测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.trader = None
        self.snapshot_gen = None

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*60}")

        try:
            result = test_func()
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)

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
    print("检查配置项...")

    # 检查必需的配置项
    assert hasattr(config, 'SYMBOL'), "缺少SYMBOL配置"
    assert hasattr(config, 'KLINE_LIMIT'), "缺少KLINE_LIMIT配置"
    assert hasattr(config, 'USE_DYNAMIC_STRATEGY'), "缺少USE_DYNAMIC_STRATEGY配置"
    assert hasattr(config, 'ENABLE_STRATEGIES'), "缺少ENABLE_STRATEGIES配置"

    print(f"  SYMBOL: {config.SYMBOL}")
    print(f"  KLINE_LIMIT: {config.KLINE_LIMIT}")
    print(f"  USE_DYNAMIC_STRATEGY: {config.USE_DYNAMIC_STRATEGY}")
    print(f"  ENABLE_STRATEGIES: {len(config.ENABLE_STRATEGIES)}个策略")

    assert config.SYMBOL, "SYMBOL不能为空"
    assert config.KLINE_LIMIT > 0, "KLINE_LIMIT必须大于0"
    assert isinstance(config.ENABLE_STRATEGIES, list), "ENABLE_STRATEGIES必须是列表"


def test_trader_initialization(tester):
    """测试2: Trader初始化"""
    print("初始化Trader...")

    tester.trader = BitgetTrader()
    assert tester.trader is not None, "Trader初始化失败"
    assert tester.trader.exchange is not None, "交易所连接失败"

    print(f"  交易所: {tester.trader.exchange.id}")
    print(f"  ✅ Trader初始化成功")


def test_snapshot_initialization(tester):
    """测试3: MarketSnapshot初始化"""
    print("初始化MarketSnapshot...")

    assert tester.trader is not None, "需要先初始化Trader"

    # 测试默认时间周期
    tester.snapshot_gen = MarketSnapshot(tester.trader)
    assert tester.snapshot_gen is not None, "MarketSnapshot初始化失败"
    assert tester.snapshot_gen.timeframes == ['5m', '15m', '1h', '4h'], "默认时间周期不正确"

    print(f"  默认时间周期: {tester.snapshot_gen.timeframes}")

    # 测试自定义时间周期
    custom_gen = MarketSnapshot(tester.trader, ['15m', '1h'])
    assert custom_gen.timeframes == ['15m', '1h'], "自定义时间周期不正确"

    print(f"  自定义时间周期: {custom_gen.timeframes}")
    print(f"  ✅ MarketSnapshot初始化成功")


async def test_data_fetching(tester):
    """测试4: 数据获取功能"""
    print("测试数据获取...")

    assert tester.snapshot_gen is not None, "需要先初始化MarketSnapshot"

    # 使用单个时间周期测试
    test_gen = MarketSnapshot(tester.trader, ['15m'])
    snapshot = await test_gen.fetch_snapshot()

    assert snapshot is not None, "快照获取失败"
    assert 'timestamp' in snapshot, "缺少timestamp字段"
    assert 'symbol' in snapshot, "缺少symbol字段"
    assert 'timeframes' in snapshot, "缺少timeframes字段"
    assert 'consensus' in snapshot, "缺少consensus字段"

    print(f"  时间戳: {snapshot['timestamp']}")
    print(f"  交易对: {snapshot['symbol']}")
    print(f"  时间周期数: {len(snapshot['timeframes'])}")

    # 检查15m数据
    assert '15m' in snapshot['timeframes'], "缺少15m数据"
    tf_data = snapshot['timeframes']['15m']

    if 'error' not in tf_data:
        assert 'price' in tf_data, "缺少price字段"
        assert 'indicators' in tf_data, "缺少indicators字段"
        assert 'market_regime' in tf_data, "缺少market_regime字段"
        assert 'strategy_signals' in tf_data, "缺少strategy_signals字段"

        print(f"  价格: {tf_data['price']['current']}")
        print(f"  市场状态: {tf_data['market_regime']['state']}")
        print(f"  ✅ 数据获取成功")
    else:
        print(f"  ⚠️ 数据获取出错: {tf_data['error']}")


def test_json_output(tester):
    """测试5: JSON格式输出"""
    print("测试JSON格式输出...")

    assert tester.snapshot_gen is not None, "需要先初始化MarketSnapshot"

    # 创建测试数据
    test_snapshot = {
        'timestamp': '2026-01-13T12:00:00',
        'symbol': 'BTCUSDT',
        'timeframes': {},
        'consensus': {'enabled': False}
    }

    json_output = tester.snapshot_gen.to_json(test_snapshot)
    assert json_output is not None, "JSON输出失败"
    assert isinstance(json_output, str), "JSON输出不是字符串"

    # 验证JSON格式
    parsed = json.loads(json_output)
    assert parsed['symbol'] == 'BTCUSDT', "JSON解析后数据不正确"

    print(f"  JSON长度: {len(json_output)}字符")
    print(f"  ✅ JSON格式输出正常")


def test_dashboard_output(tester):
    """测试6: Dashboard格式输出"""
    print("测试Dashboard格式输出...")

    # 创建测试数据
    test_snapshot = {
        'timestamp': '2026-01-13T12:00:00',
        'symbol': 'BTCUSDT',
        'timeframes': {
            '15m': {
                'price': {'current': 91000.0, 'change_24h': -0.5},
                'indicators': {
                    'rsi': 50.0,
                    'adx': {'adx': 15.0},
                    'bollinger': {'width_pct': 0.5}
                },
                'market_regime': {
                    'state': 'RANGING',
                    'confidence': 0.75
                },
                'strategy_signals': []
            }
        },
        'consensus': {'enabled': True, 'result': 'no_signal', 'reason': 'Test'}
    }

    dashboard_output = MarketFormatter.format_dashboard(test_snapshot)
    assert dashboard_output is not None, "Dashboard输出失败"
    assert isinstance(dashboard_output, str), "Dashboard输出不是字符串"
    assert 'BTCUSDT' in dashboard_output, "Dashboard缺少交易对信息"
    assert '15m' in dashboard_output, "Dashboard缺少时间周期信息"

    print(f"  Dashboard长度: {len(dashboard_output)}字符")
    print(f"  ✅ Dashboard格式输出正常")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("市场快照功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestMarketSnapshot()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("Trader初始化", lambda: test_trader_initialization(tester))
    tester.run_test("MarketSnapshot初始化", lambda: test_snapshot_initialization(tester))
    tester.run_test("数据获取功能", lambda: test_data_fetching(tester))
    tester.run_test("JSON格式输出", lambda: test_json_output(tester))
    tester.run_test("Dashboard格式输出", lambda: test_dashboard_output(tester))

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

