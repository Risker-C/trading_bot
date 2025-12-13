"""
平掉所有持仓（双向持仓模式）
"""
from trader import BitgetTrader
from logger_utils import get_logger

logger = get_logger("close_both")

def main():
    print("=" * 60)
    print("🚨 平掉所有持仓（双向持仓模式）")
    print("=" * 60)

    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功\n")

    # 获取所有持仓
    try:
        positions = trader.exchange.fetch_positions(
            symbols=['BTCUSDT'],
            params={"productType": "USDT-FUTURES"}
        )

        active_positions = []
        for pos in positions:
            contracts = float(pos.get('contracts', 0))
            if contracts > 0:
                active_positions.append(pos)

        if not active_positions:
            print("✅ 无持仓")
            return

        print(f"📊 找到 {len(active_positions)} 个持仓:\n")

        for i, pos in enumerate(active_positions, 1):
            side = pos.get('side')
            amount = float(pos.get('contracts', 0))
            entry_price = float(pos.get('entryPrice', 0))
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))

            print(f"持仓 {i}:")
            print(f"   方向: {side}")
            print(f"   数量: {amount}")
            print(f"   开仓价: {entry_price:.2f}")
            print(f"   未实现盈亏: {unrealized_pnl:.4f} USDT\n")

        # 平掉所有持仓
        print("=" * 60)
        print("开始平仓...")
        print("=" * 60)

        for i, pos in enumerate(active_positions, 1):
            side = pos.get('side')
            amount = float(pos.get('contracts', 0))

            # 确定平仓方向
            close_side = 'sell' if side == 'long' else 'buy'

            print(f"\n平仓 {i}/{len(active_positions)}: {side.upper()} {amount} BTC")
            print(f"   执行: {close_side.upper()} {amount} (tradeSide=close)")

            # 使用 reduce_only=True 来平仓
            order = trader.create_market_order(
                side=close_side,
                amount=amount,
                reduce_only=True  # 这会使用 tradeSide="close"
            )

            if order:
                print(f"   ✅ 平仓成功! 订单ID: {order.get('id', 'N/A')}")
            else:
                print(f"   ❌ 平仓失败")

        # 等待并检查最终状态
        import time
        print("\n⏳ 等待3秒后检查最终状态...")
        time.sleep(3)

        # 最终检查
        positions_after = trader.exchange.fetch_positions(
            symbols=['BTCUSDT'],
            params={"productType": "USDT-FUTURES"}
        )

        active_after = [p for p in positions_after if float(p.get('contracts', 0)) > 0]

        print("\n" + "=" * 60)
        print("最终状态")
        print("=" * 60)

        if active_after:
            print(f"⚠️  仍有 {len(active_after)} 个持仓:")
            for pos in active_after:
                print(f"   {pos.get('side')}: {pos.get('contracts')} BTC")
        else:
            print("✅ 所有持仓已清空")

        balance = trader.get_balance()
        print(f"\n💰 当前余额: {balance:.2f} USDT")

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
