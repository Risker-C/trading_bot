"""
流式回放引擎 - 支持实时数据流模拟交易
"""
import asyncio
from typing import Dict, Any, Optional, Callable
import pandas as pd
from datetime import datetime


class ReplayEngine:
    """流式回放引擎"""

    def __init__(self, speed_multiplier: float = 1.0):
        """
        Args:
            speed_multiplier: 回放速度倍数（1.0=实时，2.0=2倍速）
        """
        self.speed_multiplier = speed_multiplier
        self.is_running = False
        self.is_paused = False

    async def replay(
        self,
        klines: pd.DataFrame,
        strategy_name: str,
        initial_capital: float = 10000.0,
        on_tick: Optional[Callable] = None,
        on_trade: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        流式回放K线数据

        Args:
            klines: K线数据
            strategy_name: 策略名称
            initial_capital: 初始资金
            on_tick: K线回调函数
            on_trade: 交易回调函数

        Returns:
            回放结果
        """
        from strategies.strategies import get_strategy

        self.is_running = True
        cash = initial_capital
        position = None
        trades = []
        equity_curve = [initial_capital]

        try:
            for i in range(50, len(klines)):
                if not self.is_running:
                    break

                # 暂停控制
                while self.is_paused and self.is_running:
                    await asyncio.sleep(0.1)

                window = klines.iloc[i-50:i+1]
                current_bar = klines.iloc[i]

                # 触发tick回调
                if on_tick:
                    await on_tick({
                        'timestamp': int(current_bar.name.timestamp()),
                        'price': current_bar['close'],
                        'volume': current_bar['volume'],
                        'equity': cash
                    })

                # 生成信号
                strategy = get_strategy(strategy_name, window)
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
                            'side': signal.signal.value,
                            'action': 'open',
                            'price': current_bar['close'],
                            'qty': qty,
                            'fee': fee
                        }
                        trades.append(trade)

                        # 触发交易回调
                        if on_trade:
                            await on_trade(trade)

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
                            'side': position['side'],
                            'action': 'close',
                            'price': current_bar['close'],
                            'qty': position['qty'],
                            'fee': close_fee,
                            'pnl': net_pnl  # 净盈亏（已扣除所有手续费）
                        }
                        trades.append(trade)
                        position = None

                        # 触发交易回调
                        if on_trade:
                            await on_trade(trade)

                # 更新权益
                current_equity = cash
                if position:
                    unrealized_pnl = (current_bar['close'] - position['entry_price']) * position['qty']
                    if position['side'] == 'short':
                        unrealized_pnl = -unrealized_pnl
                    current_equity += unrealized_pnl

                equity_curve.append(current_equity)

                # 速度控制（模拟时间流逝）
                if self.speed_multiplier > 0:
                    await asyncio.sleep(0.1 / self.speed_multiplier)

            return {
                'status': 'completed' if self.is_running else 'stopped',
                'trades': trades,
                'equity_curve': equity_curve,
                'final_equity': cash
            }

        finally:
            self.is_running = False

    def pause(self):
        """暂停回放"""
        self.is_paused = True

    def resume(self):
        """恢复回放"""
        self.is_paused = False

    def stop(self):
        """停止回放"""
        self.is_running = False
        self.is_paused = False
