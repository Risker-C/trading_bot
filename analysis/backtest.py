"""
回测模块 - 来自 Qbot
支持策略回测和性能评估
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import matplotlib.pyplot as plt

import config
from strategies.strategies import (
    Signal, TradeSignal, get_strategy, 
    analyze_all_strategies, STRATEGY_MAP
)
from strategies.indicators import IndicatorCalculator
from utils.logger_utils import get_logger

logger = get_logger("backtest")


@dataclass
class BacktestTrade:
    """回测交易记录"""
    entry_time: datetime
    exit_time: datetime = None
    side: str = ""
    entry_price: float = 0
    exit_price: float = 0
    amount: float = 0
    pnl: float = 0
    pnl_percent: float = 0
    commission: float = 0
    strategy: str = ""
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    # 基础统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    
    # 盈亏统计
    total_pnl: float = 0
    total_commission: float = 0
    net_pnl: float = 0
    avg_pnl: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    
    # 回撤统计
    max_drawdown: float = 0
    max_drawdown_duration: int = 0
    
    # 收益统计
    total_return: float = 0
    annual_return: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    
    # 交易统计
    avg_trade_duration: float = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # 详细数据
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)


class Backtester:
    """回测引擎"""
    
    def __init__(
        self,
        df: pd.DataFrame,
        initial_balance: float = None,
        commission: float = None,
        slippage: float = None,
        leverage: int = None
    ):
        self.df = df.copy()
        self.initial_balance = initial_balance or config.BACKTEST_INITIAL_BALANCE
        self.commission = commission or config.BACKTEST_COMMISSION
        self.slippage = slippage or config.BACKTEST_SLIPPAGE
        self.leverage = leverage or config.LEVERAGE
        
        # 状态
        self.balance = self.initial_balance
        self.position: Optional[BacktestTrade] = None
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[Dict] = []
        
        # 统计
        self.peak_equity = self.initial_balance
        self.max_drawdown = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
    
    def run(
        self,
        strategies: List[str] = None,
        use_consensus: bool = False,
        verbose: bool = True
    ) -> BacktestResult:
        """
        运行回测
        """
        strategies = strategies or config.ENABLE_STRATEGIES
        
        if verbose:
            logger.info(f"开始回测: {len(self.df)} 根K线")
            logger.info(f"策略: {strategies}")
            logger.info(f"初始资金: {self.initial_balance}")
        
        # 需要足够的历史数据
        warmup = 100
        
        for i in range(warmup, len(self.df)):
            # 获取到当前为止的数据
            current_df = self.df.iloc[:i+1].copy()
            current_bar = self.df.iloc[i]
            current_time = current_bar.name if isinstance(current_bar.name, datetime) else datetime.now()
            current_price = current_bar['close']
            
            # 记录权益
            equity = self._calculate_equity(current_price)
            self.equity_curve.append({
                'time': current_time,
                'equity': equity,
                'balance': self.balance,
                'position_value': equity - self.balance,
            })
            
            # 更新回撤
            self._update_drawdown(equity)
            
            # 有持仓时检查止损止盈
            if self.position:
                should_close, reason = self._check_exit(current_df, current_price)
                if should_close:
                    self._close_position(current_price, current_time, reason)
                    continue
            
            # 无持仓时检查开仓信号
            else:
                signal = self._get_signal(current_df, strategies, use_consensus)
                
                if signal and signal.signal == Signal.LONG:
                    self._open_position('long', current_price, current_time, signal)
                elif signal and signal.signal == Signal.SHORT:
                    self._open_position('short', current_price, current_time, signal)
        
        # 回测结束，强制平仓
        if self.position:
            final_price = self.df.iloc[-1]['close']
            final_time = self.df.index[-1] if isinstance(self.df.index[-1], datetime) else datetime.now()
            self._close_position(final_price, final_time, "回测结束")
        
        # 计算结果
        result = self._calculate_result()
        
        if verbose:
            self._print_result(result)
        
        return result
    
    def _calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        equity = self.balance
        
        if self.position:
            if self.position.side == 'long':
                pnl = (current_price - self.position.entry_price) * self.position.amount
            else:
                pnl = (self.position.entry_price - current_price) * self.position.amount
            equity += pnl
        
        return equity
    
    def _update_drawdown(self, equity: float):
        """更新回撤"""
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = (self.peak_equity - equity) / self.peak_equity
        self.max_drawdown = max(self.max_drawdown, drawdown)
    
    def _get_signal(
        self,
        df: pd.DataFrame,
        strategies: List[str],
        use_consensus: bool
    ) -> Optional[TradeSignal]:
        """获取交易信号"""
        try:
            if use_consensus:
                from strategies.strategies import get_consensus_signal
                return get_consensus_signal(df, strategies)
            else:
                signals = analyze_all_strategies(df, strategies)
                return signals[0] if signals else None
        except Exception as e:
            return None
    
    def _open_position(
        self,
        side: str,
        price: float,
        time: datetime,
        signal: TradeSignal
    ):
        """开仓"""
        # 计算仓位大小
        position_value = self.balance * config.POSITION_SIZE_PERCENT
        position_value = min(position_value, self.balance * 0.5)
        
        # 考虑滑点
        if side == 'long':
            entry_price = price * (1 + self.slippage)
        else:
            entry_price = price * (1 - self.slippage)
        
        amount = position_value / entry_price * self.leverage
        
        # 计算手续费
        commission = position_value * self.commission
        self.balance -= commission
        
        self.position = BacktestTrade(
            entry_time=time,
            side=side,
            entry_price=entry_price,
            amount=amount,
            commission=commission,
            strategy=signal.strategy if signal else "unknown"
        )
    
    def _check_exit(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> Tuple[bool, str]:
        """检查是否需要平仓"""
        if not self.position:
            return False, ""
        
        # 计算盈亏比例
        if self.position.side == 'long':
            pnl_pct = (current_price - self.position.entry_price) / self.position.entry_price
        else:
            pnl_pct = (self.position.entry_price - current_price) / self.position.entry_price
        
        pnl_pct *= self.leverage
        
        # 止损检查
        if pnl_pct <= -config.STOP_LOSS_PERCENT:
            return True, "止损"
        
        # 止盈检查
        if pnl_pct >= config.TAKE_PROFIT_PERCENT:
            return True, "止盈"
        
        # 策略退出信号
        try:
            for strategy_name in config.ENABLE_STRATEGIES:
                strategy = get_strategy(strategy_name, df)
                exit_signal = strategy.check_exit(self.position.side)

                if self.position.side == 'long' and exit_signal.signal == Signal.CLOSE_LONG:
                    return True, f"策略退出: {exit_signal.reason}"
                if self.position.side == 'short' and exit_signal.signal == Signal.CLOSE_SHORT:
                    return True, f"策略退出: {exit_signal.reason}"
        except Exception as e:
            logger.debug(f"回测中检查策略退出信号失败: {e}")
            pass
        
        return False, ""
    
    def _close_position(
        self,
        price: float,
        time: datetime,
        reason: str
    ):
        """平仓"""
        if not self.position:
            return
        
        # 考虑滑点
        if self.position.side == 'long':
            exit_price = price * (1 - self.slippage)
        else:
            exit_price = price * (1 + self.slippage)
        
        # 计算盈亏
        if self.position.side == 'long':
            pnl = (exit_price - self.position.entry_price) * self.position.amount
        else:
            pnl = (self.position.entry_price - exit_price) * self.position.amount
        
        pnl_percent = pnl / (self.position.entry_price * self.position.amount / self.leverage) * 100
        
        # 平仓手续费
        close_commission = abs(self.position.amount * exit_price / self.leverage) * self.commission
        
        # 更新余额
        self.balance += pnl - close_commission
        
        # 记录交易
        self.position.exit_time = time
        self.position.exit_price = exit_price
        self.position.pnl = pnl
        self.position.pnl_percent = pnl_percent
        self.position.commission += close_commission
        self.position.exit_reason = reason
        
        self.trades.append(self.position)
        
        # 更新连续统计
        if pnl > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)
        
        self.position = None
    
    def _calculate_result(self) -> BacktestResult:
        """计算回测结果"""
        result = BacktestResult()
        result.trades = self.trades
        result.equity_curve = self.equity_curve
        
        if not self.trades:
            return result
        
        # 基础统计
        result.total_trades = len(self.trades)
        result.winning_trades = len([t for t in self.trades if t.pnl > 0])
        result.losing_trades = len([t for t in self.trades if t.pnl < 0])
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # 盈亏统计
        pnls = [t.pnl for t in self.trades]
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        
        result.total_pnl = sum(pnls)
        result.total_commission = sum(t.commission for t in self.trades)
        result.net_pnl = result.total_pnl - result.total_commission
        result.avg_pnl = result.total_pnl / result.total_trades
        result.avg_win = sum(wins) / len(wins) if wins else 0
        result.avg_loss = sum(losses) / len(losses) if losses else 0
        result.profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float('inf')
        
        # 回撤
        result.max_drawdown = self.max_drawdown
        
        # 收益率
        result.total_return = (self.balance - self.initial_balance) / self.initial_balance
        
        # 年化收益（假设250个交易日）
        if self.equity_curve:
            days = (self.equity_curve[-1]['time'] - self.equity_curve[0]['time']).days
            if days > 0:
                result.annual_return = result.total_return * (365 / days)
        
        # Sharpe Ratio
        if len(pnls) > 1:
            returns = pd.Series([t.pnl_percent for t in self.trades])
            result.sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Sortino Ratio（只考虑下行风险）
        if losses:
            downside_returns = pd.Series([t.pnl_percent for t in self.trades if t.pnl < 0])
            downside_std = downside_returns.std()
            if downside_std > 0:
                avg_return = pd.Series([t.pnl_percent for t in self.trades]).mean()
                result.sortino_ratio = avg_return / downside_std * np.sqrt(252)
        
        # Calmar Ratio
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annual_return / result.max_drawdown
        
        # 交易持续时间
        durations = []
        for t in self.trades:
            if t.exit_time and t.entry_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 3600  # 小时
                durations.append(duration)
        result.avg_trade_duration = sum(durations) / len(durations) if durations else 0
        
        # 连续统计
        result.max_consecutive_wins = self.max_consecutive_wins
        result.max_consecutive_losses = self.max_consecutive_losses
        
        # 月度收益
        for trade in self.trades:
            month_key = trade.entry_time.strftime("%Y-%m")
            if month_key not in result.monthly_returns:
                result.monthly_returns[month_key] = 0
            result.monthly_returns[month_key] += trade.pnl
        
        return result
    
    def _print_result(self, result: BacktestResult):
        """打印回测结果"""
        print("\n" + "=" * 60)
        print("回测结果")
        print("=" * 60)
        
        print(f"\n{'基础统计':=^56}")
        print(f"总交易次数: {result.total_trades}")
        print(f"盈利次数: {result.winning_trades}")
        print(f"亏损次数: {result.losing_trades}")
        print(f"胜率: {result.win_rate:.2%}")
        
        print(f"\n{'盈亏统计':=^56}")
        print(f"总盈亏: {result.total_pnl:.2f} USDT")
        print(f"总手续费: {result.total_commission:.2f} USDT")
        print(f"净盈亏: {result.net_pnl:.2f} USDT")
        print(f"平均盈亏: {result.avg_pnl:.2f} USDT")
        print(f"平均盈利: {result.avg_win:.2f} USDT")
        print(f"平均亏损: {result.avg_loss:.2f} USDT")
        print(f"盈亏比: {result.profit_factor:.2f}")
        
        print(f"\n{'收益统计':=^56}")
        print(f"总收益率: {result.total_return:.2%}")
        print(f"年化收益率: {result.annual_return:.2%}")
        print(f"最大回撤: {result.max_drawdown:.2%}")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {result.sortino_ratio:.2f}")
        print(f"Calmar Ratio: {result.calmar_ratio:.2f}")
        
        print(f"\n{'交易统计':=^56}")
        print(f"平均持仓时间: {result.avg_trade_duration:.1f} 小时")
        print(f"最大连胜: {result.max_consecutive_wins}")
        print(f"最大连亏: {result.max_consecutive_losses}")
        
        print(f"\n{'月度收益':=^56}")
        for month, pnl in sorted(result.monthly_returns.items()):
            print(f"  {month}: {pnl:+.2f} USDT")
        
        print("\n" + "=" * 60)
    
    def plot_equity_curve(self, save_path: str = None):
        """绘制权益曲线"""
        if not self.equity_curve:
            print("无权益数据")
            return
        
        df = pd.DataFrame(self.equity_curve)
        df.set_index('time', inplace=True)
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
        
        # 权益曲线
        axes[0].plot(df.index, df['equity'], label='Equity', color='blue')
        axes[0].axhline(y=self.initial_balance, color='gray', linestyle='--', label='Initial Balance')
        axes[0].set_ylabel('Equity (USDT)')
        axes[0].legend()
        axes[0].set_title('Equity Curve')
        axes[0].grid(True, alpha=0.3)
        
        # 回撤曲线
        peak = df['equity'].expanding().max()
        drawdown = (peak - df['equity']) / peak * 100
        axes[1].fill_between(df.index, drawdown, color='red', alpha=0.3)
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].set_title('Drawdown')
        axes[1].grid(True, alpha=0.3)
        
        # 交易标记
        for trade in self.trades:
            color = 'green' if trade.pnl > 0 else 'red'
            marker = '^' if trade.side == 'long' else 'v'
            axes[2].scatter(trade.entry_time, trade.entry_price, color=color, marker=marker, s=50)
        
        axes[2].set_ylabel('Price')
        axes[2].set_title('Trade Entries')
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150)
            print(f"图表已保存: {save_path}")
        else:
            plt.show()
    
    def export_trades(self, path: str):
        """导出交易记录"""
        if not self.trades:
            print("无交易记录")
            return
        
        data = []
        for t in self.trades:
            data.append({
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'side': t.side,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'amount': t.amount,
                'pnl': t.pnl,
                'pnl_percent': t.pnl_percent,
                'commission': t.commission,
                'strategy': t.strategy,
                'exit_reason': t.exit_reason,
            })
        
        df = pd.DataFrame(data)
        df.to_csv(path, index=False)
        print(f"交易记录已导出: {path}")


# ==================== 策略对比 ====================

def compare_strategies(
    df: pd.DataFrame,
    strategies: List[str],
    **kwargs
) -> Dict[str, BacktestResult]:
    """对比不同策略的回测结果"""
    results = {}
    
    for strategy in strategies:
        print(f"\n{'='*60}")
        print(f"回测策略: {strategy}")
        print('='*60)
        
        backtester = Backtester(df, **kwargs)
        result = backtester.run(strategies=[strategy], verbose=True)
        results[strategy] = result
    
    # 打印对比表
    print("\n" + "=" * 80)
    print("策略对比")
    print("=" * 80)
    print(f"{'策略':<20} {'交易数':>8} {'胜率':>8} {'总收益':>12} {'最大回撤':>10} {'Sharpe':>8}")
    print("-" * 80)
    
    for name, r in results.items():
        print(f"{name:<20} {r.total_trades:>8} {r.win_rate:>7.1%} "
              f"{r.total_return:>11.1%} {r.max_drawdown:>9.1%} {r.sharpe_ratio:>8.2f}")
    
    return results


# ==================== 参数优化（简化版）====================

def optimize_parameters(
    df: pd.DataFrame,
    strategy: str,
    param_grid: Dict[str, List],
    **kwargs
) -> List[Dict]:
    """
    参数优化
    param_grid 示例: {'RSI_PERIOD': [10, 14, 20], 'RSI_OVERSOLD': [25, 30, 35]}
    """
    from itertools import product
    
    # 生成参数组合
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(product(*values))
    
    results = []
    total = len(combinations)
    
    print(f"开始参数优化: {total} 种组合")
    
    for i, combo in enumerate(combinations):
        # 设置参数
        params = dict(zip(keys, combo))
        for key, value in params.items():
            setattr(config, key, value)
        
        # 运行回测
        backtester = Backtester(df, **kwargs)
        result = backtester.run(strategies=[strategy], verbose=False)
        
        results.append({
            'params': params,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'total_trades': result.total_trades,
        })
        
        if (i + 1) % 10 == 0:
            print(f"进度: {i+1}/{total}")
    
    # 按 Sharpe Ratio 排序
    results.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
    
    # 打印前10个结果
    print("\n" + "=" * 80)
    print("参数优化结果 (Top 10)")
    print("=" * 80)
    
    for i, r in enumerate(results[:10]):
        print(f"\n{i+1}. Sharpe={r['sharpe_ratio']:.2f}, "
              f"Return={r['total_return']:.1%}, "
              f"MaxDD={r['max_drawdown']:.1%}")
        print(f"   参数: {r['params']}")
    
    return results


# ==================== 主函数 ====================

def main():
    """回测示例"""
    import ccxt
    
    # 获取历史数据
    print("获取历史数据...")
    exchange = ccxt.binance()
    
    ohlcv = exchange.fetch_ohlcv(
        'BTC/USDT',
        timeframe='15m',
        limit=1000
    )
    
    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    print(f"获取到 {len(df)} 根K线")
    
    # 运行单策略回测
    print("\n运行单策略回测...")
    backtester = Backtester(df, initial_balance=10000)
    result = backtester.run(
        strategies=['macd_cross'],
        verbose=True
    )
    
    # 绘制权益曲线
    backtester.plot_equity_curve(save_path='backtest_equity.png')
    
    # 导出交易记录
    backtester.export_trades('backtest_trades.csv')
    
    # 策略对比
    print("\n运行策略对比...")
    compare_strategies(
        df,
        strategies=['macd_cross', 'ema_cross', 'bollinger_breakthrough'],
        initial_balance=10000
    )


if __name__ == "__main__":
    main()

