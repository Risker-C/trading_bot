"""
Backtest Engine - Core backtesting logic
"""
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from backtest.repository import BacktestRepository
from backtest.repository_factory import get_summary_repository


class BacktestEngine:
    """Core backtesting engine"""

    def __init__(self, repo: BacktestRepository):
        self.repo = repo

    def run(self, session_id: str, klines: pd.DataFrame, strategy_name: str,
            initial_capital: float = 10000.0, strategy_params: Optional[Dict] = None):
        """
        Run backtest on historical data

        Args:
            session_id: Backtest session ID
            klines: DataFrame with OHLCV data
            strategy_name: Strategy name to use (单策略模式)
            initial_capital: Starting capital
            strategy_params: Strategy parameters (支持多策略配置)
        """
        from strategies.strategies import get_strategy, get_weighted_signal

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

            # 判断是否为多策略模式
            is_multi_strategy = strategy_params and strategy_params.get("strategies")
            weighted_threshold = strategy_params.get("threshold", 0.30) if strategy_params else 0.30
            is_band_limited = (strategy_name == "band_limited_hedging") and not is_multi_strategy

            if is_band_limited:
                metrics = self._run_band_limited(
                    session_id=session_id,
                    klines=klines,
                    strategy_params=strategy_params,
                    initial_capital=initial_capital
                )
                self.repo.upsert_metrics(session_id, metrics)
                self.repo.update_session_status(session_id, "completed")

                try:
                    summary_db_path = getattr(self.repo, "db_path", None)
                    summary_repo = get_summary_repository(db_path=summary_db_path)
                    summary_repo.upsert_from_session(session_id)
                except Exception as e:
                    print(f"Warning: Failed to update summary for session {session_id}: {e}")
                return

            for i in range(50, len(klines)):
                window = klines.iloc[i-50:i+1]
                current_bar = klines.iloc[i]

                try:
                    # 生成信号：多策略加权 or 单策略
                    if is_multi_strategy:
                        signal = get_weighted_signal(
                            window,
                            strategy_params["strategies"],
                            threshold=weighted_threshold
                        )
                    else:
                        strategy = get_strategy(strategy_name, window)
                        signal = strategy.analyze()

                    # 如果有持仓，先检查是否需要平仓
                    if position is not None:
                        # 多策略模式：使用反向信号判断平仓
                        # 单策略模式：使用 check_exit
                        should_exit = False
                        exit_reason = ""

                        if is_multi_strategy:
                            # 多策略：当反向信号强度超过阈值时平仓
                            if signal and signal.signal.value in ['long', 'short']:
                                if (position['side'] == 'long' and signal.signal.value == 'short') or \
                                   (position['side'] == 'short' and signal.signal.value == 'long'):
                                    should_exit = True
                                    exit_reason = f"反向信号触发平仓: {signal.reason}"
                        else:
                            # 单策略：使用原有的 check_exit 逻辑
                            exit_signal = strategy.check_exit(position['side'])
                            if exit_signal and exit_signal.signal.value in ['close_long', 'close_short']:
                                should_exit = True
                                exit_reason = exit_signal.reason

                        if should_exit:
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
                                'strategy_name': signal.strategy if signal else strategy_name,
                                'reason': exit_reason,
                                'open_trade_id': position_open_trade_id
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
                    if position is None and signal:
                        if signal.signal.value in ['long', 'short']:
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
                            position_open_trade_id = trade_id
                            trade_count += 1
                finally:
                    # 及时释放对象引用
                    if not is_multi_strategy:
                        strategy = None
                    signal = None
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
                summary_db_path = getattr(self.repo, "db_path", None)
                summary_repo = get_summary_repository(db_path=summary_db_path)
                summary_repo.upsert_from_session(session_id)
            except Exception as e:
                # Log but don't fail the backtest if summary update fails
                print(f"Warning: Failed to update summary for session {session_id}: {e}")

        except Exception as e:
            self.repo.update_session_status(session_id, "failed", str(e))
            raise

    def _run_band_limited(
        self,
        session_id: str,
        klines: pd.DataFrame,
        strategy_params: Optional[Dict],
        initial_capital: float
    ) -> Dict:
        from strategies.strategies import get_strategy

        params = dict(strategy_params or {})
        params.setdefault("initial_capital", initial_capital)

        trade_count = 0
        win_count = 0
        win_pnl_sum = 0.0
        total_pnl = 0.0

        open_trade_ids: Dict[str, List[int]] = {"long": [], "short": []}
        strategy = get_strategy("band_limited_hedging", klines.iloc[0:51], **params)

        for i in range(50, len(klines)):
            window = klines.iloc[i-50:i+1]
            current_bar = klines.iloc[i]

            try:
                if hasattr(strategy, "update_window"):
                    strategy.update_window(window)
                else:
                    strategy.df = window
                signal = strategy.analyze()
                actions = []
                if signal and isinstance(signal.indicators, dict):
                    actions = signal.indicators.get("actions", []) or []

                for action in actions:
                    qty = float(action.get("qty", 0))
                    if qty <= 0:
                        continue

                    side = action.get("side", "")
                    price = float(action.get("price", current_bar["close"]))
                    fee = float(action.get("fee", 0.0))
                    gross_pnl = float(action.get("pnl", 0.0))
                    net_pnl = gross_pnl - fee

                    trade = {
                        "ts": int(current_bar.name.timestamp()),
                        "symbol": "BTC/USDT:USDT",
                        "side": side,
                        "action": action.get("action", "open"),
                        "qty": qty,
                        "price": price,
                        "fee": fee,
                        "strategy_name": "band_limited_hedging",
                        "reason": action.get("reason", signal.reason if signal else "")
                    }

                    if trade["action"] == "open":
                        trade_id = self.repo.append_trade(session_id, trade)
                        open_trade_ids[side].append(trade_id)
                        total_pnl -= fee
                    else:
                        trade["pnl"] = net_pnl
                        trade["pnl_pct"] = (net_pnl / initial_capital) * 100
                        open_list = open_trade_ids.get(side, [])
                        trade["open_trade_id"] = open_list.pop(0) if open_list else None
                        self.repo.append_trade(session_id, trade)

                        total_pnl += net_pnl
                        if net_pnl > 0:
                            win_count += 1
                            win_pnl_sum += net_pnl

                    trade_count += 1
            finally:
                signal = None
                window = None
                current_bar = None

        return {
            "total_trades": trade_count,
            "win_rate": win_count / trade_count if trade_count else 0,
            "total_pnl": total_pnl,
            "total_return": (total_pnl / initial_capital) * 100,
            "max_drawdown": 0,
            "sharpe": 0,
            "profit_factor": 1.0,
            "expectancy": total_pnl / trade_count if trade_count else 0,
            "avg_win": win_pnl_sum / win_count if win_count else 0,
            "avg_loss": 0,
            "start_ts": int(klines.index[0].timestamp()),
            "end_ts": int(klines.index[-1].timestamp())
        }
