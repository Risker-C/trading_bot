import pandas as pd
import numpy as np

from strategies.strategies import BandLimitedHedgingStrategy
from backtest.engine import BacktestEngine


def _make_klines(prices):
    df = pd.DataFrame({
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": np.ones(len(prices)),
    })
    df.index = pd.date_range("2020-01-01", periods=len(prices), freq="min")
    return df


def test_band_limited_strategy_mes_hold_and_trigger():
    prices = np.full(60, 100.0)
    df = _make_klines(prices)

    strategy = BandLimitedHedgingStrategy(
        df,
        MES=0.02,
        alpha=0.5,
        E_max=10000,
        initial_capital=10000,
    )

    signal = strategy.analyze()
    actions = signal.indicators.get("actions", [])
    assert len(actions) == 2

    prices_hold = prices.copy()
    prices_hold[-1] = 100.5
    strategy.update_window(_make_klines(prices_hold))
    signal = strategy.analyze()
    actions = signal.indicators.get("actions", [])
    assert actions == []

    prices_trigger = prices.copy()
    prices_trigger[-1] = 103.0
    strategy.update_window(_make_klines(prices_trigger))
    signal = strategy.analyze()
    actions = signal.indicators.get("actions", [])
    assert len(actions) > 0


class _DummyRepo:
    def __init__(self):
        self.trades = []

    def append_trade(self, session_id, trade):
        trade_id = len(self.trades) + 1
        trade["id"] = trade_id
        self.trades.append(trade)
        return trade_id


def test_band_limited_engine_runs():
    prices = np.linspace(100, 110, 80)
    df = _make_klines(prices)

    repo = _DummyRepo()
    engine = BacktestEngine(repo)

    metrics = engine._run_band_limited(
        session_id="test",
        klines=df,
        strategy_params={"MES": 0.02, "alpha": 0.5, "E_max": 10000},
        initial_capital=10000,
    )

    assert metrics["total_trades"] >= 2
    assert len(repo.trades) >= 2
