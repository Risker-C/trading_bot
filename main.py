"""
量化交易机器人 - 主入口
整合 Qbot 功能的增强版
"""
import sys
import argparse
from datetime import datetime

import config
from utils.logger_utils import get_logger

logger = get_logger("main")


def run_live():
    """运行实盘交易"""
    from core.trader import BitgetTrader
    
    # 验证配置
    errors = config.validate_config()
    if errors:
        logger.error("配置错误:")
        for e in errors:
            logger.error(f"  - {e}")
        sys.exit(1)
    
    config.print_config()
    
    trader = BitgetTrader()
    trader.run()


def run_backtest(args):
    """运行回测"""
    import pandas as pd
    import ccxt
    from analysis.backtest import Backtester, compare_strategies
    
    # 获取数据
    print("获取历史数据...")
    
    if args.file:
        df = pd.read_csv(args.file, parse_dates=['timestamp'], index_col='timestamp')
    else:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(
            args.symbol or 'BTC/USDT',
            timeframe=args.timeframe or '15m',
            limit=args.limit or 1000
        )
        
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
    
    print(f"数据范围: {df.index[0]} ~ {df.index[-1]}")
    print(f"K线数量: {len(df)}")
    
    # 运行回测
    if args.compare:
        strategies = args.strategies.split(',') if args.strategies else config.ENABLE_STRATEGIES
        compare_strategies(df, strategies, initial_balance=args.balance)
    else:
        strategies = args.strategies.split(',') if args.strategies else config.ENABLE_STRATEGIES
        
        backtester = Backtester(df, initial_balance=args.balance)
        result = backtester.run(strategies=strategies, use_consensus=args.consensus)
        
        if args.plot:
            backtester.plot_equity_curve(save_path=args.plot)
        
        if args.export:
            backtester.export_trades(args.export)


def run_optimize(args):
    """运行参数优化"""
    import pandas as pd
    import ccxt
    from analysis.backtest import optimize_parameters
    
    # 获取数据
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(
        args.symbol or 'BTC/USDT',
        timeframe=args.timeframe or '15m',
        limit=2000
    )
    
    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # 定义参数网格
    param_grid = {
        'RSI_PERIOD': [10, 14, 20],
        'RSI_OVERSOLD': [25, 30, 35],
        'RSI_OVERBOUGHT': [65, 70, 75],
    }
    
    optimize_parameters(df, args.strategy or 'rsi_divergence', param_grid)


def show_status():
    """显示状态"""
    from core.trader import BitgetTrader
    
    trader = BitgetTrader()
    status = trader.get_status()
    
    print("\n" + "=" * 50)
    print("交易机器人状态")
    print("=" * 50)
    
    print(f"\n余额: {trader.get_balance():.2f} USDT")
    
    if status['position']:
        pos = status['position']
        print(f"\n持仓:")
        print(f"  方向: {pos['side']}")
        print(f"  数量: {pos['amount']}")
        print(f"  开仓价: {pos['entry_price']:.2f}")
        print(f"  未实现盈亏: {pos['unrealized_pnl']:.2f}")
    else:
        print("\n无持仓")
    
    print(f"\n风险指标:")
    risk = status['risk']['metrics']
    print(f"  总交易: {risk['total_trades']}")
    print(f"  胜率: {risk['win_rate']}")
    print(f"  盈亏比: {risk['profit_factor']}")
    print(f"  最大回撤: {risk['max_drawdown']}")
    print(f"  Kelly: {risk['kelly_fraction']}")
    
    print(f"\n健康状态:")
    health = status['health']
    print(f"  健康: {'是' if health['is_healthy'] else '否'}")
    print(f"  API错误: {health['api_errors']}")
    print(f"  重连次数: {health['reconnect_count']}")


def main():
    parser = argparse.ArgumentParser(description='量化交易机器人')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # live 命令
    parser_live = subparsers.add_parser('live', help='运行实盘交易')
    
    # backtest 命令
    parser_bt = subparsers.add_parser('backtest', help='运行回测')
    parser_bt.add_argument('--file', help='数据文件路径')
    parser_bt.add_argument('--symbol', default='BTC/USDT', help='交易对')
    parser_bt.add_argument('--timeframe', default='15m', help='时间周期')
    parser_bt.add_argument('--limit', type=int, default=1000, help='K线数量')
    parser_bt.add_argument('--balance', type=float, default=10000, help='初始资金')
    parser_bt.add_argument('--strategies', help='策略列表，逗号分隔')
    parser_bt.add_argument('--consensus', action='store_true', help='使用共识信号')
    parser_bt.add_argument('--compare', action='store_true', help='对比策略')
    parser_bt.add_argument('--plot', help='保存图表路径')
    parser_bt.add_argument('--export', help='导出交易记录路径')
    
    # optimize 命令
    parser_opt = subparsers.add_parser('optimize', help='参数优化')
    parser_opt.add_argument('--strategy', help='策略名称')
    parser_opt.add_argument('--symbol', default='BTC/USDT', help='交易对')
    parser_opt.add_argument('--timeframe', default='15m', help='时间周期')
    
    # status 命令
    parser_status = subparsers.add_parser('status', help='显示状态')
    
    args = parser.parse_args()
    
    if args.command == 'live':
        run_live()
    elif args.command == 'backtest':
        run_backtest(args)
    elif args.command == 'optimize':
        run_optimize(args)
    elif args.command == 'status':
        show_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
