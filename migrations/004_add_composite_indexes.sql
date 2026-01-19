-- Migration: Add composite indexes for better query performance
-- Purpose: Optimize cursor pagination and AI report queries
-- Date: 2026-01-19

BEGIN;

-- Composite index for cursor pagination on summaries
CREATE INDEX IF NOT EXISTS idx_summary_cursor ON backtest_session_summaries(created_at, session_id);

-- Composite index for AI report queries by session
CREATE INDEX IF NOT EXISTS idx_ai_session_created ON backtest_ai_reports(session_id, created_at);

COMMIT;
