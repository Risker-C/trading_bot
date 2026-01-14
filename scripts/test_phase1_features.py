"""
Phase 1 Features Test Suite
测试错误退避控制器、价格稳定性检测和订单健康监控器
"""
import sys
import os
# 添加父目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time

# 导入待测试模块
from risk.error_backoff_controller import ErrorBackoffController, ErrorType, BackoffState
from risk.execution_filter import ExecutionFilter
from monitoring.order_health_monitor import OrderHealthMonitor
from config.settings import settings as config


class TestErrorBackoffController(unittest.TestCase):
    """测试错误退避控制器"""

    def setUp(self):
        """测试前准备"""
        self.controller = ErrorBackoffController()

    def test_exponential_backoff_calculation(self):
        """测试指数退避计算"""
        exchange = "test_exchange"

        # 第一次错误: 120秒
        self.controller.register_error(exchange, "429", "Rate limit")
        state = self.controller._backoff_states[exchange]
        self.assertEqual(state.error_count, 1)
        self.assertEqual(state.pause_duration_seconds, 120)

        # 第二次错误: 240秒
        time.sleep(0.1)  # 确保时间戳不同
        self.controller.register_error(exchange, "429", "Rate limit")
        state = self.controller._backoff_states[exchange]
        self.assertEqual(state.error_count, 2)
        self.assertEqual(state.pause_duration_seconds, 240)

        # 第三次错误: 480秒
        time.sleep(0.1)
        self.controller.register_error(exchange, "429", "Rate limit")
        state = self.controller._backoff_states[exchange]
        self.assertEqual(state.error_count, 3)
        self.assertEqual(state.pause_duration_seconds, 480)

    def test_error_type_parsing(self):
        """测试错误类型解析"""
        test_cases = [
            ("429", ErrorType.RATE_LIMIT),
            ("21104", ErrorType.INVALID_NONCE),
            ("timeout", ErrorType.TIMEOUT),
            ("network error", ErrorType.NETWORK_ERROR),
            ("unknown", ErrorType.API_ERROR),
        ]

        for error_code, expected_type in test_cases:
            result = self.controller._parse_error_type(error_code)
            self.assertEqual(result, expected_type)

    def test_pause_and_recovery(self):
        """测试暂停和恢复"""
        exchange = "test_exchange"

        # 注册错误
        self.controller.register_error(exchange, "429", "Rate limit")

        # 应该处于暂停状态
        self.assertTrue(self.controller.is_paused(exchange))

        # 手动设置暂停时间为过去
        state = self.controller._backoff_states[exchange]
        state.pause_until = datetime.now() - timedelta(seconds=1)

        # 应该不再暂停
        self.assertFalse(self.controller.is_paused(exchange))

    def test_reset_exchange(self):
        """测试重置交易所状态"""
        exchange = "test_exchange"

        # 注册错误
        self.controller.register_error(exchange, "429", "Rate limit")
        self.assertIn(exchange, self.controller._backoff_states)

        # 重置
        self.controller.reset_exchange(exchange)
        self.assertNotIn(exchange, self.controller._backoff_states)


class TestPriceStabilityDetection(unittest.TestCase):
    """测试价格稳定性检测"""

    def setUp(self):
        """测试前准备"""
        self.filter = ExecutionFilter()
        self.filter.price_stability_enabled = True
        self.filter.price_stability_window = 5.0
        self.filter.price_stability_threshold = 0.5

    def test_price_data_collection(self):
        """测试价格数据收集"""
        # 第一次检查 - 数据不足
        pass_check, reason, volatility = self.filter._check_price_stability(100.0)
        self.assertTrue(pass_check)
        self.assertIn("收集中", reason)

        # 添加更多价格样本
        time.sleep(1.1)
        self.filter._check_price_stability(100.5)
        time.sleep(1.1)
        self.filter._check_price_stability(101.0)

        # 现在应该有足够数据
        self.assertGreater(len(self.filter.price_history), 1)

    def test_stable_price_detection(self):
        """测试稳定价格检测"""
        # 模拟稳定价格（波动<0.5%）
        base_price = 100.0
        for i in range(6):
            price = base_price + (i * 0.04)  # 0.04% 变化
            time.sleep(0.2)
            self.filter._check_price_stability(price)

        # 最后一次检查应该通过
        pass_check, reason, volatility = self.filter._check_price_stability(base_price + 0.2)
        self.assertTrue(pass_check)
        self.assertLess(volatility, 0.5)

    def test_volatile_price_detection(self):
        """测试波动价格检测"""
        # 模拟波动价格（波动>0.5%）
        base_price = 100.0

        # 添加稳定的初始数据
        for i in range(3):
            time.sleep(0.3)
            self.filter._check_price_stability(base_price)

        # 添加大幅波动
        time.sleep(0.3)
        self.filter._check_price_stability(base_price * 1.01)  # +1% 波动

        # 检查应该失败
        pass_check, reason, volatility = self.filter._check_price_stability(base_price * 1.01)
        if len(self.filter.price_history) >= 2:
            # 如果有足够数据，应该检测到波动
            self.assertGreater(volatility, 0.5)


class TestOrderHealthMonitor(unittest.TestCase):
    """测试订单健康监控器"""

    def setUp(self):
        """测试前准备"""
        self.mock_trader = Mock()
        self.mock_trader.exchange = Mock()
        self.monitor = OrderHealthMonitor(self.mock_trader)
        self.monitor.enabled = True

    def test_order_age_calculation(self):
        """测试订单年龄计算"""
        # 创建模拟订单
        timestamp = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
        order = {
            'id': 'test_order_1',
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'status': 'open',
            'timestamp': timestamp,
            'filled': 0,
            'amount': 1.0,
        }

        health_info = self.monitor._check_order_health(order)

        # 验证年龄计算
        self.assertEqual(health_info.order_id, 'test_order_1')
        self.assertGreater(health_info.age_seconds, 14 * 60)  # 至少14分钟
        self.assertLess(health_info.age_seconds, 16 * 60)  # 最多16分钟

    def test_stale_order_detection(self):
        """测试过期订单检测"""
        # 创建过期订单（15分钟前）
        timestamp = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
        order = {
            'id': 'stale_order',
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'status': 'open',
            'timestamp': timestamp,
            'filled': 0,
            'amount': 1.0,
        }

        health_info = self.monitor._check_order_health(order)

        # 应该被标记为过期（阈值10分钟）
        self.assertTrue(health_info.is_stale)

    def test_partial_fill_detection(self):
        """测试部分成交检测"""
        order = {
            'id': 'partial_order',
            'symbol': 'BTCUSDT',
            'side': 'buy',
            'status': 'open',
            'timestamp': int(datetime.now().timestamp() * 1000),
            'filled': 0.5,
            'amount': 1.0,
        }

        health_info = self.monitor._check_order_health(order)

        # 应该被标记为部分成交
        self.assertTrue(health_info.is_partial)

    def test_health_check_with_no_orders(self):
        """测试无订单时的健康检查"""
        self.mock_trader.exchange.fetch_open_orders.return_value = []

        result = self.monitor.check_health()

        self.assertEqual(result.get('open_orders'), 0)

    @patch('time.sleep')
    def test_check_interval_enforcement(self, mock_sleep):
        """测试检查间隔强制"""
        self.monitor.check_interval = 300  # 5分钟
        self.monitor.last_check_time = datetime.now()

        # 立即再次检查应该被跳过
        result = self.monitor.check_health()

        self.assertTrue(result.get('skipped'))


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_error_backoff_integration_with_health_monitor(self):
        """测试错误退避与健康监控器集成"""
        from core.trader import HealthMonitor

        health_monitor = HealthMonitor(exchange_name="test")

        # 模拟API错误
        error = Exception("Rate limit exceeded (429)")
        health_monitor.record_error(error, "429")

        # 应该触发退避
        if health_monitor.backoff_controller:
            self.assertTrue(health_monitor.is_paused())

    def test_execution_filter_integration(self):
        """测试执行过滤器集成"""
        import pandas as pd

        filter = ExecutionFilter()

        # 创建模拟数据
        df = pd.DataFrame({
            'timestamp': [datetime.now()] * 20,
            'open': [100] * 20,
            'high': [101] * 20,
            'low': [99] * 20,
            'close': [100] * 20,
            'volume': [1000] * 20,
        })

        ticker = {'bid': 99.9, 'ask': 100.1, 'last': 100.0}
        indicators = {'volume_ratio': 1.0, 'atr': 0.5}

        # 执行检查
        pass_check, reason, details = filter.check_all(df, 100.0, ticker, indicators)

        # 应该有检查结果
        self.assertIsInstance(pass_check, bool)
        self.assertIsInstance(details, dict)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestErrorBackoffController))
    suite.addTests(loader.loadTestsFromTestCase(TestPriceStabilityDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestOrderHealthMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
