-- ============================================================
-- Live Trading Database Schema for Supabase
-- Migrated from SQLite (trading_bot.db)
-- Tables prefixed with 'live_' to distinguish from backtest data
-- ============================================================

-- 1. 交易记录表 (live_trades)
CREATE TABLE IF NOT EXISTS live_trades (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT,
    symbol TEXT,
    side TEXT,
    action TEXT,
    amount DOUBLE PRECISION,
    price DOUBLE PRECISION,
    value_usdt DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    pnl_percent DOUBLE PRECISION,
    strategy TEXT,
    reason TEXT,
    status TEXT,
    filled_price DOUBLE PRECISION,
    filled_time TIMESTAMPTZ,
    fee DOUBLE PRECISION,
    fee_currency TEXT,
    batch_number INTEGER,
    remaining_amount DOUBLE PRECISION,
    leverage INTEGER,
    margin_mode TEXT,
    position_side TEXT,
    order_type TEXT,
    reduce_only BOOLEAN,
    trade_side TEXT,
    created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_live_trades_created_at ON live_trades(created_at);
CREATE INDEX IF NOT EXISTS idx_live_trades_strategy ON live_trades(strategy);
CREATE INDEX IF NOT EXISTS idx_live_trades_symbol ON live_trades(symbol);

-- RLS
ALTER TABLE live_trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access on live_trades" ON live_trades FOR ALL USING (true) WITH CHECK (true);

-- 2. 策略信号表 (live_signals)
CREATE TABLE IF NOT EXISTS live_signals (
    id BIGSERIAL PRIMARY KEY,
    strategy TEXT,
    signal TEXT,
    reason TEXT,
    strength DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    indicators JSONB,
    created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_live_signals_created_at ON live_signals(created_at);
CREATE INDEX IF NOT EXISTS idx_live_signals_strategy ON live_signals(strategy);

-- RLS
ALTER TABLE live_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access on live_signals" ON live_signals FOR ALL USING (true) WITH CHECK (true);

-- 3. 持仓快照表 (live_position_snapshots)
CREATE TABLE IF NOT EXISTS live_position_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT,
    side TEXT,
    amount DOUBLE PRECISION,
    entry_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    leverage INTEGER,
    highest_price DOUBLE PRECISION,
    lowest_price DOUBLE PRECISION,
    entry_time BIGINT,
    margin_mode TEXT,
    liquidation_price DOUBLE PRECISION,
    margin_ratio DOUBLE PRECISION,
    mark_price DOUBLE PRECISION,
    notional DOUBLE PRECISION,
    initial_margin DOUBLE PRECISION,
    maintenance_margin DOUBLE PRECISION,
    created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_live_position_snapshots_created_at ON live_position_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_live_position_snapshots_symbol ON live_position_snapshots(symbol);

-- RLS
ALTER TABLE live_position_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access on live_position_snapshots" ON live_position_snapshots FOR ALL USING (true) WITH CHECK (true);

-- 4. 账户余额快照表 (live_balance_snapshots)
CREATE TABLE IF NOT EXISTS live_balance_snapshots (
    id BIGSERIAL PRIMARY KEY,
    total DOUBLE PRECISION,
    free DOUBLE PRECISION,
    used DOUBLE PRECISION,
    created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_live_balance_snapshots_created_at ON live_balance_snapshots(created_at);

-- RLS
ALTER TABLE live_balance_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access on live_balance_snapshots" ON live_balance_snapshots FOR ALL USING (true) WITH CHECK (true);

-- 6. 风控事件表 (live_risk_events)
CREATE TABLE IF NOT EXISTS live_risk_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT,
    description TEXT,
    current_price DOUBLE PRECISION,
    trigger_price DOUBLE PRECISION,
    position_side TEXT,
    created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_live_risk_events_created_at ON live_risk_events(created_at);
CREATE INDEX IF NOT EXISTS idx_live_risk_events_event_type ON live_risk_events(event_type);

-- RLS
ALTER TABLE live_risk_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access on live_risk_events" ON live_risk_events FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- Verification Query (run after creation)
-- ============================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name LIKE 'live_%';
