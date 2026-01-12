import asyncio
import sqlite3
from datetime import datetime
from typing import List, Optional

from logger_utils import TradeDatabase, get_logger

from apps.api.models.trade import Trade, TradeHistoryResponse, TradeSummary


class TradeService:
    """Read-only helper around TradeDatabase with async helpers."""

    def __init__(self, db: Optional[TradeDatabase] = None):
        self.db = db or TradeDatabase()
        self.logger = get_logger(__name__)
        self._ensure_wal_mode()

    def _ensure_wal_mode(self) -> None:
        try:
            conn = sqlite3.connect(self.db.db_file)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.close()
        except sqlite3.Error as exc:
            self.logger.warning("Failed to enable SQLite WAL mode: %s", exc)

    async def list_trades(self, limit: int = 50, offset: int = 0) -> List[Trade]:
        rows = await asyncio.to_thread(self.db.get_trades, limit, offset)
        return [self._to_trade(row) for row in rows]

    async def get_trade_by_id(self, trade_id: int) -> Optional[Trade]:
        """根据 ID 获取单个交易详情"""
        row = await asyncio.to_thread(self.db.get_trade_by_id, trade_id)
        return self._to_trade(row) if row else None

    async def get_summary(self) -> TradeSummary:
        stats = await asyncio.to_thread(self.db.get_statistics)
        return TradeSummary(**stats)

    async def get_history(self, limit: int = 100) -> TradeHistoryResponse:
        recent_task = asyncio.create_task(self.list_trades(limit=limit))
        today_task = asyncio.create_task(self._get_today_trades())
        pnl_task = asyncio.create_task(self._get_today_pnl())
        summary_task = asyncio.create_task(self.get_summary())

        recent_trades = await recent_task
        today_trades = await today_task
        today_pnl = await pnl_task
        summary = await summary_task

        return TradeHistoryResponse(
            today_pnl=today_pnl,
            today_trades=today_trades,
            recent_trades=recent_trades,
            summary=summary,
        )

    async def _get_today_trades(self) -> List[Trade]:
        rows = await asyncio.to_thread(self.db.get_today_trades)
        return [self._to_trade(row) for row in rows]

    async def _get_today_pnl(self) -> float:
        value = await asyncio.to_thread(self.db.get_today_pnl)
        return float(value or 0)

    def _to_trade(self, raw: dict) -> Trade:
        data = dict(raw)
        data["created_at"] = self._parse_datetime(data.get("created_at"))
        filled_time = data.get("filled_time")
        if filled_time:
            data["filled_time"] = self._parse_datetime(filled_time)
        return Trade(**data)

    @staticmethod
    def _parse_datetime(value) -> datetime:
        if not value:
            return datetime.utcnow()
        if isinstance(value, datetime):
            return value
        text_value = str(value)
        for candidate in (text_value, text_value.replace(" ", "T")):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        try:
            return datetime.strptime(text_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.utcnow()
