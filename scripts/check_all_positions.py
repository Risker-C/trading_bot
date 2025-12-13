"""
检查所有持仓（包括多空双向）
"""
from trader import BitgetTrader
from logger_utils import get_logger
import json

logger = get_logger("check_all")

def main():
    print("=" * 60)
    print("📊 完整持仓检查")
    print("=" * 60)

    trader = BitgetTrader()

    if trader.exchange is None:
        print("❌ 交易所初始化失败")
        return

    print("✅ 交易所连接成功\n")

    # 1. 余额
    balance = trader.get_balance()
    print(f"💰 余额: {balance:.2f} USDT\n")

    # 2. 使用原始API获取所有持仓
    print("📊 所有持仓（原始API）:")
    try:
        positions = trader.exchange.fetch_positions(
            symbols=['BTCUSDT'],
            params={"productType": "USDT-FUTURES"}
        )

        print(f"   找到 {len(positions)} 个持仓记录\n")

        for i, pos in enumerate(positions, 1):
            # 只显示有持仓的
            contracts = float(pos.get('contracts', 0))
            if contracts > 0:
                print(f"   持仓 {i}:")
                print(f"   符号: {pos.get('symbol')}")
                print(f"   方向: {pos.get('side')}")
                print(f"   数量: {contracts}")
                print(f"   开仓价: {pos.get('entryPrice', 0):.2f}")
                print(f"   未实现盈亏: {pos.get('unrealizedPnl', 0):.4f}")
                print(f"   保证金: {pos.get('initialMargin', 0):.4f}")
                print(f"   杠杆: {pos.get('leverage', 0)}")
                print()

    except Exception as e:
        print(f"   获取持仓失败: {e}")
        import traceback
        traceback.print_exc()

    # 3. 检查未平仓订单
    print("\n📋 未平仓订单:")
    try:
        open_orders = trader.exchange.fetch_open_orders(
            symbol='BTCUSDT',
            params={"productType": "USDT-FUTURES"}
        )

        if open_orders:
            for order in open_orders:
                print(f"   订单ID: {order['id']}")
                print(f"   方向: {order['side']}")
                print(f"   数量: {order['amount']}")
                print(f"   状态: {order['status']}")
                print()
        else:
            print("   无未平仓订单")

    except Exception as e:
        print(f"   获取订单失败: {e}")

    # 4. 检查最近成交订单
    print("\n📋 最近成交订单:")
    try:
        closed_orders = trader.exchange.fetch_closed_orders(
            symbol='BTCUSDT',
            limit=5,
            params={"productType": "USDT-FUTURES"}
        )

        for i, order in enumerate(closed_orders[-5:], 1):
            print(f"\n   订单 {i}:")
            print(f"   ID: {order['id']}")
            print(f"   方向: {order['side']}")
            print(f"   数量: {order['amount']}")
            print(f"   成交量: {order.get('filled', 0)}")
            print(f"   状态: {order['status']}")
            print(f"   时间: {order.get('datetime', 'N/A')}")

    except Exception as e:
        print(f"   获取成交订单失败: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
