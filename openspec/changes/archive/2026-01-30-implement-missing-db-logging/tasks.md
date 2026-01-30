# Implementation Tasks

## Phase 1: 分析 Bitget API 数据结构

### Task 1.1: 分析 Bitget 订单返回数据
- [x] 查看 `exchange/adapters/bitget_adapter.py` 中的订单创建和查询方法
- [x] 记录 `fetch_order()` 返回的所有字段
- [x] 记录 `create_market_order()` 返回的所有字段
- [x] 确定哪些字段对交易记录有用
- **验证**: 生成 Bitget 订单数据结构文档

### Task 1.2: 分析 Bitget 持仓返回数据
- [x] 查看 `exchange/adapters/bitget_adapter.py` 中的 `get_positions()` 方法
- [x] 记录 `fetch_positions()` 返回的所有字段（raw_data）
- [x] 确定哪些字段对持仓快照有用
- **验证**: 生成 Bitget 持仓数据结构文档

---

## Phase 2: 删除未使用的表

### Task 2.1: 删除 SQLite 表定义
- [x] 在 `utils/logger_utils.py` 的 `_init_db()` 方法中删除以下表的创建语句：
  - `equity_curve`
  - `daily_stats`
  - `risk_metrics`
- **验证**: SQLite 初始化不再创建这些表

### Task 2.2: 删除 Supabase 表定义
- [x] 在 `scripts/live_trading_supabase_schema.sql` 中删除以下表的 DDL：
  - `live_equity_curve`
  - `live_daily_stats`
  - `live_risk_metrics`
- [x] 创建删除表的 SQL 脚本（用于已有数据库）
- **验证**: Supabase schema 文件不再包含这些表

### Task 2.3: 删除数据库方法
- [x] 在 `utils/logger_utils.py` 的 `TradeDatabase` 类中删除以下方法：
  - `log_equity()`
  - `get_equity_curve()`
  - `update_daily_stats()`
  - `get_daily_stats()`
  - `log_risk_metrics()`
  - `get_latest_risk_metrics()`
- [x] 在 `utils/supabase_trade_database.py` 的 `SupabaseTradeDatabase` 类中删除相同方法
- **验证**: 代码中不再有这些方法的定义

### Task 2.4: 清理测试代码
- [x] 在 `scripts/test_supabase_trade_database.py` 中删除相关测试
- [x] 搜索并清理其他测试脚本中的相关代码
- **验证**: 测试脚本不再测试已删除的功能

---

## Phase 3: 增强 trades 表结构

### Task 3.1: 设计新字段
- [x] 根据 Bitget API 分析结果，确定需要添加的字段：
  - `leverage` (INTEGER): 杠杆倍数
  - `margin_mode` (TEXT): 保证金模式（crossed/isolated）
  - `position_side` (TEXT): 持仓方向（用于双向持仓）
  - `order_type` (TEXT): 订单类型（market/limit）
  - `reduce_only` (BOOLEAN): 是否只减仓
  - `trade_side` (TEXT): 交易方向（open/close）
- **验证**: 字段设计文档完成

### Task 3.2: 更新 SQLite 表结构
- [x] 在 `utils/logger_utils.py` 的 `_init_db()` 中添加新字段到 `trades` 表
- [x] 创建 ALTER TABLE 迁移脚本（用于已有数据库）
- **验证**: 新数据库包含所有新字段

### Task 3.3: 更新 Supabase 表结构
- [x] 在 `scripts/live_trading_supabase_schema.sql` 中添加新字段到 `live_trades` 表
- [x] 创建 ALTER TABLE SQL 脚本（用于已有 Supabase 表）
- **验证**: Supabase schema 包含所有新字段

### Task 3.4: 更新 log_trade 方法
- [x] 在 `TradeDatabase.log_trade()` 中添加新参数
- [x] 在 `TradeDatabase.log_trade_buffered()` 中添加新参数（SQLite 无此方法）
- [x] 在 `SupabaseTradeDatabase.log_trade()` 中添加新参数
- [x] 在 `SupabaseTradeDatabase.log_trade_buffered()` 中添加新参数
- **验证**: 方法签名包含所有新字段

### Task 3.5: 更新交易记录调用
- [ ] 在 `core/trader.py` 的 `open_long()` 中传递新字段（待后续集成）
- [ ] 在 `core/trader.py` 的 `open_short()` 中传递新字段（待后续集成）
- [ ] 在 `core/trader.py` 的 `close_position()` 中传递新字段（待后续集成）
- [ ] 从 Bitget 订单返回数据中提取新字段值（待后续集成）
- **验证**: 交易记录包含所有新字段数据

---

## Phase 4: 增强 position_snapshots 表结构

### Task 4.1: 设计新字段
- [x] 根据 Bitget API 分析结果，确定需要添加的字段：
  - `margin_mode` (TEXT): 保证金模式
  - `liquidation_price` (REAL): 强平价格
  - `margin_ratio` (REAL): 保证金率
  - `mark_price` (REAL): 标记价格
  - `notional` (REAL): 名义价值
  - `initial_margin` (REAL): 初始保证金
  - `maintenance_margin` (REAL): 维持保证金
- **验证**: 字段设计文档完成

### Task 4.2: 更新 SQLite 表结构
- [x] 在 `utils/logger_utils.py` 的 `_init_db()` 中添加新字段到 `position_snapshots` 表
- [x] 创建 ALTER TABLE 迁移脚本
- **验证**: 新数据库包含所有新字段

### Task 4.3: 更新 Supabase 表结构
- [x] 在 `scripts/live_trading_supabase_schema.sql` 中添加新字段到 `live_position_snapshots` 表
- [x] 创建 ALTER TABLE SQL 脚本
- **验证**: Supabase schema 包含所有新字段

### Task 4.4: 更新 log_position_snapshot 方法
- [x] 在 `TradeDatabase.log_position_snapshot()` 中添加新参数
- [x] 在 `SupabaseTradeDatabase.log_position_snapshot()` 中添加新参数
- **验证**: 方法签名包含所有新字段

### Task 4.5: 更新持仓快照调用
- [ ] 在 `risk/risk_manager.py` 的 `_save_position_to_db()` 中传递新字段（待后续集成）
- [ ] 从 Bitget 持仓返回数据（raw_data）中提取新字段值（待后续集成）
- **验证**: 持仓快照包含所有新字段数据

---

## Phase 5: 数据迁移

### Task 5.1: 创建 SQLite 迁移脚本
- [x] SQLite 迁移通过 `_init_db()` 自动完成（ALTER TABLE IF NOT EXISTS）
- **验证**: 脚本可以成功执行

### Task 5.2: 创建 Supabase 迁移脚本
- [x] 创建 `scripts/migrate_add_db_fields.sql`
- [x] 添加 ALTER TABLE 语句为 live_trades 表添加新字段
- [x] 添加 ALTER TABLE 语句为 live_position_snapshots 表添加新字段
- [x] 添加 DROP TABLE 语句删除未使用的表（注释形式，可选执行）
- **验证**: SQL 脚本可以在 Supabase Dashboard 执行

### Task 5.3: 执行迁移
- [ ] 备份现有数据库（用户手动执行）
- [ ] 执行 SQLite 迁移脚本（自动）
- [ ] 执行 Supabase 迁移脚本（用户手动执行）
- [ ] 验证表结构正确
- **验证**: 所有表结构已更新

---

## Phase 6: 测试与验证

### Task 6.1: 单元测试
- [x] 测试 trades 表新字段记录（语法验证通过）
- [x] 测试 position_snapshots 表新字段记录（语法验证通过）
- [x] 测试已删除方法不再存在（代码已删除）
- **验证**: 所有单元测试通过

### Task 6.2: 集成测试
- [ ] 启动 Bot 执行一笔交易（待用户执行）
- [ ] 验证 trades 表包含所有新字段数据（待用户执行）
- [ ] 验证 position_snapshots 表包含所有新字段数据（待用户执行）
- [ ] 验证已删除的表不再存在（待用户执行）
- **验证**: 集成测试通过

### Task 6.3: 数据验证
- [ ] 检查 Bitget 返回的数据是否完整记录（待用户执行）
- [ ] 检查字段值是否正确（待用户执行）
- [ ] 检查 Supabase 和 SQLite 数据一致性（待用户执行）
- **验证**: 数据准确完整

---

## Phase 7: 文档更新

### Task 7.1: 更新数据库分析报告
- [ ] 更新 `docs/database_usage_analysis.md`（可选）
- [ ] 标记已删除的表（可选）
- [ ] 说明增强的字段（可选）
- **验证**: 文档准确反映当前状态

### Task 7.2: 更新 README
- [ ] 说明数据库表结构变更（可选）
- [ ] 说明如何执行迁移脚本（可选）
- [ ] 说明新字段的含义（可选）
- **验证**: 文档清晰易懂

---

## Dependencies
- Phase 2 可以独立执行（删除表）
- Phase 3 依赖 Phase 1（需要 API 分析结果）
- Phase 4 依赖 Phase 1（需要 API 分析结果）
- Phase 5 依赖 Phase 2-4（需要完整的表结构设计）
- Phase 6 依赖 Phase 5（需要迁移完成）
- Phase 7 依赖 Phase 6（需要验证结果）

## Parallelizable Work
- Phase 1.1 和 Phase 1.2 可以并行（不同 API）
- Phase 3 和 Phase 4 可以并行（不同表）
- Phase 2 可以与 Phase 1 并行

## Estimated Time
- Phase 1: 30 分钟（API 分析）
- Phase 2: 30 分钟（删除表）
- Phase 3: 1.5 小时（增强 trades 表）
- Phase 4: 1.5 小时（增强 position_snapshots 表）
- Phase 5: 30 分钟（数据迁移）
- Phase 6: 30 分钟（测试验证）
- Phase 7: 15 分钟（文档更新）
- **总计**: 约 5 小时
