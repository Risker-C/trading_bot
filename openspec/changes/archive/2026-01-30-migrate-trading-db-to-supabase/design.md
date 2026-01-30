# Design Document

## Architecture Overview

### Component Structure
```
utils/
├── logger_utils.py              # 现有 TradeDatabase 类
├── supabase_trade_database.py  # 新增 SupabaseTradeDatabase 类
└── db_factory.py                # 新增工厂函数（可选）

scripts/
├── live_trading_supabase_schema.sql      # Supabase DDL
└── migrate_live_trading_to_supabase.py   # 数据迁移脚本

backtest/adapters/storage/
└── supabase_client.py           # 复用现有 Supabase 客户端
```

### Class Hierarchy
```
TradeDatabase (SQLite)
    ├── log_trade()
    ├── log_signal()
    ├── log_trade_buffered()
    ├── log_signal_buffered()
    └── ...

SupabaseTradeDatabase (Supabase)
    ├── log_trade()          # 实现相同接口
    ├── log_signal()         # 实现相同接口
    ├── log_trade_buffered() # 复用缓冲区逻辑
    ├── log_signal_buffered()
    └── ...
```

## Key Design Decisions

### 1. 接口兼容性策略
**决策**: 新类实现与 `TradeDatabase` 完全相同的方法签名

**理由**:
- 最小化代码改动，现有调用无需修改
- 降低迁移风险
- 支持配置切换和回滚

**实现**:
```python
# utils/logger_utils.py 底部
if getattr(config, 'USE_SUPABASE_FOR_LIVE_DATA', False):
    from utils.supabase_trade_database import SupabaseTradeDatabase
    db = SupabaseTradeDatabase()
else:
    db = TradeDatabase()
```

### 2. 批量写入优化
**决策**: 复用现有的缓冲区机制，但针对 Supabase 调整参数

**理由**:
- 网络延迟比本地 SQLite 高，批量写入更重要
- 现有缓冲区逻辑已验证可用
- Supabase 支持批量插入（`insert()` 接受数组）

**实现**:
- 默认 `SUPABASE_BATCH_SIZE = 100`（比 SQLite 的 20 更大）
- 默认 `SUPABASE_BATCH_FLUSH_INTERVAL = 5`（保持一致）
- 使用 Supabase SDK 的 `insert([...])` 批量插入

### 3. 表命名策略
**决策**: 使用 `live_` 前缀区分实时交易表和回测表

**理由**:
- 避免命名冲突（回测系统已有 `backtest_` 前缀）
- 清晰的语义区分
- 便于权限管理和查询优化

**表映射**:
```
SQLite              → Supabase
trades              → live_trades
signals             → live_signals
position_snapshots  → live_position_snapshots
balance_snapshots   → live_balance_snapshots
equity_curve        → live_equity_curve
risk_events         → live_risk_events
daily_stats         → live_daily_stats
risk_metrics        → live_risk_metrics
```

### 4. 时间戳存储
**决策**: 使用 `bigint` 存储毫秒级时间戳

**理由**:
- 与回测系统一致
- 避免时区问题
- 便于跨系统查询和对比

**实现**:
```python
created_at = int(time.time() * 1000)  # 毫秒时间戳
```

### 5. 错误处理与重试
**决策**: 实现指数退避重试机制（用户选择）

**理由**:
- 网络故障是云数据库的常见问题
- 指数退避避免过度重试导致限流
- 保证数据写入的可靠性

**实现**:
```python
def _write_with_retry(self, operation, max_retries=3):
    """指数退避重试"""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait_time)
```

### 6. 数据保留策略
**决策**: 不设置自动清理，保留所有历史数据（用户选择）

**理由**:
- 用户选择保留全部数据
- 便于长期分析和回溯
- Supabase 存储成本可接受

**未来优化**:
- 如需清理，可通过 Supabase 定时任务实现
- 或在应用层添加归档逻辑

### 7. 配置管理
**决策**: 使用环境变量和配置文件结合

**理由**:
- Supabase 凭证通过 `.env` 管理（安全）
- 功能开关通过 `config/settings.py` 管理（便于切换）

**配置项**:
```python
# .env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# config/settings.py
USE_SUPABASE_FOR_LIVE_DATA = False  # 默认关闭
SUPABASE_BATCH_SIZE = 100
SUPABASE_BATCH_FLUSH_INTERVAL = 5
```

## Data Flow

### 写入流程
```
Bot 调用 db.log_trade()
    ↓
检查配置 USE_SUPABASE_FOR_LIVE_DATA
    ↓
如果 True → SupabaseTradeDatabase.log_trade()
    ↓
添加到缓冲区 _trade_buffer
    ↓
检查是否需要刷新（大小或时间）
    ↓
批量写入 Supabase (insert([...]))
    ↓
指数退避重试（如果失败）
```

### 查询流程
```
Bot 调用 db.get_recent_trades()
    ↓
SupabaseTradeDatabase.get_recent_trades()
    ↓
Supabase SDK 查询
    ↓
返回结果（格式与 SQLite 一致）
```

## Migration Strategy

### 迁移步骤
1. **准备阶段**
   - 备份 `trading_bot.db`
   - 在 Supabase 创建表结构
   - 验证表创建成功

2. **数据迁移**
   - 按表顺序迁移（无依赖关系，可并行）
   - 批量读取 SQLite 数据（chunk_size=500）
   - 批量写入 Supabase
   - 验证行数一致

3. **切换阶段**
   - 设置 `USE_SUPABASE_FOR_LIVE_DATA = True`
   - 重启 Bot
   - 验证数据正常写入

4. **回滚方案**
   - 设置 `USE_SUPABASE_FOR_LIVE_DATA = False`
   - 重启 Bot
   - 恢复使用 SQLite

### 迁移脚本伪代码
```python
def migrate_table(sqlite_conn, supabase_client, table_name, chunk_size=500):
    # 读取 SQLite 数据
    cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
    columns = [desc[0] for desc in cursor.description]

    # 分批迁移
    while True:
        rows = cursor.fetchmany(chunk_size)
        if not rows:
            break

        # 转换为字典
        records = [dict(zip(columns, row)) for row in rows]

        # 批量插入 Supabase
        supabase_client.table(f'live_{table_name}').insert(records).execute()

    # 验证行数
    sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    supabase_count = len(supabase_client.table(f'live_{table_name}').select('id', count='exact').execute().data)

    assert sqlite_count == supabase_count, f"Row count mismatch: {sqlite_count} != {supabase_count}"
```

## Performance Considerations

### 写入性能
- **SQLite**: ~1ms per write (本地)
- **Supabase**: ~50-100ms per write (网络)
- **批量写入**: ~100-200ms for 100 records

**优化策略**:
- 使用批量写入（100条/批）
- 异步刷新缓冲区（5秒间隔）
- 高频表优先批量写入

### 查询性能
- 添加索引（created_at, strategy, symbol）
- 使用 Supabase 的查询优化
- 限制返回行数（默认 limit=100）

## Security Considerations

### 凭证管理
- Service Role Key 存储在 `.env`（不提交到 Git）
- 生产环境通过环境变量注入
- 使用 `.gitignore` 排除 `.env`

### RLS 策略
- 启用 RLS（Row Level Security）
- 配置全开放策略（与回测系统一致）
- 未来可细化权限控制

```sql
ALTER TABLE live_trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access" ON live_trades FOR ALL USING (true) WITH CHECK (true);
```

## Testing Strategy

### 单元测试
- 测试 `SupabaseTradeDatabase` 各方法
- 测试批量写入逻辑
- 测试重试机制
- 测试配置切换

### 集成测试
- 启动 Bot 并执行模拟交易
- 验证数据正确写入 Supabase
- 验证查询结果正确

### 性能测试
- 测试批量写入吞吐量
- 测试写入延迟
- 对比 SQLite 和 Supabase 性能

## Rollback Plan

### 回滚触发条件
- 写入失败率 > 5%
- 写入延迟 > 500ms
- 数据丢失或损坏

### 回滚步骤
1. 设置 `USE_SUPABASE_FOR_LIVE_DATA = False`
2. 重启 Bot
3. 验证 SQLite 正常工作
4. 分析 Supabase 问题
5. 修复后重新迁移

## Future Enhancements

### 短期优化
- 实现 Realtime 订阅（前端实时更新）
- 添加性能监控和告警
- 优化批量写入参数

### 长期规划
- 多实例部署支持
- 数据归档策略
- 跨区域复制
- 读写分离
