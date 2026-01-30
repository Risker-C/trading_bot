# Remove Unused Tables and Enhance Position Tracking

## Context

### User Need
根据数据库使用情况分析报告（`docs/database_usage_analysis.md`），需要：
1. **删除未使用的数据库表**：`equity_curve`, `daily_stats`, `risk_metrics`（功能未实现，无实际用途）
2. **增强仓位变化记录**：确保记录 Bitget 接口返回的所有详细信息，包括开仓价格、仓位信息、手续费、杠杆、保证金模式等

### Current State
- **已使用的表**: `trades` (0条，功能已实现), `signals` (61条), `position_snapshots` (0条，功能已实现), `balance_snapshots` (11条), `risk_events` (0条，功能已实现)
- **未使用的表**: `equity_curve`, `daily_stats`, `risk_metrics`（功能未实现，需要删除）
- **trades 表现状**: 已有 `filled_price`, `filled_time`, `fee`, `fee_currency` 等字段，但可能缺少其他 Bitget 返回的详细信息
- **position_snapshots 表现状**: 只记录基本持仓信息，缺少 `leverage`, `margin_mode`, `liquidation_price` 等详细信息
- **当前数据库模式**: Supabase（`USE_SUPABASE_FOR_LIVE_DATA = True`）

### Discovered Constraints

**Hard Constraints:**
1. 必须同时修改 SQLite 和 Supabase 的表结构
2. 必须保持向后兼容（已有数据不能丢失）
3. 删除表时必须同时删除相关的代码调用
4. 增强表结构时必须使用 ALTER TABLE 添加新字段
5. 必须更新 `TradeDatabase` 和 `SupabaseTradeDatabase` 两个类
6. 必须确保 Bitget 接口返回的所有有用信息都被记录

**Soft Constraints:**
1. 新增字段应设置默认值或允许 NULL，避免影响现有代码
2. 删除未使用的表后，应清理相关的测试代码
3. 增强后的记录功能应在代码注释中说明字段含义

**Dependencies:**
1. 依赖 Bitget API 返回的数据结构
2. 依赖 `utils/logger_utils.py` 和 `utils/supabase_trade_database.py`
3. 依赖 `scripts/live_trading_supabase_schema.sql`
4. 依赖 `core/trader.py` 中的交易执行逻辑

**Risks:**
1. 删除表可能影响现有的测试脚本 → 需要清理测试代码
2. 修改表结构可能导致数据迁移问题 → 使用 ALTER TABLE 添加字段
3. Bitget API 返回的字段可能变化 → 使用灵活的字段设计

## Proposed Solution

### High-Level Approach
1. **删除未使用的表**：
   - 从 SQLite schema 中删除 `equity_curve`, `daily_stats`, `risk_metrics`
   - 从 Supabase schema 中删除对应的 `live_equity_curve`, `live_daily_stats`, `live_risk_metrics`
   - 从 `TradeDatabase` 和 `SupabaseTradeDatabase` 中删除相关方法
   - 清理测试脚本中的相关代码

2. **增强 trades 表**：
   - 分析 Bitget `fetch_order()` 返回的完整数据结构
   - 添加缺失的字段（如 `leverage`, `margin_mode`, `position_side` 等）
   - 更新 `log_trade()` 和 `log_trade_buffered()` 方法

3. **增强 position_snapshots 表**：
   - 添加详细字段：`leverage`, `margin_mode`, `liquidation_price`, `margin_ratio`, `available`, `frozen` 等
   - 更新 `log_position_snapshot()` 方法
   - 确保从 Bitget `get_positions()` 获取的所有有用信息都被记录

### Key Design Decisions
1. **删除策略**: 直接删除表和相关代码，不保留任何残留
2. **字段添加策略**: 使用 ALTER TABLE 添加新字段，设置默认值或允许 NULL
3. **数据来源**: 从 Bitget API 返回的 `raw_data` 中提取详细信息

## Scope

### In Scope
- 删除 `equity_curve`, `daily_stats`, `risk_metrics` 表（SQLite + Supabase）
- 删除相关的数据库方法和测试代码
- 分析 Bitget API 返回的数据结构
- 增强 `trades` 表结构和记录逻辑
- 增强 `position_snapshots` 表结构和记录逻辑
- 更新数据库 schema 文件
- 创建数据迁移脚本（ALTER TABLE）

### Out of Scope
- 修改其他表的结构
- 实现新的数据分析功能
- 修改前端展示逻辑
- 优化查询性能

## Success Criteria
1. `equity_curve`, `daily_stats`, `risk_metrics` 表已从 SQLite 和 Supabase 中删除
2. 相关的数据库方法和测试代码已清理
3. `trades` 表包含所有 Bitget 订单返回的有用信息
4. `position_snapshots` 表包含所有 Bitget 持仓返回的详细信息
5. 现有代码正常运行，不受影响
6. 数据迁移脚本可以成功执行（添加新字段）

## Resolved Questions (User Decisions)
1. **删除哪些表**: `equity_curve`, `daily_stats`, `risk_metrics`
2. **仓位记录方式**: 同时增强 `trades` 和 `position_snapshots` 表

## Status
- [x] 提案创建
- [x] 用户确认需求
- [ ] 等待批准执行
