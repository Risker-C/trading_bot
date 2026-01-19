"""
Backtest Engine - Core backtesting logic
"""
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from backtest.repository import BacktestRepository
from backtest.summary_repository import SummaryRepository


class BacktestEngine:
    """Core backtesting engine"""

    def __init__(self, repo: BacktestRepository):
        self.repo = repo

    def run(self, session_id: str, klines: pd.DataFrame, strategy_name: str, initial_capital: float = 10000.0):
        """
        Run backtest on historical data

        Args:
            session_id: Backtest session ID
            klines: DataFrame with OHLCV data
            strategy_name: Strategy name to use
            initial_capital: Starting capital
        """
        from strategies.strategies import get_strategy

        try:
            self.repo.update_session_status(session_id, "running")

            cash = initial_capital
            position = None
            position_open_trade_id = None  # 记录开仓交易ID

            # 使用累加器代替列表，避免内存累积
            trade_count = 0
            win_count = 0
            win_pnl_sum = 0.0
            total_pnl = 0.0

            for i in range(50, len(klines)):
                window = klines.iloc[i-50:i+1]
                current_bar = klines.iloc[i]

                strategy = get_strategy(strategy_name, window)

                try:
                    # 如果有持仓，先检查是否需要平仓
                    if position is not None:
                        exit_signal = strategy.check_exit(position['side'])

                        if exit_signal and exit_signal.signal.value in ['close_long', 'close_short']:
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
                                'strategy_name': exit_signal.strategy,
                                'reason': exit_signal.reason,
                                'open_trade_id': position_open_trade_id  # 关联开仓交易ID
                            }
                            self.repo.append_trade(session_id, trade)

                            # 更新累加器
                            trade_count += 1
                            total_pnl += pnl
                            if pnl > 0:
                                win_count += 1
                                win_pnl_sum += pnl

                            position = None
                            position_open_trade_id = None
                            continue

                    # 如果没有持仓，检查是否有开仓信号
                    if position is None:
                        signal = strategy.analyze()

                        if signal and signal.signal.value in ['long', 'short']:
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
                                'strategy_name': signal.strategy,
                                'reason': signal.reason
                            }
                            trade_id = self.repo.append_trade(session_id, trade)
                            position_open_trade_id = trade_id  # 保存开仓交易ID
                            trade_count += 1
                finally:
                    # 及时释放对象引用
                    strategy = None
                    window = None
                    current_bar = None

            metrics = {
                'total_trades': trade_count,
                'win_rate': win_count / trade_count if trade_count else 0,
                'total_pnl': total_pnl,
                'total_return': (total_pnl / initial_capital) * 100,
                'max_drawdown': 0,
                'sharpe': 0,
                'profit_factor': 1.0,
                'expectancy': total_pnl / trade_count if trade_count else 0,
                'avg_win': win_pnl_sum / win_count if win_count else 0,
                'avg_loss': 0,
                'start_ts': int(klines.index[0].timestamp()),
                'end_ts': int(klines.index[-1].timestamp())
            }

            self.repo.upsert_metrics(session_id, metrics)
            self.repo.update_session_status(session_id, "completed")

            # Update summary table for history list
            try:
                summary_repo = SummaryRepository(self.repo.db_path)
                summary_repo.upsert_from_session(session_id)
            except Exception as e:
                # Log but don't fail the backtest if summary update fails
                print(f"Warning: Failed to update summary for session {session_id}: {e}")

        except Exception as e:
            self.repo.update_session_status(session_id, "failed", str(e))
            raise
