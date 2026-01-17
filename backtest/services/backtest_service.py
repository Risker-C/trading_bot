"""
统一回测服务 - 整合现有功能并实现完整指标计算
"""
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime

from backtest.domain.interfaces import IDataRepository, IFeatureCache
from backtest.services.metrics_calculator import MetricsCalculator


class BacktestService:
    """统一回测服务"""

    def __init__(
        self,
        repo: IDataRepository,
        cache: IFeatureCache
    ):
        self.repo = repo
        self.cache = cache
        self.metrics_calc = MetricsCalculator()

    async def run_backtest(
        self,
        run_id: str,
        klines: pd.DataFrame,
        strategy_name: str,
        strategy_params: Optional[Dict[str, Any]] = None,
        initial_capital: float = 10000.0
    ) -> Dict[str, Any]:
        """
        运行回测

        Args:
            run_id: 回测运行ID
            klines: K线数据
            strategy_name: 策略名称
            strategy_params: 策略参数
            initial_capital: 初始资金

        Returns:
            回测结果（包含指标和权益曲线）
        """
        from strategies.strategies import get_strategy

        try:
            await self.repo.update_run_status(run_id, "running")

            cash = initial_capital
            position = None
            trades = []
            equity_curve = [initial_capital]

            # 回测循环
            for i in range(50, len(klines)):
                window = klines.iloc[i-50:i+1]
                current_bar = klines.iloc[i]

                # 生成信号（传递策略参数）
                strategy = get_strategy(strategy_name, window, **(strategy_params or {}))
                signal = strategy.analyze()

                # 开仓
                if signal and signal.signal.value in ['long', 'short']:
                    if position is None:
                        # 计算可开仓数量（使用95%资金，合约模式）
                        available_cash = cash * 0.95
                        qty = available_cash / current_bar['close']
                        position_value = qty * current_bar['close']
                        fee = position_value * 0.001

                        position = {
                            'side': signal.signal.value,
                            'entry_price': current_bar['close'],
                            'entry_ts': int(current_bar.name.timestamp()),
                            'qty': qty,
                            'entry_fee': fee  # 记录开仓手续费
                        }

                        # 合约模式：只扣除手续费
                        cash -= fee

                        trade = {
                            'ts': int(current_bar.name.timestamp()),
                            'symbol': 'BTC/USDT:USDT',
                            'side': signal.signal.value,
                            'action': 'open',
                            'qty': qty,
                            'price': current_bar['close'],
                            'fee': fee,
                            'strategy_name': signal.strategy,
                            'reason': signal.reason
                        }
                        trades.append(trade)

                # 平仓
                elif signal and signal.signal.value in ['close_long', 'close_short']:
                    if position:
                        # 验证平仓信号与持仓方向匹配
                        if (signal.signal.value == 'close_long' and position['side'] != 'long') or \
                           (signal.signal.value == 'close_short' and position['side'] != 'short'):
                            continue

                        # 计算持仓价值和平仓手续费
                        position_value = position['qty'] * current_bar['close']
                        close_fee = position_value * 0.001

                        # 计算盈亏（合约模式）
                        pnl = (current_bar['close'] - position['entry_price']) * position['qty']
                        if position['side'] == 'short':
                            pnl = -pnl

                        # 扣除开仓和平仓手续费
                        total_fee = position['entry_fee'] + close_fee
                        net_pnl = pnl - total_fee

                        # 合约模式：加回净盈亏
                        cash += net_pnl

                        trade = {
                            'ts': int(current_bar.name.timestamp()),
                            'symbol': 'BTC/USDT:USDT',
                            'side': position['side'],
                            'action': 'close',
                            'qty': position['qty'],
                            'price': current_bar['close'],
                            'fee': close_fee,
                            'pnl': net_pnl,  # 净盈亏（已扣除所有手续费）
                            'pnl_pct': (net_pnl / initial_capital) * 100,
                            'strategy_name': signal.strategy,
                            'reason': signal.reason
                        }
                        trades.append(trade)
                        position = None

                # 更新权益曲线
                current_equity = cash
                if position:
                    unrealized_pnl = (current_bar['close'] - position['entry_price']) * position['qty']
                    if position['side'] == 'short':
                        unrealized_pnl = -unrealized_pnl
                    current_equity += unrealized_pnl

                equity_curve.append(current_equity)

            # 计算完整指标
            metrics = self.metrics_calc.calculate_all_metrics(
                trades, equity_curve, initial_capital
            )

            # 保存指标
            await self.repo.save_metrics(run_id, metrics)
            await self.repo.update_run_status(run_id, "completed")

            return {
                'run_id': run_id,
                'status': 'completed',
                'metrics': metrics,
                'equity_curve': equity_curve,
                'trades': trades
            }

        except Exception as e:
            await self.repo.update_run_status(run_id, "failed")
            raise
