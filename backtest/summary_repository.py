"""
Backtest Summary Repository - Optimized read model for history list
"""
import sqlite3
from typing import Optional, Dict, List, Tuple
from datetime import datetime


class SummaryRepository:
    """Repository for backtest session summaries (denormalized read model)"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path

    def _get_conn(self):
        """Get database connection with WAL mode"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
        return conn

    def upsert_from_session(self, session_id: str) -> None:
        """
        Create or update summary from session + metrics
        Called after backtest completion
        """
        conn = self._get_conn()
        try:
            # Fetch session data
            session_row = conn.execute(
                "SELECT created_at, status, symbol, timeframe, start_ts, end_ts, strategy_name, strategy_params "
                "FROM backtest_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()

            if not session_row:
                return

            # Fetch metrics data
            metrics_row = conn.execute(
                "SELECT total_trades, win_rate, total_return, max_drawdown, sharpe "
                "FROM backtest_metrics WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            # Build summary record
            now_ts = int(datetime.utcnow().timestamp())
            summary = {
                "session_id": session_id,
                "created_at": session_row[0],
                "updated_at": now_ts,
                "status": session_row[1],
                "symbol": session_row[2],
                "timeframe": session_row[3],
                "start_ts": session_row[4],
                "end_ts": session_row[5],
                "strategy_name": session_row[6],
                "strategy_params": session_row[7],
                "total_trades": metrics_row[0] if metrics_row else None,
                "win_rate": metrics_row[1] if metrics_row else None,
                "total_return": metrics_row[2] if metrics_row else None,
                "max_drawdown": metrics_row[3] if metrics_row else None,
                "sharpe": metrics_row[4] if metrics_row else None,
            }

            # Upsert summary (update all fields to maintain consistency)
            conn.execute("""
                INSERT INTO backtest_session_summaries (
                    session_id, created_at, updated_at, status, symbol, timeframe,
                    start_ts, end_ts, strategy_name, strategy_params,
                    total_trades, win_rate, total_return, max_drawdown, sharpe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    status = excluded.status,
                    symbol = excluded.symbol,
                    timeframe = excluded.timeframe,
                    start_ts = excluded.start_ts,
                    end_ts = excluded.end_ts,
                    strategy_name = excluded.strategy_name,
                    strategy_params = excluded.strategy_params,
                    total_trades = excluded.total_trades,
                    win_rate = excluded.win_rate,
                    total_return = excluded.total_return,
                    max_drawdown = excluded.max_drawdown,
                    sharpe = excluded.sharpe
            """, (
                summary["session_id"], summary["created_at"], summary["updated_at"],
                summary["status"], summary["symbol"], summary["timeframe"],
                summary["start_ts"], summary["end_ts"], summary["strategy_name"],
                summary["strategy_params"], summary["total_trades"], summary["win_rate"],
                summary["total_return"], summary["max_drawdown"], summary["sharpe"]
            ))
            conn.commit()
        finally:
            conn.close()

    # Allowed sort fields (whitelist to prevent SQL injection)
    ALLOWED_SORT_FIELDS = {"created_at", "total_return", "sharpe", "max_drawdown", "win_rate"}

    def list_summaries(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        filters: Optional[Dict] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        List summaries with cursor pagination and filters
        Returns: (summaries, next_cursor)

        Note: Cursor pagination only works correctly with sort_by="created_at"
        For other sort fields, pagination may have inconsistencies
        """
        # Validate sort_by to prevent SQL injection
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by field: {sort_by}. Allowed: {self.ALLOWED_SORT_FIELDS}")

        # Validate sort_dir
        if sort_dir not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_dir: {sort_dir}. Must be 'asc' or 'desc'")

        conn = self._get_conn()
        try:
            sql = "SELECT * FROM backtest_session_summaries WHERE 1=1"
            params = {}

            # Apply filters
            if filters:
                if filters.get("strategy_name"):
                    sql += " AND strategy_name = :strategy_name"
                    params["strategy_name"] = filters["strategy_name"]

                if filters.get("created_at_from"):
                    sql += " AND created_at >= :created_at_from"
                    params["created_at_from"] = filters["created_at_from"]

                if filters.get("created_at_to"):
                    sql += " AND created_at <= :created_at_to"
                    params["created_at_to"] = filters["created_at_to"]

                if filters.get("total_return_min") is not None:
                    sql += " AND total_return >= :total_return_min"
                    params["total_return_min"] = filters["total_return_min"]

                if filters.get("total_return_max") is not None:
                    sql += " AND total_return <= :total_return_max"
                    params["total_return_max"] = filters["total_return_max"]

                if filters.get("sharpe_min") is not None:
                    sql += " AND sharpe >= :sharpe_min"
                    params["sharpe_min"] = filters["sharpe_min"]

                if filters.get("sharpe_max") is not None:
                    sql += " AND sharpe <= :sharpe_max"
                    params["sharpe_max"] = filters["sharpe_max"]

                if filters.get("max_drawdown_min") is not None:
                    sql += " AND max_drawdown >= :max_drawdown_min"
                    params["max_drawdown_min"] = filters["max_drawdown_min"]

                if filters.get("max_drawdown_max") is not None:
                    sql += " AND max_drawdown <= :max_drawdown_max"
                    params["max_drawdown_max"] = filters["max_drawdown_max"]

                if filters.get("win_rate_min") is not None:
                    sql += " AND win_rate >= :win_rate_min"
                    params["win_rate_min"] = filters["win_rate_min"]

                if filters.get("win_rate_max") is not None:
                    sql += " AND win_rate <= :win_rate_max"
                    params["win_rate_max"] = filters["win_rate_max"]

            # Apply cursor pagination
            if cursor:
                try:
                    cursor_created_at, cursor_id = cursor.split(":")
                    if sort_dir == "desc":
                        sql += " AND (created_at < :cursor_created_at OR (created_at = :cursor_created_at AND session_id < :cursor_id))"
                    else:
                        sql += " AND (created_at > :cursor_created_at OR (created_at = :cursor_created_at AND session_id > :cursor_id))"
                    params["cursor_created_at"] = int(cursor_created_at)
                    params["cursor_id"] = cursor_id
                except ValueError:
                    pass  # Invalid cursor, ignore

            # Apply sorting
            sql += f" ORDER BY {sort_by} {sort_dir}, session_id {sort_dir} LIMIT :limit"
            params["limit"] = limit + 1  # Fetch one extra to determine if there's a next page

            # Execute query
            cursor_obj = conn.execute(sql, params)
            rows = cursor_obj.fetchall()

            # Parse results
            columns = [desc[0] for desc in cursor_obj.description]
            summaries = []
            for row in rows[:limit]:  # Only return requested limit
                summaries.append(dict(zip(columns, row)))

            # Determine next cursor
            next_cursor = None
            if len(rows) > limit:
                last_row = summaries[-1]
                next_cursor = f"{last_row['created_at']}:{last_row['session_id']}"

            return summaries, next_cursor
        finally:
            conn.close()

    def get_summary(self, session_id: str) -> Optional[Dict]:
        """Get single summary by session_id"""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM backtest_session_summaries WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        finally:
            conn.close()
