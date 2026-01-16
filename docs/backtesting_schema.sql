-- Backtest database schema for backtest.db
-- Connection settings (apply per connection):
-- PRAGMA journal_mode=WAL;
-- PRAGMA busy_timeout=5000;
-- PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS backtest_sessions (
    id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    status TEXT NOT NULL,            -- created|running|stopped|completed|failed
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,         -- 1m|5m|15m|30m|1h|4h|1d
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    initial_capital REAL NOT NULL,
    fee_rate REAL NOT NULL,
    slippage_bps REAL NOT NULL,
    leverage REAL NOT NULL DEFAULT 1.0,
    strategy_name TEXT NOT NULL,
    strategy_params TEXT NOT NULL,   -- JSON
    notes TEXT,
    error_message TEXT
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_klines_session_ts
ON backtest_klines(session_id, ts);

CREATE TABLE IF NOT EXISTS backtest_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    event_type TEXT NOT NULL,        -- signal|order|info
    side TEXT,                       -- buy|sell|close
    price REAL,
    strategy_name TEXT,
    reason TEXT,
    confidence REAL,
    indicators_json TEXT,            -- JSON
    raw_payload_json TEXT,           -- JSON
    trade_id INTEGER,
    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_events_session_ts
ON backtest_events(session_id, ts);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,              -- long|short
    action TEXT NOT NULL,            -- open|close|reduce
    qty REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL DEFAULT 0,
    fee_asset TEXT,
    pnl REAL DEFAULT 0,
    pnl_pct REAL DEFAULT 0,
    strategy_name TEXT,
    reason TEXT,
    event_id INTEGER,
    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id),
    FOREIGN KEY (event_id) REFERENCES backtest_events(id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_session_ts
ON backtest_trades(session_id, ts);

CREATE TABLE IF NOT EXISTS backtest_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,              -- long|short
    entry_ts INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_ts INTEGER,
    exit_price REAL,
    qty REAL NOT NULL,
    max_runup REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    status TEXT NOT NULL,            -- open|closed
    strategy_name TEXT,
    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_positions_session_status
ON backtest_positions(session_id, status);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    session_id TEXT PRIMARY KEY,
    total_trades INTEGER NOT NULL,
    win_rate REAL NOT NULL,
    total_pnl REAL NOT NULL,
    total_return REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    sharpe REAL NOT NULL,
    profit_factor REAL NOT NULL,
    expectancy REAL NOT NULL,
    avg_win REAL NOT NULL,
    avg_loss REAL NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    equity REAL NOT NULL,
    balance REAL NOT NULL,
    drawdown REAL NOT NULL,
    peak_equity REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_session_ts
ON backtest_equity_curve(session_id, ts);
