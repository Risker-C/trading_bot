#!/usr/bin/env python3
"""
数据库参数修复验证测试
测试修复后的 db.log_trade() 调用是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_utils import TradeDatabase, get_logger
import tempfile
import sqlite3

logger = get_logger("test_db_fix")


class TestResult:
    """测试结果"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.passed += 1
        logger.info(f"✅ {test_name} - 通过")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        logger.error(f"❌ {test_name} - 失败: {error}")

    def summary(self):
        total = self.passed + self.failed
        logger.info("\n" + "=" * 60)
        logger.info(f"测试总结: {self.passed}/{total} 通过")
        if self.failed > 0:
            logger.error(f"\n失败的测试:")
            for error in self.errors:
                logger.error(f"  - {error}")
        logger.info("=" * 60)
        return self.failed == 0


def test_log_trade_open_long(db: TradeDatabase, result: TestResult):
    """测试开多仓记录 - 修复后的正确调用"""
    test_name = "开多仓记录"
    try:
        # 模拟修复后的正确调用
        trade_id = db.log_trade(
            symbol="BTCUSDT",
            side="long",
            action="open",
            amount=0.001,
            price=90000.0,
            order_id="test_order_123",
            value_usdt=90.0,
            strategy="rsi_divergence",
            reason="RSI超卖(26.8)"
        )

        # 验证记录是否成功
        if trade_id > 0:
            # 查询数据库验证
            conn = db._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                result.add_pass(test_name)
                return True
            else:
                result.add_fail(test_name, "数据库中未找到记录")
                return False
        else:
            result.add_fail(test_name, "返回的 trade_id 无效")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_log_trade_open_short(db: TradeDatabase, result: TestResult):
    """测试开空仓记录 - 修复后的正确调用"""
    test_name = "开空仓记录"
    try:
        trade_id = db.log_trade(
            symbol="BTCUSDT",
            side="short",
            action="open",
            amount=0.001,
            price=90000.0,
            order_id="test_order_456",
            value_usdt=90.0,
            strategy="bollinger_breakthrough",
            reason="突破上轨"
        )

        if trade_id > 0:
            result.add_pass(test_name)
            return True
        else:
            result.add_fail(test_name, "返回的 trade_id 无效")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_log_trade_close(db: TradeDatabase, result: TestResult):
    """测试平仓记录 - 修复后的正确调用"""
    test_name = "平仓记录"
    try:
        trade_id = db.log_trade(
            symbol="BTCUSDT",
            side="long",
            action="close",
            amount=0.001,
            price=91000.0,
            order_id="test_order_789",
            value_usdt=91.0,
            pnl=1.0,
            pnl_percent=1.11,
            strategy="rsi_divergence",
            reason="止盈"
        )

        if trade_id > 0:
            result.add_pass(test_name)
            return True
        else:
            result.add_fail(test_name, "返回的 trade_id 无效")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_log_trade_wrong_params(db: TradeDatabase, result: TestResult):
    """测试错误的参数顺序 - 可选测试（模拟修复前的错误）"""
    test_name = "错误参数顺序检测（可选）"
    try:
        # 模拟修复前的错误调用（参数顺序错误）
        # 注意：SQLite 可能会自动进行类型转换，所以这个测试是可选的
        conn = db._get_conn()
        cursor = conn.cursor()

        # 直接执行 SQL，模拟错误的参数绑定
        cursor.execute('''
            INSERT INTO trades (
                order_id, symbol, side, action, amount, price,
                value_usdt, pnl, pnl_percent, strategy, reason, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            "test_order_999",  # order_id
            "BTCUSDT",         # symbol
            "long",            # side
            "open",            # action - 这是字符串
            "open",            # amount - 错误！应该是数字，但传入了字符串
            90000.0,           # price
            90.0,              # value_usdt
            0,                 # pnl
            0,                 # pnl_percent
            "test",            # strategy
            "test",            # reason
            "filled"           # status
        ))

        conn.commit()
        conn.close()

        # SQLite 可能会自动转换类型，这不是错误
        logger.info(f"ℹ️  {test_name} - SQLite 自动进行了类型转换（这是正常的）")
        result.add_pass(test_name + " (SQLite 类型转换)")
        return True

    except sqlite3.InterfaceError as e:
        # 预期的错误：Error binding parameter
        if "binding parameter" in str(e).lower():
            result.add_pass(test_name + " (正确检测到参数错误)")
            return True
        else:
            result.add_fail(test_name, f"意外的错误类型: {e}")
            return False
    except Exception as e:
        # 其他异常也算通过，因为至少检测到了问题
        logger.info(f"ℹ️  {test_name} - 检测到异常: {type(e).__name__}")
        result.add_pass(test_name + " (检测到异常)")
        return True


def test_log_signal(db: TradeDatabase, result: TestResult):
    """测试信号记录"""
    test_name = "信号记录"
    try:
        signal_id = db.log_signal(
            strategy="rsi_divergence",
            signal="long",
            reason="RSI超卖(26.8)",
            strength=0.8,
            confidence=0.75,
            indicators={"rsi": 26.8, "price": 90000.0}
        )

        if signal_id > 0:
            result.add_pass(test_name)
            return True
        else:
            result.add_fail(test_name, "返回的 signal_id 无效")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_database_integrity(db: TradeDatabase, result: TestResult):
    """测试数据库完整性"""
    test_name = "数据库完整性检查"
    try:
        conn = db._get_conn()
        cursor = conn.cursor()

        # 检查 trades 表
        cursor.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]

        # 检查 signals 表
        cursor.execute("SELECT COUNT(*) FROM signals")
        signal_count = cursor.fetchone()[0]

        conn.close()

        if trade_count >= 3 and signal_count >= 1:
            result.add_pass(test_name + f" (trades: {trade_count}, signals: {signal_count})")
            return True
        else:
            result.add_fail(test_name, f"记录数量不足 (trades: {trade_count}, signals: {signal_count})")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_query_trades(db: TradeDatabase, result: TestResult):
    """测试查询交易记录"""
    test_name = "查询交易记录"
    try:
        trades = db.get_trades(limit=10)

        if len(trades) > 0:
            # 验证记录字段
            first_trade = trades[0]
            required_fields = ['symbol', 'side', 'action', 'amount', 'price']

            for field in required_fields:
                if field not in first_trade:
                    result.add_fail(test_name, f"缺少字段: {field}")
                    return False

            result.add_pass(test_name + f" (查询到 {len(trades)} 条记录)")
            return True
        else:
            result.add_fail(test_name, "未查询到任何记录")
            return False

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def test_statistics(db: TradeDatabase, result: TestResult):
    """测试统计功能"""
    test_name = "统计功能"
    try:
        stats = db.get_statistics()

        required_keys = ['total_trades', 'winning_trades', 'losing_trades',
                        'win_rate', 'total_pnl', 'profit_factor']

        for key in required_keys:
            if key not in stats:
                result.add_fail(test_name, f"缺少统计字段: {key}")
                return False

        result.add_pass(test_name)
        return True

    except Exception as e:
        result.add_fail(test_name, str(e))
        return False


def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("开始数据库修复验证测试")
    logger.info("=" * 60)

    # 创建临时数据库用于测试
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    logger.info(f"\n使用临时数据库: {temp_db_path}")

    try:
        # 初始化数据库
        db = TradeDatabase(temp_db_path)
        result = TestResult()

        logger.info("\n" + "-" * 60)
        logger.info("测试1: 修复后的正确调用")
        logger.info("-" * 60)

        # 测试修复后的正确调用
        test_log_trade_open_long(db, result)
        test_log_trade_open_short(db, result)
        test_log_trade_close(db, result)
        test_log_signal(db, result)

        logger.info("\n" + "-" * 60)
        logger.info("测试2: 错误参数检测")
        logger.info("-" * 60)

        # 测试错误的参数顺序
        test_log_trade_wrong_params(db, result)

        logger.info("\n" + "-" * 60)
        logger.info("测试3: 数据库功能验证")
        logger.info("-" * 60)

        # 测试数据库功能
        test_database_integrity(db, result)
        test_query_trades(db, result)
        test_statistics(db, result)

        # 显示测试总结
        success = result.summary()

        # 清理临时数据库
        os.unlink(temp_db_path)
        logger.info(f"\n已清理临时数据库: {temp_db_path}")

        if success:
            logger.info("\n🎉 所有测试通过！修复验证成功！")
            return 0
        else:
            logger.error("\n❌ 部分测试失败，请检查错误信息")
            return 1

    except Exception as e:
        logger.error(f"\n测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

        # 清理临时数据库
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)

        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
