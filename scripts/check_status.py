"""
检查账户状态
"""
from trader import BitgetTrader
from utils.logger_utils import get_logger

logger = get_logger("check_status")

def main():
    print("=" * 60)
    print("📊 账户状态检查")
    print("=" * 60)

    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功\n")

    # 1. 余额
    balance = trader.get_balance()
    print(f"💰 余额: {balance:.2f} USDT\n")

    # 2. 持仓
    positions = trader.get_positions()
    if positions:
        print("📊 持仓:")
        for pos in positions:
            print(f"   方向: {pos['side']}")
            print(f"   数量: {pos['amount']}")
            print(f"   开仓价: {pos['entry_price']:.2f}")
            print(f"   当前价: {trader.get_ticker()['last']:.2f}")
            print(f"   未实现盈亏: {pos['unrealized_pnl']:.4f} USDT")
    else:
        print("📊 无持仓")

    # 3. 最近订单
    print("\n📋 最近5笔订单:")
    try:
        orders = trader.exchange.fetch_orders(
            symbol='BTCUSDT',
            limit=5,
            params={"productType": "USDT-FUTURES"}
        )

        for i, order in enumerate(orders[-5:], 1):
            print(f"\n   订单 {i}:")
            print(f"   ID: {order['id']}")
            print(f"   方向: {order['side']}")
            print(f"   数量: {order['amount']}")
            print(f"   状态: {order['status']}")
            print(f"   时间: {order['datetime']}")
    except Exception as e:
        print(f"   获取订单失败: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
