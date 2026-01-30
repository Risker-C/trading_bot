# Migrate Trading Database to Supabase

## Context

### User Need
迁移交易系统的实时数据存储从 SQLite (`trading_bot.db`) 到 Supabase 云数据库，以实现：
- 云端数据持久化，避免本地数据丢失
- 多实例部署支持（未来扩展）
- 更好的查询性能和并发支持
- 与回测系统统一使用 Supabase

### Current State
- 回测系统已成功迁移到 Supabase
- 交易系统使用 `TradeDatabase` 类（`utils/logger_utils.py:269-1100`）管理 SQLite
- 8个核心表存储实时交易数据：
  - `trades`: 交易记录（每笔交易写入）
  - `signals`: 策略信号（每次信号写入）
  - `position_snapshots`: 持仓快照（每分钟写入）
  - `balance_snapshots`: 余额快照（每分钟写入）
  - `equity_curve`: 权益曲线（每分钟写入）
  - `risk_events`: 风险事件（触发时写入）
  - `daily_stats`: 每日统计（每日写入）
  - `risk_metrics`: 风险指标（更新时写入）

### Discovered Constraints

**Hard Constraints:**
1. 必须保持 `TradeDatabase` 接口签名不变，确保现有调用代码无需修改
2. 必须支持批量写入优化（`log_trade_buffered`, `log_signal_buffered`）
3. 必须处理 numpy 类型转换（signals 表的 indicators 字段）
4. 必须支持配置开关在 SQLite 和 Supabase 之间切换
5. 高频写入表（signals, position_snapshots, equity_curve）需要批量写入优化
6. 必须保留现有数据（迁移脚本）

**Soft Constraints:**
1. 优先使用 Supabase Python SDK（与回测系统一致）
2. 表名添加 `live_` 前缀以区分回测数据
3. 使用 bigint 存储时间戳（毫秒）
4. 索引策略与 SQLite 保持一致

**Dependencies:**
1. 依赖现有的 `backtest/adapters/storage/supabase_client.py`
2. 依赖 `.env` 中的 Supabase 配置
3. 不影响回测系统的 Supabase 使用

**Risks:**
1. 网络延迟可能影响写入性能 → 批量写入缓解
2. Supabase 限流风险 → 监控并调整批量大小
3. 数据迁移失败风险 → 保留 SQLite 备份和回滚机制

## Proposed Solution

### High-Level Approach
1. 创建 Supabase 表结构（8个表，添加 `live_` 前缀）
2. 实现 `SupabaseTradeDatabase` 类，继承或实现与 `TradeDatabase` 相同的接口
3. 添加配置开关 `USE_SUPABASE_FOR_LIVE_DATA`
4. 实现数据迁移脚本
5. 保留 SQLite 实现作为回滚方案

### Key Design Decisions
1. **接口兼容性**: 新类实现与 `TradeDatabase` 完全相同的方法签名
2. **批量写入**: 复用现有的缓冲区机制（`_trade_buffer`, `_signal_buffer`）
3. **配置切换**: 在 `utils/logger_utils.py` 底部根据配置实例化不同的类
4. **表命名**: 使用 `live_` 前缀避免与回测表冲突

## Scope

### In Scope
- 创建 8 个 Supabase 表的 DDL
- 实现 `SupabaseTradeDatabase` 类
- 实现批量写入优化
- 添加配置开关
- 数据迁移脚本
- 基本测试验证

### Out of Scope
- 前端 Dashboard 集成（后续独立任务）
- Realtime 订阅功能（后续优化）
- 性能监控和告警（后续优化）
- 多实例部署支持（未来需求）

## Success Criteria
1. 所有现有调用 `db.log_trade()` 等方法的代码无需修改
2. 切换到 Supabase 后交易数据正常写入
3. 批量写入功能正常工作
4. 可通过配置开关回退到 SQLite
5. 现有 SQLite 数据成功迁移到 Supabase
6. 写入延迟在可接受范围内（< 100ms for buffered writes）

## Resolved Questions (User Decisions)
1. **双写模式**: 不需要双写，直接切换到 Supabase，保留 SQLite 作为回滚方案
2. **数据保留策略**: 保留全部数据，不设置自动清理
3. **重试机制**: 实现指数退避重试（1s, 2s, 4s...）

## Status
- [x] 提案创建
- [x] 用户确认关键决策
- [ ] 等待批准执行
