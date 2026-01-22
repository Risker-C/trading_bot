"""
Supabase Summary Repository - Optimized read model for history list
"""
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from backtest.adapters.storage.supabase_client import get_supabase_client
from utils.logger_utils import get_logger


class SupabaseSummaryRepository:
    """Repository for backtest session summaries (Supabase 实现)"""

    # Allowed sort fields (whitelist to prevent injection)
    ALLOWED_SORT_FIELDS = {
        "created_at", "updated_at", "total_trades", "win_rate",
        "total_return", "max_drawdown", "sharpe"
    }

    def __init__(self):
        self.client = get_supabase_client()
        self.logger = get_logger("supabase.summary_repo")

    def upsert_from_session(self, session_id: str) -> None:
        """
        Create or update summary from session + metrics
        Called after backtest completion
        """
        # Fetch session data
        start = time.monotonic()
        session_response = self.client.table('backtest_sessions') \
            .select('created_at, status, symbol, timeframe, start_ts, end_ts, strategy_name, strategy_params') \
            .eq('id', session_id) \
            .execute()

        if not session_response.data:
            self.logger.warning("Summary upsert skipped: session not found session_id=%s", session_id)
            return

        session = session_response.data[0]

        # Fetch metrics data
        metrics_response = self.client.table('backtest_metrics') \
            .select('total_trades, win_rate, total_return, max_drawdown, sharpe') \
            .eq('session_id', session_id) \
            .execute()

        metrics = metrics_response.data[0] if metrics_response.data else None

        # Build summary record
        now_ts = int(datetime.utcnow().timestamp())
        summary = {
            "session_id": session_id,
            "created_at": session['created_at'],
            "updated_at": now_ts,
            "status": session['status'],
            "symbol": session['symbol'],
            "timeframe": session['timeframe'],
            "start_ts": session['start_ts'],
            "end_ts": session['end_ts'],
            "strategy_name": session['strategy_name'],
            "strategy_params": session['strategy_params'],
            "total_trades": metrics['total_trades'] if metrics else None,
            "win_rate": metrics['win_rate'] if metrics else None,
            "total_return": metrics['total_return'] if metrics else None,
            "max_drawdown": metrics['max_drawdown'] if metrics else None,
            "sharpe": metrics['sharpe'] if metrics else None,
        }

        # Upsert summary
        self.client.table('backtest_session_summaries').upsert(summary).execute()
        elapsed = time.monotonic() - start
        self.logger.debug(
            "Summary upsert ok session_id=%s elapsed=%.3fs",
            session_id,
            elapsed
        )

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

        Args:
            cursor: Pagination cursor (created_at:session_id)
            limit: Page size
            sort_by: Sort field
            sort_dir: Sort direction (asc/desc)
            filters: Filter dict (strategy_name, created_at_from, etc.)

        Returns:
            (summaries, next_cursor)
        """
        # Validate sort_by
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by: {sort_by}. Allowed: {self.ALLOWED_SORT_FIELDS}")

        # Validate sort_dir
        if sort_dir not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_dir: {sort_dir}")

        # Build query
        query = self.client.table('backtest_session_summaries').select('*')

        # Apply filters
        if filters:
            if 'strategy_name' in filters:
                query = query.eq('strategy_name', filters['strategy_name'])
            if 'created_at_from' in filters:
                query = query.gte('created_at', filters['created_at_from'])
            if 'created_at_to' in filters:
                query = query.lte('created_at', filters['created_at_to'])
            if 'total_return_min' in filters:
                query = query.gte('total_return', filters['total_return_min'])
            if 'total_return_max' in filters:
                query = query.lte('total_return', filters['total_return_max'])
            if 'sharpe_min' in filters:
                query = query.gte('sharpe', filters['sharpe_min'])
            if 'sharpe_max' in filters:
                query = query.lte('sharpe', filters['sharpe_max'])
            if 'win_rate_min' in filters:
                query = query.gte('win_rate', filters['win_rate_min'])
            if 'win_rate_max' in filters:
                query = query.lte('win_rate', filters['win_rate_max'])

        # Cursor pagination
        if cursor:
            try:
                cursor_created_at, cursor_session_id = cursor.split(':')
                cursor_created_at = int(cursor_created_at)

                if sort_dir == 'desc':
                    query = query.lt('created_at', cursor_created_at)
                else:
                    query = query.gt('created_at', cursor_created_at)
            except (ValueError, IndexError):
                raise ValueError(f"Invalid cursor format: {cursor}")

        # Sorting
        query = query.order(sort_by, desc=(sort_dir == 'desc'))
        query = query.order('session_id', desc=(sort_dir == 'desc'))

        # Fetch limit + 1 to determine if there's a next page
        query = query.limit(limit + 1)

        start = time.monotonic()
        response = query.execute()
        elapsed = time.monotonic() - start
        summaries = response.data[:limit]

        # Determine next cursor
        next_cursor = None
        if len(response.data) > limit:
            last = summaries[-1]
            next_cursor = f"{last['created_at']}:{last['session_id']}"

        self.logger.debug(
            "Summary list ok rows=%s limit=%s elapsed=%.3fs",
            len(response.data),
            limit,
            elapsed
        )
        return summaries, next_cursor

    def get_summary(self, session_id: str) -> Optional[Dict]:
        """Get single summary by session_id"""
        start = time.monotonic()
        response = self.client.table('backtest_session_summaries') \
            .select('*') \
            .eq('session_id', session_id) \
            .execute()
        elapsed = time.monotonic() - start
        self.logger.debug(
            "Summary get ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            elapsed
        )

        return response.data[0] if response.data else None
