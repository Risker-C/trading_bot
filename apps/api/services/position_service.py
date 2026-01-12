import asyncio
import sqlite3
from datetime import datetime
from typing import List, Optional

import config
from logger_utils import TradeDatabase, get_logger

from apps.api.models.position import Position


class PositionService:
    """Expose latest position snapshot via async helpers."""

    def __init__(
        self,
        db: Optional[TradeDatabase] = None,
        symbol: Optional[str] = None,
    ):
        self.db = db or TradeDatabase()
        self.symbol = symbol or getattr(config, "SYMBOL", "BTCUSDT")
        self.logger = get_logger(__name__)
        self._ensure_wal_mode()

    def _ensure_wal_mode(self) -> None:
        try:
            conn = sqlite3.connect(self.db.db_file)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.close()
        except sqlite3.Error as exc:
            self.logger.warning("Failed to enable SQLite WAL for positions: %s", exc)

    async def get_current_position(self, symbol: Optional[str] = None) -> Optional[Position]:
        target_symbol = symbol or self.symbol
        snapshot = await asyncio.to_thread(self.db.get_latest_position_snapshot, target_symbol)
        if not snapshot:
            return None

        return Position(
            symbol=snapshot.get("symbol", target_symbol),
            side=snapshot.get("side"),
            amount=float(snapshot.get("amount") or 0),
            entry_price=self._to_float(snapshot.get("entry_price")),
            current_price=self._to_float(snapshot.get("current_price")),
            unrealized_pnl=self._to_float(snapshot.get("unrealized_pnl")),
            leverage=snapshot.get("leverage"),
            highest_price=self._to_float(snapshot.get("highest_price")),
            lowest_price=self._to_float(snapshot.get("lowest_price")),
            entry_time=self._parse_datetime(snapshot.get("entry_time")),
            updated_at=self._parse_datetime(snapshot.get("created_at")),
        )

    async def get_position_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Position]:
        """获取持仓历史快照列表"""
        snapshots = await asyncio.to_thread(
            self.db.get_position_history,
            symbol=symbol,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date
        )

        return [self._snapshot_to_position(snapshot) for snapshot in snapshots]

    def _snapshot_to_position(self, snapshot: dict) -> Position:
        """将快照字典转换为 Position 对象"""
        return Position(
            symbol=snapshot.get("symbol", ""),
            side=snapshot.get("side"),
            amount=float(snapshot.get("amount") or 0),
            entry_price=self._to_float(snapshot.get("entry_price")),
            current_price=self._to_float(snapshot.get("current_price")),
            unrealized_pnl=self._to_float(snapshot.get("unrealized_pnl")),
            leverage=snapshot.get("leverage"),
            highest_price=self._to_float(snapshot.get("highest_price")),
            lowest_price=self._to_float(snapshot.get("lowest_price")),
            entry_time=self._parse_datetime(snapshot.get("entry_time")),
            updated_at=self._parse_datetime(snapshot.get("created_at")),
        )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for candidate in (str(value), str(value).replace(" ", "T")):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    @staticmethod
    def _to_float(value) -> Optional[float]:
        return float(value) if value is not None else None
