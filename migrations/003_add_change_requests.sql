-- Migration: Add change request and audit log tables
-- Purpose: Support approval workflow and audit trail for production changes
-- Date: 2026-01-19

BEGIN;

-- Create change requests table
CREATE TABLE IF NOT EXISTS backtest_change_requests (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  status TEXT NOT NULL,  -- pending/approved/rejected/applied/failed
  session_id TEXT NOT NULL,
  strategy_name TEXT NOT NULL,
  target_env TEXT NOT NULL,  -- staging/prod
  change_payload TEXT NOT NULL,  -- JSON with old and new config
  change_description TEXT,
  approved_by TEXT,
  approved_at INTEGER,
  applied_by TEXT,
  applied_at INTEGER,
  error_message TEXT,
  FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

-- Create audit logs table
CREATE TABLE IF NOT EXISTS backtest_audit_logs (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  payload TEXT,
  ip_address TEXT,
  user_agent TEXT
);

-- Create indexes for change requests
CREATE INDEX IF NOT EXISTS idx_cr_status ON backtest_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_cr_env ON backtest_change_requests(target_env);
CREATE INDEX IF NOT EXISTS idx_cr_created_at ON backtest_change_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_cr_session ON backtest_change_requests(session_id);

-- Create indexes for audit logs
CREATE INDEX IF NOT EXISTS idx_audit_target ON backtest_audit_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON backtest_audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON backtest_audit_logs(actor);

COMMIT;
