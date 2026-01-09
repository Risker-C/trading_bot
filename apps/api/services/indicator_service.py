from datetime import datetime
from typing import List, Optional

from logger_utils import get_logger

from apps.api.models.indicator import Indicator
from apps.api.services.trade_service import TradeService


class IndicatorService:
    """Expose derived indicator set for dashboards."""

    def __init__(self, trade_service: Optional[TradeService] = None):
        self.trade_service = trade_service or TradeService()
        self.logger = get_logger(__name__)

    async def get_active_indicators(self) -> List[Indicator]:
        summary = await self.trade_service.get_summary()
        now = datetime.utcnow()
        return [
            Indicator(
                name="Win Rate",
                value=round(summary.win_rate, 2),
                signal=self._score(summary.win_rate, 40, 55),
                metadata={"unit": "%", "thresholds": {"warning": 40, "optimal": 55}},
                updated_at=now,
            ),
            Indicator(
                name="Profit Factor",
                value=round(summary.profit_factor, 2),
                signal=self._score(summary.profit_factor, 1, 1.5),
                metadata={"unit": "ratio"},
                updated_at=now,
            ),
            Indicator(
                name="Average PnL",
                value=round(summary.avg_pnl, 4),
                signal="positive" if summary.avg_pnl >= 0 else "negative",
                metadata={"unit": "USDT"},
                updated_at=now,
            ),
            Indicator(
                name="Trade Velocity",
                value=summary.total_trades,
                signal=self._score(summary.total_trades, 10, 30),
                metadata={"unit": "trades"},
                updated_at=now,
            ),
        ]

    @staticmethod
    def _score(value: float, warning_threshold: float, optimal_threshold: float) -> str:
        if value >= optimal_threshold:
            return "strong"
        if value >= warning_threshold:
            return "stable"
        return "weak"
