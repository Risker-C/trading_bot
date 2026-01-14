"""
使用 tradeSide="open" 来平仓
通过开反向仓位来减少持仓
"""
from trader import BitgetTrader
from utils.logger_utils import get_logger

logger = get_logger("close_with_open")

def main():
    print("=" * 60)
    print("🚨 使用 tradeSide='open' 平仓")
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

        # 确定反向方向
        reverse_side = 'sell' if side == 'long' else 'buy'

        print(f"执行操作:")
        print(f"   方向: {reverse_side.upper()}")
        print(f"   数量: {amount}")
        print(f"   tradeSide: open")
        print(f"   说明: 开反向仓位来减少持仓\n")

        # 使用 tradeSide="open"
        params = {
            "productType": "USDT-FUTURES",
            "tradeSide": "open"
        }

        print(f"API 参数: {params}\n")

        order = trader.exchange.create_order(
            symbol='BTCUSDT',
            type='market',
            side=reverse_side,
            amount=amount,
            params=params
        )

        if order:
            print(f"✅ 订单成功!")
            print(f"   订单ID: {order.get('id', 'N/A')}")
            print(f"   方向: {order.get('side', 'N/A')}")
            print(f"   数量: {order.get('amount', 'N/A')}")

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
                print(f"持仓数量: {len(active_after)}")
                for p in active_after:
                    print(f"   {p.get('side')}: {p.get('contracts')} BTC @ {p.get('entryPrice'):.2f}")
            else:
                print("✅ 所有持仓已清空")

            balance = trader.get_balance()
            print(f"\n💰 当前余额: {balance:.2f} USDT")

        else:
            print("❌ 订单失败")

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
