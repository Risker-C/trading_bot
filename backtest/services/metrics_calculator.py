"""
指标计算模块 - 实现完整的10个回测指标
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any


class MetricsCalculator:
    """回测指标计算器"""

    @staticmethod
    def calculate_all_metrics(
        trades: List[Dict[str, Any]],
        equity_curve: List[float],
        initial_capital: float
    ) -> Dict[str, Any]:
        """计算所有回测指标"""

        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'sharpe': 0.0,
                'sortino': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0
            }

        # 基础指标
        total_trades = len([t for t in trades if t.get('action') == 'close'])
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        total_pnl = sum(t.get('pnl', 0) for t in trades)
        total_return = (total_pnl / initial_capital) * 100

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0

        # 平均盈利和亏损
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0.0

        # 盈亏比
        total_win = sum(t['pnl'] for t in winning_trades)
        total_loss = abs(sum(t['pnl'] for t in losing_trades))
        profit_factor = total_win / total_loss if total_loss > 0 else 0.0

        # 单笔期望
        expectancy = total_pnl / total_trades if total_trades > 0 else 0.0

        # 最大回撤
        max_drawdown = MetricsCalculator._calculate_max_drawdown(equity_curve)

        # 夏普比率
        sharpe = MetricsCalculator._calculate_sharpe(equity_curve, initial_capital)

        # 索提诺比率
        sortino = MetricsCalculator._calculate_sortino(equity_curve, initial_capital)

        return {
            'total_trades': total_trades,
            'win_rate': round(win_rate, 4),
            'total_pnl': round(total_pnl, 2),
            'total_return': round(total_return, 2),
            'max_drawdown': round(max_drawdown, 4),
            'sharpe': round(sharpe, 4),
            'sortino': round(sortino, 4),
            'profit_factor': round(profit_factor, 4),
            'expectancy': round(expectancy, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2)
        }

    @staticmethod
    def _calculate_max_drawdown(equity_curve: List[float]) -> float:
        """计算最大回撤"""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max

        return abs(float(np.min(drawdown)))

    @staticmethod
    def _calculate_sharpe(equity_curve: List[float], initial_capital: float) -> float:
        """计算夏普比率（假设无风险利率为0）"""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        # 计算收益率序列
        returns = np.diff(equity_curve) / equity_curve[:-1]

        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # 年化夏普比率（假设每日数据）
        sharpe = (mean_return / std_return) * np.sqrt(252)

        return float(sharpe)

    @staticmethod
    def _calculate_sortino(equity_curve: List[float], initial_capital: float) -> float:
        """计算索提诺比率（仅考虑下行波动）"""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0

        # 计算收益率序列
        returns = np.diff(equity_curve) / equity_curve[:-1]

        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)

        # 仅计算负收益的标准差
        negative_returns = returns[returns < 0]

        if len(negative_returns) == 0:
            return 0.0

        downside_std = np.std(negative_returns)

        if downside_std == 0:
            return 0.0

        # 年化索提诺比率
        sortino = (mean_return / downside_std) * np.sqrt(252)

        return float(sortino)
