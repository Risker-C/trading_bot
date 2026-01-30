# Implementation Tasks

## Phase 1: Supabase Schema Setup
- [x] 创建 `scripts/live_trading_supabase_schema.sql` 包含8个表的DDL
  - 验证：在 Supabase Dashboard 执行 SQL 后所有表创建成功
- [x] 配置 RLS 策略（全开放策略，与回测系统一致）
  - 验证：使用 service role key 可以读写所有表

## Phase 2: SupabaseTradeDatabase 实现
- [x] 创建 `utils/supabase_trade_database.py` 实现核心类
  - 实现 `__init__` 方法（初始化 Supabase 客户端）
  - 实现 `log_trade` 方法（单条交易写入）
  - 实现 `log_signal` 方法（单条信号写入，处理 numpy 类型）
  - 验证：单元测试通过，数据正确写入 Supabase

- [x] 实现批量写入方法
  - 实现 `log_trade_buffered` 方法（复用缓冲区逻辑）
  - 实现 `log_signal_buffered` 方法
  - 实现 `log_trades_batch` 方法（批量插入）
  - 实现 `log_signals_batch` 方法
  - 实现 `flush_buffers` 方法
  - 验证：批量写入测试通过，性能满足要求（< 100ms）

- [x] 实现其他数据记录方法
  - 实现 `log_position_snapshot` 方法
  - 实现 `log_balance_snapshot` 方法
  - 实现 `log_risk_event` 方法
  - 实现 `log_equity_curve` 方法
  - 实现 `log_risk_metrics` 方法
  - 验证：所有方法正常工作

- [x] 实现查询方法
  - 实现 `get_latest_position_snapshot` 方法
  - 实现 `get_position_history` 方法
  - 实现 `get_recent_trades` 方法
  - 实现 `get_daily_stats` 方法
  - 验证：查询结果正确

## Phase 3: 配置集成
- [x] 在 `config/settings.py` 添加配置项
  - 添加 `USE_SUPABASE_FOR_LIVE_DATA = True` （已启用）
  - 添加 `SUPABASE_BATCH_SIZE = 100` （Supabase 批量大小）
  - 添加 `SUPABASE_BATCH_FLUSH_INTERVAL = 5` （刷新间隔）
  - 验证：配置项可正常读取

- [x] 修改 `utils/logger_utils.py` 底部的实例化逻辑
  - 根据 `USE_SUPABASE_FOR_LIVE_DATA` 选择实例化 `TradeDatabase` 或 `SupabaseTradeDatabase`
  - 确保接口完全兼容
  - 验证：切换配置后 bot 正常启动

## Phase 4: 数据迁移
- [x] 创建 `scripts/migrate_live_trading_to_supabase.py` 迁移脚本
  - 实现按表迁移逻辑（按依赖顺序）
  - 实现数据验证逻辑（行数对比）
  - 添加进度显示
  - 验证：迁移脚本可成功执行

- [x] 执行数据迁移
  - 备份 `trading_bot.db`
  - 运行迁移脚本
  - 验证数据一致性
  - 验证：SQLite 和 Supabase 数据行数一致

## Phase 5: 测试与验证
- [x] 创建 `scripts/test_supabase_trade_database.py` 测试脚本
  - 测试单条写入
  - 测试批量写入
  - 测试查询方法
  - 测试配置切换
  - 验证：所有测试通过

- [x] 集成测试
  - 启动 bot 并切换到 Supabase
  - 执行一笔模拟交易
  - 验证数据正确写入 Supabase
  - 验证：实时交易数据正常记录

- [x] 性能测试
  - 测试批量写入吞吐量
  - 测试写入延迟
  - 对比 SQLite 和 Supabase 性能
  - 验证：性能满足要求

## Phase 6: 文档与清理
- [x] 更新 README 或相关文档
  - 说明如何配置 Supabase
  - 说明如何运行迁移脚本
  - 说明如何切换数据库
  - 验证：文档清晰易懂

- [x] 代码审查与清理
  - 移除调试日志
  - 添加必要的错误处理
  - 确保代码风格一致
  - 验证：代码质量符合标准

## Dependencies
- Phase 2 依赖 Phase 1（需要表结构）
- Phase 3 依赖 Phase 2（需要实现类）
- Phase 4 依赖 Phase 1 和 Phase 2（需要表和实现）
- Phase 5 依赖 Phase 2, 3, 4（需要完整功能）

## Parallelizable Work
- Phase 1 和 Phase 2 的部分工作可以并行（DDL 和代码实现）
- Phase 4 和 Phase 5 的测试脚本编写可以并行
