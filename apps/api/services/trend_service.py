import asyncio
from datetime import datetime
from typing import List, Optional

import config
from logger_utils import get_logger

from apps.api.models.trend import Trend
from apps.api.services.trade_service import TradeService


class TrendService:
    """Derive lightweight market trend heuristics from recent trades."""

    def __init__(self, trade_service: Optional[TradeService] = None):
        self.trade_service = trade_service or TradeService()
        self.symbol = getattr(config, "SYMBOL", "BTCUSDT")
        self.timeframe = getattr(config, "TIMEFRAME", "15m")
        self.logger = get_logger(__name__)

    async def latest_trend(self) -> Trend:
        trades = await self.trade_service.list_trades(limit=60)
        prices = [trade.price for trade in reversed(trades) if trade.price]

        if not prices:
            return self._empty_trend()

        change = prices[-1] - prices[0]
        change_pct = (change / prices[0]) * 100 if prices[0] else 0
        direction = self._resolve_direction(change_pct)
        momentum = self._calculate_momentum(prices)
        volatility = self._calculate_volatility(prices)
        average_price = sum(prices) / len(prices)

        return Trend(
            symbol=self.symbol,
            timeframe=self.timeframe,
            direction=direction,
            change_percent=round(change_pct, 4),
            momentum=round(momentum, 6),
            volatility=round(volatility, 6),
            average_price=round(average_price, 2),
            support=min(prices),
            resistance=max(prices),
            sample_size=len(prices),
            updated_at=datetime.utcnow(),
        )

    async def get_trend_history(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Trend]:
        """
        获取趋势历史数据（基于历史交易记录的简化实现）

        注意：由于没有存储历史趋势快照，此方法返回基于历史交易的简化趋势数据
        """
        # 获取历史交易记录
        trades = await self.trade_service.list_trades(limit=limit * 60, offset=offset)

        if not trades:
            return []

        # 按60条交易为一组，计算每组的趋势
        trends = []
        chunk_size = 60

        for i in range(0, len(trades), chunk_size):
            chunk = trades[i:i + chunk_size]
            if len(chunk) < 10:  # 至少需要10条交易才能计算趋势
                continue

            prices = [trade.price for trade in reversed(chunk) if trade.price]
            if not prices:
                continue

            change = prices[-1] - prices[0]
            change_pct = (change / prices[0]) * 100 if prices[0] else 0
            direction = self._resolve_direction(change_pct)
            momentum = self._calculate_momentum(prices)
            volatility = self._calculate_volatility(prices)
            average_price = sum(prices) / len(prices)

            # 使用该组最后一条交易的时间作为趋势时间
            updated_at = chunk[0].created_at if chunk else datetime.utcnow()

            trend = Trend(
                symbol=self.symbol,
                timeframe=self.timeframe,
                direction=direction,
                change_percent=round(change_pct, 4),
                momentum=round(momentum, 6),
                volatility=round(volatility, 6),
                average_price=round(average_price, 2),
                support=min(prices),
                resistance=max(prices),
                sample_size=len(prices),
                updated_at=updated_at,
            )
            trends.append(trend)

            if len(trends) >= limit:
                break

        return trends

    def _empty_trend(self) -> Trend:
        return Trend(
            symbol=self.symbol,
            timeframe=self.timeframe,
            direction="neutral",
            change_percent=0,
            momentum=0,
            volatility=0,
            average_price=None,
            support=None,
            resistance=None,
            sample_size=0,
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def _calculate_momentum(prices: List[float]) -> float:
        if len(prices) < 2:
            return 0
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        return sum(deltas) / len(deltas)

    @staticmethod
    def _calculate_volatility(prices: List[float]) -> float:
        if len(prices) < 2:
            return 0
        avg_price = sum(prices) / len(prices)
        variance = sum((price - avg_price) ** 2 for price in prices) / len(prices)
        return (variance ** 0.5) / avg_price * 100 if avg_price else 0

    @staticmethod
    def _resolve_direction(change_pct: float) -> str:
        if change_pct > 0.2:
            return "bullish"
        if change_pct < -0.2:
            return "bearish"
        return "neutral"
