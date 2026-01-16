"""
Backtest Engine - Core backtesting logic
"""
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from backtest.repository import BacktestRepository


class BacktestEngine:
    """Core backtesting engine"""

    def __init__(self, repo: BacktestRepository):
        self.repo = repo

    def run(self, session_id: str, klines: pd.DataFrame, strategy_func, initial_capital: float = 10000.0):
        """
        Run backtest on historical data

        Args:
            session_id: Backtest session ID
            klines: DataFrame with OHLCV data
            strategy_func: Strategy function that returns signals
            initial_capital: Starting capital
        """
        try:
            self.repo.update_session_status(session_id, "running")

            cash = initial_capital
            position = None
            trades = []

            for i in range(50, len(klines)):
                window = klines.iloc[i-50:i+1]
                current_bar = klines.iloc[i]

                signal = strategy_func(window)

                if signal and signal.signal.value in ['long', 'short']:
                    if position is None:
                        position = {
                            'side': signal.signal.value,
                            'entry_price': current_bar['close'],
                            'entry_ts': int(current_bar.name.timestamp()),
                            'qty': cash * 0.95 / current_bar['close']
                        }

                        trade = {
                            'ts': int(current_bar.name.timestamp()),
                            'symbol': 'BTC/USDT:USDT',
                            'side': signal.signal.value,
                            'action': 'open',
                            'qty': position['qty'],
                            'price': current_bar['close'],
                            'fee': cash * 0.001,
                            'strategy_name': signal.strategy_name,
                            'reason': signal.reason
                        }
                        self.repo.append_trade(session_id, trade)
                        trades.append(trade)

                elif signal and signal.signal.value in ['close_long', 'close_short']:
                    if position:
                        pnl = (current_bar['close'] - position['entry_price']) * position['qty']
                        if position['side'] == 'short':
                            pnl = -pnl

                        cash += pnl

                        trade = {
                            'ts': int(current_bar.name.timestamp()),
                            'symbol': 'BTC/USDT:USDT',
                            'side': position['side'],
                            'action': 'close',
                            'qty': position['qty'],
                            'price': current_bar['close'],
                            'fee': cash * 0.001,
                            'pnl': pnl,
                            'pnl_pct': (pnl / initial_capital) * 100,
                            'strategy_name': signal.strategy_name,
                            'reason': signal.reason
                        }
                        self.repo.append_trade(session_id, trade)
                        trades.append(trade)
                        position = None

            total_pnl = sum(t.get('pnl', 0) for t in trades)
            winning_trades = [t for t in trades if t.get('pnl', 0) > 0]

            metrics = {
                'total_trades': len(trades),
                'win_rate': len(winning_trades) / len(trades) if trades else 0,
                'total_pnl': total_pnl,
                'total_return': (total_pnl / initial_capital) * 100,
                'max_drawdown': 0,
                'sharpe': 0,
                'profit_factor': 1.0,
                'expectancy': total_pnl / len(trades) if trades else 0,
                'avg_win': sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
                'avg_loss': 0,
                'start_ts': int(klines.index[0].timestamp()),
                'end_ts': int(klines.index[-1].timestamp())
            }

            self.repo.upsert_metrics(session_id, metrics)
            self.repo.update_session_status(session_id, "completed")

        except Exception as e:
            self.repo.update_session_status(session_id, "failed", str(e))
            raise
