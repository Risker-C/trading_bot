-- Supabase Schema for Backtest System
-- Generated: 2026-01-21
-- Migration from SQLite to PostgreSQL

-- ============================================
-- Core Backtest Tables
-- ============================================

CREATE TABLE IF NOT EXISTS backtest_sessions (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  updated_at bigint NOT NULL,
  status text NOT NULL,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  initial_capital double precision NOT NULL,
  fee_rate double precision NOT NULL,
  slippage_bps double precision NOT NULL,
  leverage double precision NOT NULL DEFAULT 1.0,
  strategy_name text NOT NULL,
  strategy_params text NOT NULL,
  notes text,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON backtest_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_strategy ON backtest_sessions(strategy_name);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_klines (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  open double precision NOT NULL,
  high double precision NOT NULL,
  low double precision NOT NULL,
  close double precision NOT NULL,
  volume double precision NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_klines_session_ts
ON backtest_klines(session_id, ts);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_events (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  event_type text NOT NULL,
  side text,
  price double precision,
  strategy_name text,
  reason text,
  confidence double precision,
  indicators_json text,
  raw_payload_json text,
  trade_id bigint
);

CREATE INDEX IF NOT EXISTS idx_backtest_events_session_ts
ON backtest_events(session_id, ts);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_trades (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  symbol text NOT NULL,
  side text NOT NULL,
  action text NOT NULL,
  qty double precision NOT NULL,
  price double precision NOT NULL,
  fee double precision DEFAULT 0,
  fee_asset text,
  pnl double precision DEFAULT 0,
  pnl_pct double precision DEFAULT 0,
  strategy_name text,
  reason text,
  event_id bigint REFERENCES backtest_events(id),
  open_trade_id bigint
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_session_ts
ON backtest_trades(session_id, ts);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_positions (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  symbol text NOT NULL,
  side text NOT NULL,
  entry_ts bigint NOT NULL,
  entry_price double precision NOT NULL,
  exit_ts bigint,
  exit_price double precision,
  qty double precision NOT NULL,
  max_runup double precision DEFAULT 0,
  max_drawdown double precision DEFAULT 0,
  realized_pnl double precision DEFAULT 0,
  unrealized_pnl double precision DEFAULT 0,
  status text NOT NULL,
  strategy_name text
);

CREATE INDEX IF NOT EXISTS idx_backtest_positions_session_status
ON backtest_positions(session_id, status);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_metrics (
  session_id text PRIMARY KEY REFERENCES backtest_sessions(id),
  total_trades bigint NOT NULL,
  win_rate double precision NOT NULL,
  total_pnl double precision NOT NULL,
  total_return double precision NOT NULL,
  max_drawdown double precision NOT NULL,
  sharpe double precision NOT NULL,
  profit_factor double precision NOT NULL,
  expectancy double precision NOT NULL,
  avg_win double precision NOT NULL,
  avg_loss double precision NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_return ON backtest_metrics(total_return);
CREATE INDEX IF NOT EXISTS idx_metrics_sharpe ON backtest_metrics(sharpe);
CREATE INDEX IF NOT EXISTS idx_metrics_drawdown ON backtest_metrics(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_metrics_winrate ON backtest_metrics(win_rate);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_equity_curve (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  equity double precision NOT NULL,
  balance double precision NOT NULL,
  drawdown double precision NOT NULL,
  peak_equity double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_session_ts
ON backtest_equity_curve(session_id, ts);

-- ============================================
-- Strategy and Optimization Tables
-- ============================================

CREATE TABLE IF NOT EXISTS strategy_versions (
  id text PRIMARY KEY,
  name text NOT NULL,
  version text NOT NULL,
  params_schema text NOT NULL,
  code_hash text NOT NULL,
  created_at bigint NOT NULL,
  UNIQUE (name, version)
);

-- ============================================

CREATE TABLE IF NOT EXISTS parameter_sets (
  id text PRIMARY KEY,
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  params text NOT NULL,
  source text NOT NULL,
  created_at bigint NOT NULL
);

-- ============================================

CREATE TABLE IF NOT EXISTS kline_datasets (
  id text PRIMARY KEY,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  checksum text NOT NULL,
  data bytea NOT NULL,
  created_at bigint NOT NULL,
  UNIQUE (symbol, timeframe, start_ts, end_ts)
);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_runs (
  id text PRIMARY KEY,
  kline_dataset_id text NOT NULL REFERENCES kline_datasets(id),
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  param_set_id text REFERENCES parameter_sets(id),
  filter_set text,
  status text NOT NULL,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON backtest_runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON backtest_runs(strategy_version_id);

-- ============================================

CREATE TABLE IF NOT EXISTS optimization_jobs (
  id text PRIMARY KEY,
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  kline_dataset_id text NOT NULL REFERENCES kline_datasets(id),
  algorithm text NOT NULL,
  search_space text NOT NULL,
  status text NOT NULL,
  created_at bigint NOT NULL
);

-- ============================================

CREATE TABLE IF NOT EXISTS optimization_results (
  id text PRIMARY KEY,
  job_id text NOT NULL REFERENCES optimization_jobs(id),
  param_set_id text NOT NULL REFERENCES parameter_sets(id),
  run_id text NOT NULL REFERENCES backtest_runs(id),
  rank bigint,
  score double precision,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opt_results_job_rank ON optimization_results(job_id, rank);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_reports (
  id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES backtest_runs(id),
  summary text NOT NULL,
  recommendations text NOT NULL,
  created_at bigint NOT NULL
);

-- ============================================
-- History, AI, and Change Management Tables
-- ============================================

CREATE TABLE IF NOT EXISTS backtest_session_summaries (
  session_id text PRIMARY KEY,
  created_at bigint NOT NULL,
  updated_at bigint NOT NULL,
  status text NOT NULL,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  strategy_name text NOT NULL,
  strategy_params text,
  total_trades bigint,
  win_rate double precision,
  total_return double precision,
  max_drawdown double precision,
  sharpe double precision
);

CREATE INDEX IF NOT EXISTS idx_summary_created_at ON backtest_session_summaries(created_at);
CREATE INDEX IF NOT EXISTS idx_summary_strategy ON backtest_session_summaries(strategy_name);
CREATE INDEX IF NOT EXISTS idx_summary_return ON backtest_session_summaries(total_return);
CREATE INDEX IF NOT EXISTS idx_summary_sharpe ON backtest_session_summaries(sharpe);
CREATE INDEX IF NOT EXISTS idx_summary_drawdown ON backtest_session_summaries(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_summary_winrate ON backtest_session_summaries(win_rate);
CREATE INDEX IF NOT EXISTS idx_summary_cursor ON backtest_session_summaries(created_at, session_id);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_ai_reports (
  id text PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  created_at bigint NOT NULL,
  model_name text NOT NULL,
  prompt_version text NOT NULL,
  input_digest text NOT NULL,
  summary text NOT NULL,
  strengths text,
  weaknesses text,
  recommendations text,
  param_suggestions text,
  compare_group_id text
);

CREATE INDEX IF NOT EXISTS idx_ai_session ON backtest_ai_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_group ON backtest_ai_reports(compare_group_id);
CREATE INDEX IF NOT EXISTS idx_ai_created_at ON backtest_ai_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_session_created ON backtest_ai_reports(session_id, created_at);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_change_requests (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  created_by text NOT NULL,
  status text NOT NULL,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  strategy_name text NOT NULL,
  target_env text NOT NULL,
  change_payload text NOT NULL,
  change_description text,
  approved_by text,
  approved_at bigint,
  applied_by text,
  applied_at bigint,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_cr_status ON backtest_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_cr_env ON backtest_change_requests(target_env);
CREATE INDEX IF NOT EXISTS idx_cr_created_at ON backtest_change_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_cr_session ON backtest_change_requests(session_id);

-- ============================================

CREATE TABLE IF NOT EXISTS backtest_audit_logs (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  actor text NOT NULL,
  action text NOT NULL,
  target_type text NOT NULL,
  target_id text NOT NULL,
  payload text,
  ip_address text,
  user_agent text
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON backtest_audit_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON backtest_audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON backtest_audit_logs(actor);

-- ============================================
-- Row Level Security (RLS) - All Access Policy
-- ============================================

-- Enable RLS on all tables
ALTER TABLE backtest_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_klines ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_equity_curve ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE parameter_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE kline_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE optimization_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_session_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_ai_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_change_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_audit_logs ENABLE ROW LEVEL SECURITY;

-- Create all-access policies (no permission isolation as per requirements)
CREATE POLICY "Allow all access" ON backtest_sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_klines FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_trades FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_positions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_metrics FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_equity_curve FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON strategy_versions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON parameter_sets FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON kline_datasets FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_runs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON optimization_jobs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON optimization_results FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_reports FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_session_summaries FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_ai_reports FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_change_requests FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_audit_logs FOR ALL USING (true) WITH CHECK (true);

-- ============================================
-- Completion
-- ============================================

-- This schema includes:
-- - 18 tables (7 core + 7 strategy/optimization + 4 history/AI)
-- - All necessary indexes for query performance
-- - Foreign key constraints for data integrity
-- - RLS policies for security (all-access per requirements)
