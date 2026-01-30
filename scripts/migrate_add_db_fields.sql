-- ============================================================
-- Migration Script: Add Enhanced Fields to Live Trading Tables
-- Run this in Supabase Dashboard SQL Editor
-- ============================================================

-- 1. Add new fields to live_trades table
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS leverage INTEGER;
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS margin_mode TEXT;
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS position_side TEXT;
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS order_type TEXT;
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS reduce_only BOOLEAN;
ALTER TABLE live_trades ADD COLUMN IF NOT EXISTS trade_side TEXT;

-- 2. Add new fields to live_position_snapshots table
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS margin_mode TEXT;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS liquidation_price DOUBLE PRECISION;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS margin_ratio DOUBLE PRECISION;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS mark_price DOUBLE PRECISION;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS notional DOUBLE PRECISION;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS initial_margin DOUBLE PRECISION;
ALTER TABLE live_position_snapshots ADD COLUMN IF NOT EXISTS maintenance_margin DOUBLE PRECISION;

-- 3. Drop unused tables (optional - run only if you want to clean up)
-- WARNING: This will permanently delete data in these tables
-- DROP TABLE IF EXISTS live_equity_curve;
-- DROP TABLE IF EXISTS live_daily_stats;
-- DROP TABLE IF EXISTS live_risk_metrics;

-- ============================================================
-- Verification Query
-- ============================================================
-- Run this to verify the migration:
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'live_trades' ORDER BY ordinal_position;
--
-- SELECT column_name, data_type FROM information_schema.columns
-- WHERE table_name = 'live_position_snapshots' ORDER BY ordinal_position;
