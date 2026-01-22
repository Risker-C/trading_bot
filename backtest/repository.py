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
        conn = self._get_conn()

        # Check if tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_sessions'")
        tables_exist = cursor.fetchone() is not None

        if tables_exist:
            # Run migrations for existing database
            self._run_migrations(conn)
            conn.close()
            return

        # Try to load schema from file
        schema_path = Path(__file__).parent.parent / "docs" / "backtesting_schema.sql"
        if schema_path.exists():
            with open(schema_path) as f:
                schema_sql = f.read()
            conn.executescript(schema_sql)
        else:
            # Fallback: create tables inline
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS backtest_sessions (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    start_ts INTEGER NOT NULL,
                    end_ts INTEGER NOT NULL,
                    initial_capital REAL NOT NULL,
                    fee_rate REAL DEFAULT 0.001,
                    slippage_bps INTEGER DEFAULT 5,
                    leverage REAL DEFAULT 1.0,
                    strategy_name TEXT NOT NULL,
                    strategy_params TEXT,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS backtest_metrics (
                    session_id TEXT PRIMARY KEY,
                    total_trades INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    total_return REAL,
                    max_drawdown REAL,
                    sharpe REAL,
                    profit_factor REAL,
                    expectancy REAL,
                    avg_win REAL,
                    avg_loss REAL,
                    start_ts INTEGER,
                    end_ts INTEGER,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    action TEXT NOT NULL,
                    qty REAL NOT NULL,
                    price REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    pnl REAL,
                    pnl_pct REAL,
                    strategy_name TEXT,
                    reason TEXT,
                    open_trade_id INTEGER,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS backtest_klines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS backtest_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS backtest_equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    equity REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );

                CREATE TABLE IF NOT EXISTS backtest_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT,
                    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
                );
            """)

        conn.commit()
        conn.close()

    def _run_migrations(self, conn):
        """Run database migrations for schema updates"""
        # Migration 1: Add open_trade_id column to backtest_trades
        try:
            cursor = conn.execute("PRAGMA table_info(backtest_trades)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'open_trade_id' not in columns:
                conn.execute("ALTER TABLE backtest_trades ADD COLUMN open_trade_id INTEGER")
                conn.commit()
                print("Migration: Added open_trade_id column to backtest_trades")
        except Exception as e:
            print(f"Migration error: {e}")

    def save_klines(self, session_id: str, klines: List[Dict]):
        """Save kline data for a session"""
        conn = self._get_conn()
        conn.executemany("""
            INSERT INTO backtest_klines (
                session_id, ts, open, high, low, close, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                session_id, k['ts'], k['open'], k['high'],
                k['low'], k['close'], k['volume']
            ) for k in klines
        ])
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
                fee, pnl, pnl_pct, strategy_name, reason, open_trade_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, trade['ts'], trade['symbol'],
            trade['side'], trade['action'], trade['qty'], trade['price'],
            trade.get('fee', 0), trade.get('pnl', 0), trade.get('pnl_pct', 0),
            trade.get('strategy_name'), trade.get('reason'), trade.get('open_trade_id')
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

    def get_session(self, session_id: str) -> Dict:
        """Get session by ID"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        columns = [col[0] for col in cursor.description]
        conn.close()
        return dict(zip(columns, row))

    def get_metrics(self, session_id: str) -> Dict:
        """Get metrics by session_id"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_metrics WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        columns = [col[0] for col in cursor.description]
        conn.close()
        return dict(zip(columns, row))

    def get_trades(
        self,
        session_id: str,
        limit: Optional[int] = None,
        desc: bool = False
    ) -> List[Dict]:
        """Get trades for a session"""
        conn = self._get_conn()
        order_dir = "DESC" if desc else "ASC"
        if limit is None:
            cursor = conn.execute(
                f"SELECT * FROM backtest_trades WHERE session_id = ? ORDER BY ts {order_dir}",
                (session_id,)
            )
        else:
            cursor = conn.execute(
                f"SELECT * FROM backtest_trades WHERE session_id = ? ORDER BY ts {order_dir} LIMIT ?",
                (session_id, limit)
            )
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def get_klines(
        self,
        session_id: str,
        limit: Optional[int] = None,
        before: Optional[int] = None
    ) -> List[Dict]:
        """Get klines for a session"""
        conn = self._get_conn()
        params: List = [session_id]
        sql = "SELECT ts, open, high, low, close, volume FROM backtest_klines WHERE session_id = ?"
        if before is not None:
            sql += " AND ts < ?"
            params.append(before)
        sql += " ORDER BY ts ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        cursor = conn.execute(sql, tuple(params))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def get_latest_session(self, statuses: Optional[List[str]] = None) -> Dict:
        """Get latest session by updated_at"""
        conn = self._get_conn()
        sql = "SELECT * FROM backtest_sessions"
        params: List = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            sql += f" WHERE status IN ({placeholders})"
            params.extend(statuses)
        sql += " ORDER BY updated_at DESC LIMIT 1"
        cursor = conn.execute(sql, tuple(params))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {}
        columns = [col[0] for col in cursor.description]
        conn.close()
        return dict(zip(columns, row))
