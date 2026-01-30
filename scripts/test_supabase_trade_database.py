"""
Supabase 实时交易数据库测试脚本

测试 SupabaseTradeDatabase 的所有核心功能。
"""
import os
import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_trade_database import SupabaseTradeDatabase
from utils.logger_utils import get_logger

_logger = get_logger("test.supabase_trade_db")


class SupabaseTradeDBTester:
    """Supabase 交易数据库测试器"""

    def __init__(self):
        self.db = SupabaseTradeDatabase()
        self.test_results = []

    def _log_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append((test_name, passed))
        _logger.info("%s - %s %s", status, test_name, f"({message})" if message else "")

    def test_log_trade(self):
        """测试单条交易记录"""
        _logger.info("=" * 60)
        _logger.info("Test: log_trade")
        _logger.info("=" * 60)

        try:
            trade_id = self.db.log_trade(
                symbol="ETHUSDT",
                side="LONG",
                action="OPEN",
                amount=0.1,
                price=2000.0,
                order_id="test_order_001",
                value_usdt=200.0,
                pnl=0,
                pnl_percent=0,
                strategy="test_strategy",
                reason="test",
                status="filled",
                filled_price=2001.0,
                fee=0.12,
                fee_currency="USDT"
            )
            self._log_test("log_trade", trade_id > 0, f"trade_id={trade_id}")
            return trade_id
        except Exception as e:
            self._log_test("log_trade", False, str(e))
            return None

    def test_log_signal(self):
        """测试单条信号记录"""
        _logger.info("=" * 60)
        _logger.info("Test: log_signal")
        _logger.info("=" * 60)

        try:
            signal_id = self.db.log_signal(
                strategy="test_strategy",
                signal="BUY",
                reason="test signal",
                strength=0.8,
                confidence=0.9,
                indicators={"rsi": 45.5, "macd": 0.02}
            )
            self._log_test("log_signal", signal_id > 0, f"signal_id={signal_id}")
            return signal_id
        except Exception as e:
            self._log_test("log_signal", False, str(e))
            return None

    def test_batch_trades(self):
        """测试批量交易写入"""
        _logger.info("=" * 60)
        _logger.info("Test: log_trades_batch")
        _logger.info("=" * 60)

        try:
            trades = [
                {
                    "symbol": "ETHUSDT",
                    "side": "LONG",
                    "action": "OPEN",
                    "amount": 0.1,
                    "price": 2000.0 + i,
                    "order_id": f"batch_order_{i}",
                    "value_usdt": 200.0,
                    "pnl": 0,
                    "pnl_percent": 0,
                    "strategy": "test_batch",
                    "reason": "batch test",
                    "status": "filled"
                }
                for i in range(5)
            ]

            count = self.db.log_trades_batch(trades)
            self._log_test("log_trades_batch", count == 5, f"inserted {count} trades")
            return count
        except Exception as e:
            self._log_test("log_trades_batch", False, str(e))
            return 0

    def test_batch_signals(self):
        """测试批量信号写入"""
        _logger.info("=" * 60)
        _logger.info("Test: log_signals_batch")
        _logger.info("=" * 60)

        try:
            signals = [
                {
                    "strategy": "test_batch",
                    "signal": "BUY" if i % 2 == 0 else "SELL",
                    "reason": f"batch signal {i}",
                    "strength": 0.7 + i * 0.05,
                    "confidence": 0.8,
                    "indicators": {"rsi": 50 + i, "macd": 0.01 * i}
                }
                for i in range(5)
            ]

            count = self.db.log_signals_batch(signals)
            self._log_test("log_signals_batch", count == 5, f"inserted {count} signals")
            return count
        except Exception as e:
            self._log_test("log_signals_batch", False, str(e))
            return 0

    def test_buffered_writes(self):
        """测试缓冲写入"""
        _logger.info("=" * 60)
        _logger.info("Test: buffered writes")
        _logger.info("=" * 60)

        try:
            # 启用批量写入
            import config
            original_value = getattr(config, 'DB_BATCH_WRITES_ENABLED', False)
            config.DB_BATCH_WRITES_ENABLED = True

            # 写入多条记录到缓冲区
            for i in range(3):
                self.db.log_trade_buffered(
                    symbol="ETHUSDT",
                    side="SHORT",
                    action="CLOSE",
                    amount=0.1,
                    price=2100.0 + i,
                    strategy="test_buffered",
                    reason="buffered test"
                )

            # 手动刷新缓冲区
            self.db.flush_buffers(force=True)

            # 恢复原始配置
            config.DB_BATCH_WRITES_ENABLED = original_value

            self._log_test("buffered_writes", True, "flushed 3 trades")
            return True
        except Exception as e:
            self._log_test("buffered_writes", False, str(e))
            return False

    def test_position_snapshot(self):
        """测试持仓快照"""
        _logger.info("=" * 60)
        _logger.info("Test: position snapshot")
        _logger.info("=" * 60)

        try:
            self.db.log_position_snapshot(
                symbol="ETHUSDT",
                side="LONG",
                amount=0.5,
                entry_price=2000.0,
                current_price=2050.0,
                unrealized_pnl=25.0,
                leverage=50,
                highest_price=2060.0,
                lowest_price=1990.0,
                entry_time=str(int(time.time() * 1000))
            )

            # 读取最新快照
            snapshot = self.db.get_latest_position_snapshot("ETHUSDT")
            passed = snapshot is not None and snapshot["amount"] == 0.5
            self._log_test("position_snapshot", passed, f"snapshot={snapshot is not None}")
            return passed
        except Exception as e:
            self._log_test("position_snapshot", False, str(e))
            return False

    def test_balance_snapshot(self):
        """测试余额快照"""
        _logger.info("=" * 60)
        _logger.info("Test: balance snapshot")
        _logger.info("=" * 60)

        try:
            self.db.log_balance_snapshot(
                total=1000.0,
                free=800.0,
                used=200.0
            )
            self._log_test("balance_snapshot", True)
            return True
        except Exception as e:
            self._log_test("balance_snapshot", False, str(e))
            return False

    def test_risk_event(self):
        """测试风控事件"""
        _logger.info("=" * 60)
        _logger.info("Test: risk event")
        _logger.info("=" * 60)

        try:
            self.db.log_risk_event(
                event_type="STOP_LOSS",
                description="Test stop loss triggered",
                current_price=1950.0,
                trigger_price=1980.0,
                position_side="LONG"
            )
            self._log_test("risk_event", True)
            return True
        except Exception as e:
            self._log_test("risk_event", False, str(e))
            return False

    def test_query_methods(self):
        """测试查询方法"""
        _logger.info("=" * 60)
        _logger.info("Test: query methods")
        _logger.info("=" * 60)

        try:
            # 获取交易记录
            trades = self.db.get_trades(limit=5)
            _logger.info("get_trades: %d records", len(trades))

            # 获取今日交易
            today_trades = self.db.get_today_trades()
            _logger.info("get_today_trades: %d records", len(today_trades))

            # 获取今日盈亏
            today_pnl = self.db.get_today_pnl()
            _logger.info("get_today_pnl: %.2f", today_pnl)

            # 获取统计数据
            stats = self.db.get_statistics(days=30)
            _logger.info("get_statistics: %s", stats)

            passed = len(trades) > 0
            self._log_test("query_methods", passed, f"trades={len(trades)}")
            return passed
        except Exception as e:
            self._log_test("query_methods", False, str(e))
            return False

    def run_all_tests(self):
        """运行所有测试"""
        _logger.info("=" * 60)
        _logger.info("Supabase Trade Database Test Suite")
        _logger.info("=" * 60)

        # 运行所有测试
        self.test_log_trade()
        self.test_log_signal()
        self.test_batch_trades()
        self.test_batch_signals()
        self.test_buffered_writes()
        self.test_position_snapshot()
        self.test_balance_snapshot()
        self.test_risk_event()
        self.test_query_methods()

        # 打印测试总结
        _logger.info("=" * 60)
        _logger.info("Test Summary")
        _logger.info("=" * 60)

        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)

        for test_name, result in self.test_results:
            status = "✅" if result else "❌"
            _logger.info("%s %s", status, test_name)

        _logger.info("=" * 60)
        _logger.info("Total: %d/%d tests passed (%.1f%%)", passed, total, passed / total * 100)
        _logger.info("=" * 60)

        return passed == total


def main():
    """主函数"""
    tester = SupabaseTradeDBTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
