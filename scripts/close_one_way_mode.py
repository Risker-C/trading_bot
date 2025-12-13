"""
单向持仓模式平仓
使用 tradeSide="open" + 反向订单
"""
from trader import BitgetTrader
from logger_utils import get_logger

logger = get_logger("close_one_way")

def main():
    print("=" * 60)
    print("🚨 单向持仓模式平仓")
    print("=" * 60)

    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功\n")

    # 获取当前持仓
    try:
        positions = trader.exchange.fetch_positions(
            symbols=['BTCUSDT'],
            params={"productType": "USDT-FUTURES"}
        )

        active_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]

        if not active_positions:
            print("✅ 无持仓")
            return

        pos = active_positions[0]
        side = pos.get('side')
        amount = float(pos.get('contracts', 0))
        entry_price = float(pos.get('entryPrice', 0))

        print(f"📊 当前持仓:")
        print(f"   方向: {side}")
        print(f"   数量: {amount}")
        print(f"   开仓价: {entry_price:.2f}\n")

        # 确定平仓方向
        close_side = 'sell' if side == 'long' else 'buy'

        print(f"执行平仓（单向持仓模式）:")
        print(f"   方向: {close_side.upper()}")
        print(f"   数量: {amount}")
        print(f"   tradeSide: open (单向模式)\n")

        # 单向持仓模式：使用 tradeSide="open" + 反向订单
        order = trader.create_market_order(
            side=close_side,
            amount=amount,
            reduce_only=False  # 单向模式使用 tradeSide="open"
        )

        if order:
            print(f"✅ 平仓成功!")
            print(f"   订单ID: {order.get('id', 'N/A')}")
            print(f"   方向: {order.get('side', 'N/A')}")
            print(f"   数量: {order.get('amount', 'N/A')}")

            # 清除本地持仓记录
            trader.risk_manager.clear_position()

            # 等待并检查
            import time
            time.sleep(3)

            positions_after = trader.exchange.fetch_positions(
                symbols=['BTCUSDT'],
                params={"productType": "USDT-FUTURES"}
            )

            active_after = [p for p in positions_after if float(p.get('contracts', 0)) > 0]

            print("\n" + "=" * 60)
            print("最终状态")
            print("=" * 60)

            if active_after:
                print(f"⚠️  仍有持仓:")
                for p in active_after:
                    print(f"   {p.get('side')}: {p.get('contracts')} BTC")
            else:
                print("✅ 所有持仓已清空")

            balance = trader.get_balance()
            print(f"\n💰 当前余额: {balance:.2f} USDT")

        else:
            print("❌ 平仓失败")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
