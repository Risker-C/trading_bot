"""
使用 Bitget 原始 API 平仓
直接调用 Bitget 的平仓接口
"""
from core.trader import BitgetTrader
from utils.logger_utils import get_logger

logger = get_logger("close_raw")

def main():
    print("=" * 60)
    print("🚨 使用原始 API 平仓所有持仓")
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

        print(f"📊 找到 {len(active_positions)} 个持仓:\n")

        for i, pos in enumerate(active_positions, 1):
            side = pos.get('side')
            amount = float(pos.get('contracts', 0))
            entry_price = float(pos.get('entryPrice', 0))

            print(f"持仓 {i}:")
            print(f"   方向: {side}")
            print(f"   数量: {amount}")
            print(f"   开仓价: {entry_price:.2f}\n")

        # 尝试使用 Bitget 的 flash close 功能（一键平仓）
        print("=" * 60)
        print("尝试方法1: 使用一键平仓 API")
        print("=" * 60)

        for pos in active_positions:
            side = pos.get('side')

            try:
                # 使用 Bitget 的一键平仓 API
                result = trader.exchange.private_mix_post_v2_mix_order_close_positions({
                    'symbol': 'BTCUSDT',
                    'productType': 'USDT-FUTURES',
                    'holdSide': side
                })

                print(f"\n✅ {side.upper()} 仓位平仓成功!")
                print(f"   结果: {result}")

            except Exception as e:
                print(f"\n❌ {side.upper()} 仓位平仓失败: {e}")

        # 等待并检查
        import time
        print("\n⏳ 等待3秒后检查最终状态...")
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
            print(f"⚠️  仍有 {len(active_after)} 个持仓:")
            for p in active_after:
                print(f"   {p.get('side')}: {p.get('contracts')} BTC")
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
