-- Migration: Add backtest_session_summaries table and indexes
-- Purpose: Optimize history list queries by creating a denormalized read model
-- Date: 2026-01-19

BEGIN;

-- Create summary table (denormalized sessions + metrics)
CREATE TABLE IF NOT EXISTS backtest_session_summaries (
  session_id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  status TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  start_ts INTEGER NOT NULL,
  end_ts INTEGER NOT NULL,
  strategy_name TEXT NOT NULL,
  strategy_params TEXT,
  total_trades INTEGER,
  win_rate REAL,
  total_return REAL,
  max_drawdown REAL,
  sharpe REAL
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_summary_created_at ON backtest_session_summaries(created_at);
CREATE INDEX IF NOT EXISTS idx_summary_strategy ON backtest_session_summaries(strategy_name);
CREATE INDEX IF NOT EXISTS idx_summary_return ON backtest_session_summaries(total_return);
CREATE INDEX IF NOT EXISTS idx_summary_sharpe ON backtest_session_summaries(sharpe);
CREATE INDEX IF NOT EXISTS idx_summary_drawdown ON backtest_session_summaries(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_summary_winrate ON backtest_session_summaries(win_rate);

-- Add indexes to existing tables for better join performance
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON backtest_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_strategy ON backtest_sessions(strategy_name);
CREATE INDEX IF NOT EXISTS idx_metrics_return ON backtest_metrics(total_return);
CREATE INDEX IF NOT EXISTS idx_metrics_sharpe ON backtest_metrics(sharpe);
CREATE INDEX IF NOT EXISTS idx_metrics_drawdown ON backtest_metrics(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_metrics_winrate ON backtest_metrics(win_rate);

COMMIT;
