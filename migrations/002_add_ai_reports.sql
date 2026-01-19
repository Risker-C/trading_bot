-- Migration: Add backtest_ai_reports table
-- Purpose: Store AI analysis results for backtest sessions
-- Date: 2026-01-19

BEGIN;

-- Create AI reports table
CREATE TABLE IF NOT EXISTS backtest_ai_reports (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_digest TEXT NOT NULL,
  summary TEXT NOT NULL,
  strengths TEXT,
  weaknesses TEXT,
  recommendations TEXT,
  param_suggestions TEXT,
  compare_group_id TEXT,
  FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

-- Create indexes for AI reports
CREATE INDEX IF NOT EXISTS idx_ai_session ON backtest_ai_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_group ON backtest_ai_reports(compare_group_id);
CREATE INDEX IF NOT EXISTS idx_ai_created_at ON backtest_ai_reports(created_at);

COMMIT;
