"""
场景识别服务 - 识别市场状态（趋势市/震荡市）
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any


class ScenarioAnalyzer:
    """场景分析器"""

    @staticmethod
    def detect_market_state(klines: pd.DataFrame) -> str:
        """
        检测市场状态

        Args:
            klines: K线数据

        Returns:
            市场状态: 'trending' | 'ranging' | 'volatile'
        """
        if len(klines) < 20:
            return 'unknown'

        # 计算ADX（平均趋向指标）
        adx = ScenarioAnalyzer._calculate_adx(klines)

        # 计算波动率
        volatility = ScenarioAnalyzer._calculate_volatility(klines)

        # 判断市场状态
        if adx > 25:
            return 'trending'  # 趋势市
        elif volatility > 0.03:
            return 'volatile'  # 高波动
        else:
            return 'ranging'   # 震荡市

    @staticmethod
    def analyze_by_scenario(
        trades: List[Dict[str, Any]],
        klines: pd.DataFrame,
        window_size: int = 100
    ) -> Dict[str, Dict[str, Any]]:
        """
        按场景分析回测结果

        Args:
            trades: 交易记录
            klines: K线数据
            window_size: 场景窗口大小

        Returns:
            各场景的指标统计
        """
        scenarios = {'trending': [], 'ranging': [], 'volatile': []}

        # 将交易按场景分类
        for trade in trades:
            if trade.get('action') != 'close':
                continue

            # 找到交易时的K线位置
            trade_ts = trade['ts']
            idx = klines.index.searchsorted(pd.Timestamp(trade_ts, unit='s'))

            if idx < window_size:
                continue

            # 获取交易前的窗口数据
            window = klines.iloc[idx - window_size:idx]
            state = ScenarioAnalyzer.detect_market_state(window)

            scenarios[state].append(trade)

        # 计算各场景的统计指标
        results = {}
        for state, state_trades in scenarios.items():
            if not state_trades:
                results[state] = {
                    'count': 0,
                    'win_rate': 0,
                    'avg_pnl': 0,
                    'total_pnl': 0
                }
                continue

            winning = [t for t in state_trades if t.get('pnl', 0) > 0]
            total_pnl = sum(t.get('pnl', 0) for t in state_trades)

            results[state] = {
                'count': len(state_trades),
                'win_rate': len(winning) / len(state_trades),
                'avg_pnl': total_pnl / len(state_trades),
                'total_pnl': total_pnl
            }

        return results

    @staticmethod
    def _calculate_adx(klines: pd.DataFrame, period: int = 14) -> float:
        """计算ADX指标"""
        high = klines['high'].values
        low = klines['low'].values
        close = klines['close'].values

        # 计算+DM和-DM
        plus_dm = np.maximum(high[1:] - high[:-1], 0)
        minus_dm = np.maximum(low[:-1] - low[1:], 0)

        # 计算TR
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # 平滑
        if len(tr) < period:
            return 0

        atr = np.mean(tr[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr > 0 else 0

        # 计算ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0

        return dx

    @staticmethod
    def _calculate_volatility(klines: pd.DataFrame, period: int = 20) -> float:
        """计算波动率"""
        returns = klines['close'].pct_change().dropna()
        if len(returns) < period:
            return 0
        return float(returns.tail(period).std())
