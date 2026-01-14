"""
交易功能测试脚本
测试开仓、止盈止损、平仓等功能
"""
import time
from core.trader import BitgetTrader
from utils.logger_utils import get_logger, notifier

logger = get_logger("test_trading")

def test_trading_flow():
    """测试完整的交易流程"""

    print("=" * 60)
    print("🧪 开始交易功能测试")
    print("=" * 60)

    # 初始化交易器
    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功")

    # 1. 显示账户信息
    print("\n📊 账户信息:")
    balance = trader.get_balance()
    print(f"   可用余额: {balance:.2f} USDT")

    # 2. 检查现有持仓
    print("\n📊 检查现有持仓:")
    positions = trader.get_positions()
    if positions:
        print(f"   ⚠️  已有持仓: {positions[0]['side']}")
        print("   请先平仓后再测试")
        return
    else:
        print("   ✅ 无持仓，可以开始测试")

    # 3. 获取当前价格
    ticker = trader.get_ticker()
    if not ticker:
        print("❌ 获取价格失败")
        return

    current_price = ticker['last']
    print(f"\n💰 当前BTC价格: {current_price:.2f} USDT")

    # 3.5 获取K线数据
    df = trader.get_klines()
    if df.empty:
        print("❌ 获取K线数据失败")
        return

    # 4. 测试开仓
    print("\n" + "=" * 60)
    print("📈 测试1: 开多仓")
    print("=" * 60)

    input("\n⚠️  按Enter键继续开仓测试（这将使用真实资金）...")

    # 计算测试仓位大小（使用1%余额进行测试）
    test_usdt = balance * 0.01
    test_amount = test_usdt / current_price
    print(f"测试仓位: {test_amount:.6f} BTC (~{test_usdt:.2f} USDT)")

    print("正在开多仓...")
    result = trader.open_long(test_amount, df)

    if result.success:
        print(f"✅ 开仓成功!")
        print(f"   订单ID: {result.order_id}")
        print(f"   数量: {result.amount}")
        print(f"   预计使用: ~{balance * 0.01:.2f} USDT (1%)")

        # 发送通知
        notifier.notify_trade(
            'open', 'BTCUSDT', 'long',
            result.amount, current_price,
            reason='测试开仓'
        )
    else:
        print(f"❌ 开仓失败: {result.error}")
        return

    # 5. 等待并检查持仓
    print("\n⏳ 等待5秒后检查持仓...")
    time.sleep(5)

    positions = trader.get_positions()
    if not positions:
        print("❌ 未找到持仓")
        return

    position = positions[0]
    print(f"\n📊 持仓信息:")
    print(f"   方向: {position['side']}")
    print(f"   数量: {position['amount']}")
    print(f"   开仓价: {position['entry_price']:.2f}")
    print(f"   未实现盈亏: {position['unrealized_pnl']:.2f} USDT")

    # 6. 测试平仓
    print("\n" + "=" * 60)
    print("📤 测试2: 平仓")
    print("=" * 60)

    input("\n⚠️  按Enter键继续平仓测试...")

    print("正在平仓...")
    result = trader.close_position(reason="测试平仓")

    if result.success:
        print(f"✅ 平仓成功!")
        print(f"   订单ID: {result.order_id}")

        # 计算盈亏
        ticker = trader.get_ticker()
        if ticker:
            close_price = ticker['last']
            pnl = (close_price - position['entry_price']) * position['amount']
            print(f"   平仓价: {close_price:.2f}")
            print(f"   盈亏: {pnl:+.4f} USDT")

            # 发送通知
            notifier.notify_trade(
                'close', 'BTCUSDT', 'long',
                position['amount'], close_price,
                pnl=pnl, reason='测试平仓'
            )
    else:
        print(f"❌ 平仓失败: {result.error}")
        return

    # 7. 最终检查
    print("\n⏳ 等待3秒后最终检查...")
    time.sleep(3)

    positions = trader.get_positions()
    balance_after = trader.get_balance()

    print("\n" + "=" * 60)
    print("📊 测试完成 - 最终状态")
    print("=" * 60)
    print(f"持仓状态: {'有持仓 ⚠️' if positions else '无持仓 ✅'}")
    print(f"测试前余额: {balance:.2f} USDT")
    print(f"测试后余额: {balance_after:.2f} USDT")
    print(f"余额变化: {balance_after - balance:+.4f} USDT")

    print("\n✅ 交易功能测试完成!")
    print("\n📝 测试总结:")
    print("   ✅ 开仓功能: 正常")
    print("   ✅ 平仓功能: 正常")
    print("   ✅ 通知功能: 已发送到飞书和邮箱")
    print("\n💡 提示: 止盈止损功能需要在持仓期间自动触发，")
    print("   可以通过修改价格或等待市场波动来测试。")


if __name__ == "__main__":
    try:
        test_trading_flow()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
