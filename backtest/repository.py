"""
Backtest Repository - SQLite persistence layer
"""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List


class BacktestRepository:
    """Repository for backtest data persistence"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        """Get database connection with WAL mode"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Initialize database schema"""
        schema_path = Path(__file__).parent.parent / "docs" / "backtesting_schema.sql"
        if not schema_path.exists():
            return

        with open(schema_path) as f:
            schema_sql = f.read()

        conn = self._get_conn()
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()

    def create_session(self, params: Dict) -> str:
        """Create new backtest session"""
        session_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO backtest_sessions (
                id, created_at, updated_at, status, symbol, timeframe,
                start_ts, end_ts, initial_capital, fee_rate, slippage_bps,
                leverage, strategy_name, strategy_params
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, now, now, 'created',
            params['symbol'], params['timeframe'],
            params['start_ts'], params['end_ts'],
            params['initial_capital'], params.get('fee_rate', 0.001),
            params.get('slippage_bps', 5), params.get('leverage', 1.0),
            params['strategy_name'], json.dumps(params.get('strategy_params', {}))
        ))
        conn.commit()
        conn.close()

        return session_id

    def update_session_status(self, session_id: str, status: str, error: str = ""):
        """Update session status"""
        now = int(datetime.utcnow().timestamp())
        conn = self._get_conn()
        conn.execute("""
            UPDATE backtest_sessions
            SET status = ?, updated_at = ?, error_message = ?
            WHERE id = ?
        """, (status, now, error, session_id))
        conn.commit()
        conn.close()

    def append_trade(self, session_id: str, trade: Dict) -> int:
        """Append trade record"""
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT INTO backtest_trades (
                session_id, ts, symbol, side, action, qty, price,
                fee, pnl, pnl_pct, strategy_name, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, trade['ts'], trade['symbol'],
            trade['side'], trade['action'], trade['qty'], trade['price'],
            trade.get('fee', 0), trade.get('pnl', 0), trade.get('pnl_pct', 0),
            trade.get('strategy_name'), trade.get('reason')
        ))
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id

    def upsert_metrics(self, session_id: str, metrics: Dict):
        """Insert or update metrics"""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO backtest_metrics (
                session_id, total_trades, win_rate, total_pnl, total_return,
                max_drawdown, sharpe, profit_factor, expectancy,
                avg_win, avg_loss, start_ts, end_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, metrics['total_trades'], metrics['win_rate'],
            metrics['total_pnl'], metrics['total_return'],
            metrics['max_drawdown'], metrics['sharpe'],
            metrics['profit_factor'], metrics['expectancy'],
            metrics['avg_win'], metrics['avg_loss'],
            metrics['start_ts'], metrics['end_ts']
        ))
        conn.commit()
        conn.close()
