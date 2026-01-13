"""
命令行工具 - 手动操作和管理
"""
import argparse
import sys
import asyncio
from datetime import datetime

import config
from trader import BitgetTrader
from bot import TradingBot
from logger_utils import db, notifier, get_logger
# from backtest import run_backtest_from_exchange  # 暂时注释，函数不存在
# from monitor import run_monitor  # 暂时注释，函数不存在

logger = get_logger("cli")


def cmd_status():
    """查看状态"""
    trader = BitgetTrader()
    if trader.exchange is None:
        print("❌ 交易所连接失败")
        return
    
    # 余额
    try:
        balance_data = trader.exchange.fetch_balance(params={"productType": config.PRODUCT_TYPE})
        usdt = balance_data.get('USDT', {})
        print("\n💰 账户余额:")
        print(f"   可用: {usdt.get('free', 0):.2f} USDT")
        print(f"   冻结: {usdt.get('used', 0):.2f} USDT")
        print(f"   总计: {usdt.get('total', 0):.2f} USDT")
    except Exception as e:
        print(f"\n💰 账户余额: {trader.get_balance():.2f} USDT (可用)")
        print(f"   ⚠️  无法获取详细余额信息: {e}")
    
    # 持仓
    positions = trader.get_positions()
    print("\n📊 当前持仓:")
    if positions:
        # 获取当前价格
        ticker = trader.get_ticker()
        current_price = ticker['last'] if ticker else 0

        for pos in positions:
            emoji = "🟢" if pos['side'] == 'long' else "🔴"
            # 计算盈亏百分比
            pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount']) * 100 * config.LEVERAGE) if pos['entry_price'] > 0 and pos['amount'] > 0 else 0

            print(f"   {emoji} {pos['side'].upper()}: {pos['amount']} @ {pos['entry_price']:.2f}")
            print(f"      当前价: {current_price:.2f}")
            print(f"      盈亏: {pos['unrealized_pnl']:+.2f} USDT ({pnl_percent:+.2f}%)")
    else:
        print("   无持仓")
    
    # 行情
    ticker = trader.get_ticker()
    if ticker:
        print(f"\n📈 当前价格: {ticker['last']:.2f}")


def cmd_open_long(amount: float = None):
    """手动开多"""
    trader = BitgetTrader()
    if not trader.initialize():
        print("❌ 初始化失败")
        return
    
    result = trader.open_long(amount)
    
    if result.success:
        print(f"✅ 开多成功")
        print(f"   订单ID: {result.order_id}")
        print(f"   数量: {result.amount}")
        print(f"   价格: {result.price:.2f}")
    else:
        print(f"❌ 开多失败: {result.error}")


def cmd_open_short(amount: float = None):
    """手动开空"""
    trader = BitgetTrader()
    if not trader.initialize():
        print("❌ 初始化失败")
        return
    
    result = trader.open_short(amount)
    
    if result.success:
        print(f"✅ 开空成功")
        print(f"   订单ID: {result.order_id}")
        print(f"   数量: {result.amount}")
        print(f"   价格: {result.price:.2f}")
    else:
        print(f"❌ 开空失败: {result.error}")


def cmd_close_all():
    """平掉所有仓位"""
    trader = BitgetTrader()
    if not trader.initialize():
        print("❌ 初始化失败")
        return
    
    # 确认
    confirm = input("⚠️ 确认平掉所有仓位? (yes/no): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return
    
    results = trader.close_all_positions()
    
    for result in results:
        if result.success:
            print(f"✅ 平仓成功: {result.order_id}")
        else:
            print(f"❌ 平仓失败: {result.error}")
    
    if not results:
        print("无持仓需要平仓")


def cmd_trades(limit: int = 20):
    """查看交易记录"""
    trades = db.get_trades(limit=limit)
    
    print(f"\n📝 最近 {limit} 笔交易:")
    print("-" * 80)
    print(f"{'时间':<20} {'方向':<12} {'数量':<10} {'价格':<12} {'盈亏':<15}")
    print("-" * 80)
    
    for trade in trades:
        time_str = trade.get('created_at', '')[:19]
        side = trade.get('side', '')
        action = trade.get('action', '')
        amount = trade.get('amount', 0)
        price = trade.get('price', 0)
        pnl = trade.get('pnl', 0)
        
        side_text = f"{action}_{side}"
        pnl_str = f"{pnl:+.2f}" if pnl != 0 else "-"
        
        print(f"{time_str:<20} {side_text:<12} {amount:<10.4f} {price:<12.2f} {pnl_str}")


def cmd_stats():
    """查看统计"""
    stats = db.get_statistics()
    
    print("\n📊 交易统计:")
    print("-" * 40)
    print(f"总交易次数: {stats['total_trades']}")
    print(f"盈利次数: {stats['winning_trades']}")
    print(f"亏损次数: {stats['losing_trades']}")
    print(f"胜率: {stats['win_rate']:.1f}%")
    print(f"总盈亏: {stats['total_pnl']:+.2f} USDT")
    print(f"平均盈亏: {stats['avg_pnl']:+.2f} USDT")
    print(f"最大单笔盈利: {stats['max_profit']:+.2f} USDT")
    print(f"最大单笔亏损: {stats['max_loss']:+.2f} USDT")


def cmd_backtest():
    """运行回测"""
    print("🔄 开始回测...")
    print("⚠️  回测功能暂时不可用，请使用 python3 backtest.py 直接运行")
    # run_backtest_from_exchange()  # 暂时注释，函数不存在


def cmd_monitor():
    """运行监控面板"""
    print("⚠️  监控面板功能暂时不可用，请使用 python3 monitor.py 直接运行")
    # run_monitor()  # 暂时注释，函数不存在


def cmd_run():
    """运行机器人"""
    bot = TradingBot()
    bot.start()


def cmd_test_notify():
    """测试通知"""
    notifier.send_message("🔔 测试通知\n\n这是一条测试消息。")
    print("通知已发送（如果配置正确）")


def cmd_market(format_type='dashboard', timeframes=None):
    """查看市场快照"""
    from market_snapshot import MarketSnapshot

    trader = BitgetTrader()
    if trader.exchange is None:
        print("❌ 交易所连接失败")
        return

    # 解析时间周期
    if timeframes:
        tf_list = [tf.strip() for tf in timeframes.split(',')]
    else:
        tf_list = ['15m']  # 默认只显示15m

    snapshot_gen = MarketSnapshot(trader, tf_list)

    # 异步获取快照
    snapshot = asyncio.run(snapshot_gen.fetch_snapshot())

    # 输出
    if format_type == 'json':
        print(snapshot_gen.to_json(snapshot))
    else:
        print(snapshot_gen.to_dashboard(snapshot))


def main():
    parser = argparse.ArgumentParser(description="量化交易命令行工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # status
    subparsers.add_parser('status', help='查看账户状态')
    
    # open-long
    p_long = subparsers.add_parser('open-long', help='手动开多')
    p_long.add_argument('--amount', type=float, help='开仓数量')
    
    # open-short
    p_short = subparsers.add_parser('open-short', help='手动开空')
    p_short.add_argument('--amount', type=float, help='开仓数量')
    
    # close-all
    subparsers.add_parser('close-all', help='平掉所有仓位')
    
    # trades
    p_trades = subparsers.add_parser('trades', help='查看交易记录')
    p_trades.add_argument('--limit', type=int, default=20, help='显示数量')
    
    # stats
    subparsers.add_parser('stats', help='查看统计')
    
    # backtest
    subparsers.add_parser('backtest', help='运行回测')
    
    # monitor
    subparsers.add_parser('monitor', help='运行监控面板')
    
    # run
    subparsers.add_parser('run', help='运行交易机器人')
    
    # test-notify
    subparsers.add_parser('test-notify', help='测试Telegram通知')

    # market
    p_market = subparsers.add_parser('market', help='查看市场快照')
    p_market.add_argument('--format', choices=['dashboard', 'json'], default='dashboard', help='输出格式')
    p_market.add_argument('--timeframes', type=str, help='时间周期（逗号分隔，如: 15m,1h,4h）')

    args = parser.parse_args()
    
    if args.command == 'status':
        cmd_status()
    elif args.command == 'open-long':
        cmd_open_long(args.amount)
    elif args.command == 'open-short':
        cmd_open_short(args.amount)
    elif args.command == 'close-all':
        cmd_close_all()
    elif args.command == 'trades':
        cmd_trades(args.limit)
    elif args.command == 'stats':
        cmd_stats()
    elif args.command == 'backtest':
        cmd_backtest()
    elif args.command == 'monitor':
        cmd_monitor()
    elif args.command == 'run':
        cmd_run()
    elif args.command == 'test-notify':
        cmd_test_notify()
    elif args.command == 'market':
        cmd_market(args.format, args.timeframes)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
