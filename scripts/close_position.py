"""
紧急平仓脚本
用于关闭当前持仓
"""
from trader import BitgetTrader
from logger_utils import get_logger

logger = get_logger("close_position")

def main():
    print("=" * 60)
    print("🚨 紧急平仓")
    print("=" * 60)

    # 初始化交易器
    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功")

    # 检查持仓
    print("\n📊 检查当前持仓...")
    positions = trader.get_positions()

    if not positions:
        print("✅ 无持仓，无需平仓")
        return

    position = positions[0]
    print(f"\n📊 当前持仓:")
    print(f"   方向: {position['side']}")
    print(f"   数量: {position['amount']}")
    print(f"   开仓价: {position['entry_price']:.2f}")
    print(f"   未实现盈亏: {position['unrealized_pnl']:.4f} USDT")

    # 确认平仓
    confirm = input(f"\n⚠️  确认平仓 {position['amount']} BTC? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ 取消平仓")
        return

    # 执行平仓
    print("\n正在平仓...")

    # 根据持仓方向选择平仓方向
    close_side = 'sell' if position['side'] == 'long' else 'buy'
    amount = position['amount']

    # 直接创建市价单平仓
    order = trader.create_market_order(
        side=close_side,
        amount=amount,
        reduce_only=False  # 单向持仓模式不需要 reduce_only
    )

    if order:
        print(f"✅ 平仓成功!")
        print(f"   订单ID: {order.get('id', 'N/A')}")

        # 清除本地持仓记录
        trader.risk_manager.clear_position()

        # 等待并检查
        import time
        time.sleep(2)

        positions_after = trader.get_positions()
        if not positions_after:
            print("\n✅ 持仓已清空")
        else:
            print(f"\n⚠️  仍有持仓: {positions_after[0]}")

        # 显示余额
        balance = trader.get_balance()
        print(f"\n💰 当前余额: {balance:.2f} USDT")
    else:
        print("❌ 平仓失败")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  操作被用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
