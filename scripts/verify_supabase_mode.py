"""
验证 Supabase 模式是否正确启用
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger_utils import db, get_logger

_logger = get_logger("verify")


def main():
    """验证数据库配置"""
    _logger.info("=" * 60)
    _logger.info("Supabase Mode Verification")
    _logger.info("=" * 60)

    # 检查数据库类型
    db_type = type(db).__name__
    _logger.info("Current database type: %s", db_type)

    if db_type == "SupabaseTradeDatabase":
        _logger.info("✅ Supabase mode is ENABLED")
        _logger.info("Database: Supabase Cloud")

        # 测试写入一条记录
        try:
            _logger.info("")
            _logger.info("Testing write operation...")
            trade_id = db.log_trade(
                symbol="ETHUSDT",
                side="LONG",
                action="OPEN",
                amount=0.01,
                price=2000.0,
                strategy="verification_test",
                reason="Supabase mode verification",
                status="test"
            )
            _logger.info("✅ Write test successful, trade_id=%d", trade_id)

            # 测试读取
            _logger.info("")
            _logger.info("Testing read operation...")
            trades = db.get_trades(limit=1)
            if trades:
                _logger.info("✅ Read test successful, found %d records", len(trades))
                _logger.info("Latest trade: %s", trades[0])
            else:
                _logger.warning("⚠️ No trades found")

            _logger.info("")
            _logger.info("=" * 60)
            _logger.info("✅ Supabase mode verification PASSED")
            _logger.info("=" * 60)
            return True

        except Exception as e:
            _logger.error("❌ Supabase operation failed: %s", e)
            _logger.info("=" * 60)
            _logger.info("❌ Supabase mode verification FAILED")
            _logger.info("=" * 60)
            return False

    elif db_type == "TradeDatabase":
        _logger.warning("⚠️ Supabase mode is DISABLED")
        _logger.warning("Database: SQLite (trading_bot.db)")
        _logger.info("")
        _logger.info("To enable Supabase mode:")
        _logger.info("1. Edit config/settings.py")
        _logger.info("2. Set USE_SUPABASE_FOR_LIVE_DATA = True")
        _logger.info("3. Restart the bot")
        _logger.info("")
        _logger.info("=" * 60)
        _logger.info("⚠️ Verification skipped (SQLite mode)")
        _logger.info("=" * 60)
        return False
    else:
        _logger.error("❌ Unknown database type: %s", db_type)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
