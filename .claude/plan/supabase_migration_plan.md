# Supabase 数据库迁移实施计划

**方案**: 方案A - 最小改动迁移
**目标**: 将回测系统从 SQLite 迁移到 Supabase,保持 API 兼容性,提升性能
**特性**: 集成 Supabase Realtime 实时订阅
**生成时间**: 2026-01-21
**Codex SESSION_ID**: 019bdfb4-e25f-7023-96a0-c5ef73431117

---

## 一、迁移概述

### 1.1 现状分析

**现有数据库结构**:
- SQLite 数据库文件: `backtest.db`
- 核心表: 14 个
- 扩展表: 4 个(历史/AI/变更/审计)
- 特殊处理: K线数据使用 zlib 压缩存储在 BLOB 字段

**现有 Repository 实现**:
- `backtest/repository.py` - BacktestRepository
- `backtest/adapters/storage/sqlite_repo.py` - SQLiteRepository
- `backtest/summary_repository.py` - SummaryRepository

**⚠️ 关键发现**:
- `backtest_metrics` 表存在定义冲突:
  - 实际 DB 使用 `session_id` 作为主键
  - `sqlite_repo.py` 中期望使用 `run_id`
  - **解决方案**: 以 `backtest.db` 实际结构为准,保持 `session_id`

### 1.2 迁移目标

- ✅ 1:1 复制表结构,保持字段名和类型一致
- ✅ 保持 Repository 接口签名不变
- ✅ 保持前端 API 调用方式不变
- ✅ 集成 Supabase Realtime 替代轮询
- ✅ 优化批量写入性能
- ✅ 添加适当索引提升查询性能

---

## 二、数据类型映射

| SQLite | PostgreSQL | 说明 |
|--------|-----------|------|
| TEXT | text | 字符串 |
| INTEGER | bigint | 整数(64位) |
| REAL | double precision | 浮点数 |
| BLOB | bytea | 二进制数据 |
| INTEGER PRIMARY KEY AUTOINCREMENT | bigserial PRIMARY KEY | 自增主键 |

---

## 三、Supabase 表结构设计

### 3.1 核心回测表

#### backtest_sessions
```sql
CREATE TABLE IF NOT EXISTS backtest_sessions (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  updated_at bigint NOT NULL,
  status text NOT NULL,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  initial_capital double precision NOT NULL,
  fee_rate double precision NOT NULL,
  slippage_bps double precision NOT NULL,
  leverage double precision NOT NULL DEFAULT 1.0,
  strategy_name text NOT NULL,
  strategy_params text NOT NULL,
  notes text,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON backtest_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_strategy ON backtest_sessions(strategy_name);
```

#### backtest_klines
```sql
CREATE TABLE IF NOT EXISTS backtest_klines (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  open double precision NOT NULL,
  high double precision NOT NULL,
  low double precision NOT NULL,
  close double precision NOT NULL,
  volume double precision NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_klines_session_ts
ON backtest_klines(session_id, ts);
```

#### backtest_events
```sql
CREATE TABLE IF NOT EXISTS backtest_events (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  event_type text NOT NULL,
  side text,
  price double precision,
  strategy_name text,
  reason text,
  confidence double precision,
  indicators_json text,
  raw_payload_json text,
  trade_id bigint
);

CREATE INDEX IF NOT EXISTS idx_backtest_events_session_ts
ON backtest_events(session_id, ts);
```

#### backtest_trades
```sql
CREATE TABLE IF NOT EXISTS backtest_trades (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  symbol text NOT NULL,
  side text NOT NULL,
  action text NOT NULL,
  qty double precision NOT NULL,
  price double precision NOT NULL,
  fee double precision DEFAULT 0,
  fee_asset text,
  pnl double precision DEFAULT 0,
  pnl_pct double precision DEFAULT 0,
  strategy_name text,
  reason text,
  event_id bigint REFERENCES backtest_events(id),
  open_trade_id bigint
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_session_ts
ON backtest_trades(session_id, ts);
```

#### backtest_positions
```sql
CREATE TABLE IF NOT EXISTS backtest_positions (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  symbol text NOT NULL,
  side text NOT NULL,
  entry_ts bigint NOT NULL,
  entry_price double precision NOT NULL,
  exit_ts bigint,
  exit_price double precision,
  qty double precision NOT NULL,
  max_runup double precision DEFAULT 0,
  max_drawdown double precision DEFAULT 0,
  realized_pnl double precision DEFAULT 0,
  unrealized_pnl double precision DEFAULT 0,
  status text NOT NULL,
  strategy_name text
);

CREATE INDEX IF NOT EXISTS idx_backtest_positions_session_status
ON backtest_positions(session_id, status);
```

#### backtest_metrics
```sql
CREATE TABLE IF NOT EXISTS backtest_metrics (
  session_id text PRIMARY KEY REFERENCES backtest_sessions(id),
  total_trades bigint NOT NULL,
  win_rate double precision NOT NULL,
  total_pnl double precision NOT NULL,
  total_return double precision NOT NULL,
  max_drawdown double precision NOT NULL,
  sharpe double precision NOT NULL,
  profit_factor double precision NOT NULL,
  expectancy double precision NOT NULL,
  avg_win double precision NOT NULL,
  avg_loss double precision NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_return ON backtest_metrics(total_return);
CREATE INDEX IF NOT EXISTS idx_metrics_sharpe ON backtest_metrics(sharpe);
CREATE INDEX IF NOT EXISTS idx_metrics_drawdown ON backtest_metrics(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_metrics_winrate ON backtest_metrics(win_rate);
```

#### backtest_equity_curve
```sql
CREATE TABLE IF NOT EXISTS backtest_equity_curve (
  id bigserial PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  ts bigint NOT NULL,
  equity double precision NOT NULL,
  balance double precision NOT NULL,
  drawdown double precision NOT NULL,
  peak_equity double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_session_ts
ON backtest_equity_curve(session_id, ts);
```

### 3.2 策略与优化表

#### strategy_versions
```sql
CREATE TABLE IF NOT EXISTS strategy_versions (
  id text PRIMARY KEY,
  name text NOT NULL,
  version text NOT NULL,
  params_schema text NOT NULL,
  code_hash text NOT NULL,
  created_at bigint NOT NULL,
  UNIQUE (name, version)
);
```

#### parameter_sets
```sql
CREATE TABLE IF NOT EXISTS parameter_sets (
  id text PRIMARY KEY,
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  params text NOT NULL,
  source text NOT NULL,
  created_at bigint NOT NULL
);
```

#### kline_datasets
```sql
CREATE TABLE IF NOT EXISTS kline_datasets (
  id text PRIMARY KEY,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  checksum text NOT NULL,
  data bytea NOT NULL,
  created_at bigint NOT NULL,
  UNIQUE (symbol, timeframe, start_ts, end_ts)
);
```

#### backtest_runs
```sql
CREATE TABLE IF NOT EXISTS backtest_runs (
  id text PRIMARY KEY,
  kline_dataset_id text NOT NULL REFERENCES kline_datasets(id),
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  param_set_id text REFERENCES parameter_sets(id),
  filter_set text,
  status text NOT NULL,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_status ON backtest_runs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_strategy ON backtest_runs(strategy_version_id);
```

#### optimization_jobs
```sql
CREATE TABLE IF NOT EXISTS optimization_jobs (
  id text PRIMARY KEY,
  strategy_version_id text NOT NULL REFERENCES strategy_versions(id),
  kline_dataset_id text NOT NULL REFERENCES kline_datasets(id),
  algorithm text NOT NULL,
  search_space text NOT NULL,
  status text NOT NULL,
  created_at bigint NOT NULL
);
```

#### optimization_results
```sql
CREATE TABLE IF NOT EXISTS optimization_results (
  id text PRIMARY KEY,
  job_id text NOT NULL REFERENCES optimization_jobs(id),
  param_set_id text NOT NULL REFERENCES parameter_sets(id),
  run_id text NOT NULL REFERENCES backtest_runs(id),
  rank bigint,
  score double precision,
  created_at bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opt_results_job_rank ON optimization_results(job_id, rank);
```

#### backtest_reports
```sql
CREATE TABLE IF NOT EXISTS backtest_reports (
  id text PRIMARY KEY,
  run_id text NOT NULL REFERENCES backtest_runs(id),
  summary text NOT NULL,
  recommendations text NOT NULL,
  created_at bigint NOT NULL
);
```

### 3.3 历史与AI功能表

#### backtest_session_summaries
```sql
CREATE TABLE IF NOT EXISTS backtest_session_summaries (
  session_id text PRIMARY KEY,
  created_at bigint NOT NULL,
  updated_at bigint NOT NULL,
  status text NOT NULL,
  symbol text NOT NULL,
  timeframe text NOT NULL,
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  strategy_name text NOT NULL,
  strategy_params text,
  total_trades bigint,
  win_rate double precision,
  total_return double precision,
  max_drawdown double precision,
  sharpe double precision
);

CREATE INDEX IF NOT EXISTS idx_summary_created_at ON backtest_session_summaries(created_at);
CREATE INDEX IF NOT EXISTS idx_summary_strategy ON backtest_session_summaries(strategy_name);
CREATE INDEX IF NOT EXISTS idx_summary_return ON backtest_session_summaries(total_return);
CREATE INDEX IF NOT EXISTS idx_summary_sharpe ON backtest_session_summaries(sharpe);
CREATE INDEX IF NOT EXISTS idx_summary_drawdown ON backtest_session_summaries(max_drawdown);
CREATE INDEX IF NOT EXISTS idx_summary_winrate ON backtest_session_summaries(win_rate);
CREATE INDEX IF NOT EXISTS idx_summary_cursor ON backtest_session_summaries(created_at, session_id);
```

#### backtest_ai_reports
```sql
CREATE TABLE IF NOT EXISTS backtest_ai_reports (
  id text PRIMARY KEY,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  created_at bigint NOT NULL,
  model_name text NOT NULL,
  prompt_version text NOT NULL,
  input_digest text NOT NULL,
  summary text NOT NULL,
  strengths text,
  weaknesses text,
  recommendations text,
  param_suggestions text,
  compare_group_id text
);

CREATE INDEX IF NOT EXISTS idx_ai_session ON backtest_ai_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_group ON backtest_ai_reports(compare_group_id);
CREATE INDEX IF NOT EXISTS idx_ai_created_at ON backtest_ai_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_session_created ON backtest_ai_reports(session_id, created_at);
```

#### backtest_change_requests
```sql
CREATE TABLE IF NOT EXISTS backtest_change_requests (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  created_by text NOT NULL,
  status text NOT NULL,
  session_id text NOT NULL REFERENCES backtest_sessions(id),
  strategy_name text NOT NULL,
  target_env text NOT NULL,
  change_payload text NOT NULL,
  change_description text,
  approved_by text,
  approved_at bigint,
  applied_by text,
  applied_at bigint,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_cr_status ON backtest_change_requests(status);
CREATE INDEX IF NOT EXISTS idx_cr_env ON backtest_change_requests(target_env);
CREATE INDEX IF NOT EXISTS idx_cr_created_at ON backtest_change_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_cr_session ON backtest_change_requests(session_id);
```

#### backtest_audit_logs
```sql
CREATE TABLE IF NOT EXISTS backtest_audit_logs (
  id text PRIMARY KEY,
  created_at bigint NOT NULL,
  actor text NOT NULL,
  action text NOT NULL,
  target_type text NOT NULL,
  target_id text NOT NULL,
  payload text,
  ip_address text,
  user_agent text
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON backtest_audit_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON backtest_audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON backtest_audit_logs(actor);
```

---

## 四、后端实施方案

### 4.1 环境配置

#### `.env` (后端)
```env
# Supabase Configuration
SUPABASE_URL=https://ooqortvtyswxruzldvjw.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_Wv2wqMOSYu-GlqchGQN5Iw_Lw9w3hUM
SUPABASE_ANON_KEY=sb_publishable_FXiqHIHZ_rIBoXf7op3H_w_Lepspm2V

# Optional: Direct Postgres connection for high-throughput migrations
# SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.ooqortvtyswxruzldvjw.supabase.co:5432/postgres
```

#### 依赖安装
```txt
# requirements.txt 添加
supabase-py>=1.0.0
# 或使用直连 Postgres
# asyncpg>=0.29.0
```

### 4.2 Supabase 客户端初始化

**文件**: `backtest/adapters/storage/supabase_client.py`

```python
"""
Supabase 客户端统一初始化
"""
import os
from supabase import create_client, Client
from typing import Optional

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """获取 Supabase 客户端单例"""
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        _supabase_client = create_client(url, key)
    return _supabase_client
```

### 4.3 Repository 实现

**文件**: `backtest/adapters/storage/supabase_repo.py`

```python
"""
Supabase 适配器 - 实现 IDataRepository 接口
"""
import zlib
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd

from backtest.domain.interfaces import IDataRepository
from backtest.adapters.storage.supabase_client import get_supabase_client


class SupabaseRepository(IDataRepository):
    """Supabase 存储适配器"""

    def __init__(self):
        self.client = get_supabase_client()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> pd.DataFrame:
        """获取K线数据"""
        response = self.client.table('kline_datasets') \
            .select('data') \
            .eq('symbol', symbol) \
            .eq('timeframe', timeframe) \
            .lte('start_ts', start_ts) \
            .gte('end_ts', end_ts) \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()

        if not response.data:
            return pd.DataFrame()

        # 解压数据
        compressed_data = bytes.fromhex(response.data[0]['data'][2:])  # 移除 '\x' 前缀
        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    async def save_kline_dataset(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        data: bytes
    ) -> str:
        """保存K线数据集(压缩)"""
        dataset_id = str(uuid.uuid4())
        checksum = str(hash(data))
        now = int(datetime.utcnow().timestamp())

        # bytea 格式化为 hex string
        hex_data = '\\x' + data.hex()

        self.client.table('kline_datasets').upsert({
            'id': dataset_id,
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts,
            'checksum': checksum,
            'data': hex_data,
            'created_at': now
        }, on_conflict='symbol,timeframe,start_ts,end_ts').execute()

        return dataset_id

    # ... 其他方法类似实现,保持接口签名不变
```

**文件**: `backtest/adapters/storage/supabase_summary_repo.py`

```python
"""
Supabase Summary Repository
"""
from typing import Optional, Dict, List, Tuple
from backtest.adapters.storage.supabase_client import get_supabase_client


class SupabaseSummaryRepository:
    """Supabase 摘要仓储"""

    ALLOWED_SORT_FIELDS = {
        "created_at", "updated_at", "total_trades", "win_rate",
        "total_return", "max_drawdown", "sharpe"
    }

    def __init__(self):
        self.client = get_supabase_client()

    def list_summaries(
        self,
        cursor: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        filters: Optional[Dict] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """列表查询,支持分页、排序、筛选"""
        if sort_by not in self.ALLOWED_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by: {sort_by}")
        if sort_dir not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_dir: {sort_dir}")

        query = self.client.table('backtest_session_summaries').select('*')

        # 应用筛选
        if filters:
            if 'strategy_name' in filters:
                query = query.eq('strategy_name', filters['strategy_name'])
            if 'created_at_from' in filters:
                query = query.gte('created_at', filters['created_at_from'])
            if 'created_at_to' in filters:
                query = query.lte('created_at', filters['created_at_to'])
            # ... 更多筛选条件

        # 游标分页
        if cursor:
            cursor_created_at, cursor_session_id = cursor.split(':')
            if sort_dir == 'desc':
                query = query.lt('created_at', int(cursor_created_at))
            else:
                query = query.gt('created_at', int(cursor_created_at))

        # 排序和限制
        query = query.order(sort_by, desc=(sort_dir == 'desc'))
        query = query.order('session_id', desc=(sort_dir == 'desc'))
        query = query.limit(limit + 1)

        response = query.execute()
        summaries = response.data[:limit]
        next_cursor = None
        if len(response.data) > limit:
            last = summaries[-1]
            next_cursor = f"{last['created_at']}:{last['session_id']}"

        return summaries, next_cursor

    # ... 其他方法
```

### 4.4 批量写入优化

**文件**: `backtest/adapters/storage/batch_writer.py`

```python
"""
批量写入缓冲器,减少 HTTP 往返
"""
from typing import List, Dict
from backtest.adapters.storage.supabase_client import get_supabase_client


class BatchWriter:
    """批量写入缓冲"""

    def __init__(self, table_name: str, batch_size: int = 500):
        self.client = get_supabase_client()
        self.table_name = table_name
        self.batch_size = batch_size
        self.buffer: List[Dict] = []

    def add(self, record: Dict):
        """添加记录到缓冲"""
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """提交缓冲的所有记录"""
        if not self.buffer:
            return
        self.client.table(self.table_name).insert(self.buffer).execute()
        self.buffer.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
```

**使用示例**:
```python
# 在回测引擎中使用批量写入
with BatchWriter('backtest_klines', batch_size=1000) as writer:
    for kline in klines:
        writer.add({
            'session_id': session_id,
            'ts': kline['ts'],
            'open': kline['open'],
            # ...
        })
# 自动 flush
```

---

## 五、数据迁移方案

### 5.1 迁移脚本结构

**文件**: `scripts/migrate_sqlite_to_supabase.py`

```python
"""
SQLite to Supabase 数据迁移脚本
"""
import sqlite3
import os
import sys
from supabase import create_client
from typing import List, Dict

# 依赖顺序(先父表后子表)
MIGRATION_ORDER = [
    # 策略表
    'strategy_versions',
    'parameter_sets',
    'kline_datasets',
    'backtest_runs',
    'optimization_jobs',
    'optimization_results',
    'backtest_reports',

    # 核心回测表
    'backtest_sessions',
    'backtest_klines',
    'backtest_events',
    'backtest_trades',
    'backtest_positions',
    'backtest_metrics',
    'backtest_equity_curve',

    # 历史与AI表
    'backtest_session_summaries',
    'backtest_ai_reports',
    'backtest_change_requests',
    'backtest_audit_logs',
]

def migrate_table(
    sqlite_conn: sqlite3.Connection,
    supabase_client,
    table_name: str,
    chunk_size: int = 500,
    bytea_columns: List[str] = []
):
    """迁移单个表"""
    print(f"Migrating {table_name}...")

    # 从 SQLite 读取
    cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    if not rows:
        print(f"  ✓ {table_name}: 0 rows")
        return

    # 转换为字典
    records = []
    for row in rows:
        record = dict(zip(columns, row))

        # BLOB 字段转 hex
        for col in bytea_columns:
            if col in record and record[col]:
                record[col] = '\\x' + record[col].hex()

        records.append(record)

    # 批量插入
    for i in range(0, len(records), chunk_size):
        batch = records[i:i+chunk_size]
        supabase_client.table(table_name).insert(batch).execute()
        print(f"  Inserted {i+len(batch)}/{len(records)}")

    print(f"  ✓ {table_name}: {len(records)} rows migrated")


def validate_migration(sqlite_conn, supabase_client, table_name: str):
    """验证迁移结果"""
    sqlite_count = sqlite_conn.execute(
        f"SELECT COUNT(*) FROM {table_name}"
    ).fetchone()[0]

    supabase_count = len(
        supabase_client.table(table_name).select('id', count='exact').execute().data
    )

    if sqlite_count == supabase_count:
        print(f"  ✓ {table_name}: {sqlite_count} rows matched")
        return True
    else:
        print(f"  ✗ {table_name}: SQLite={sqlite_count}, Supabase={supabase_count}")
        return False


def main():
    # 连接 SQLite
    sqlite_conn = sqlite3.connect('backtest.db')

    # 连接 Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    supabase = create_client(url, key)

    print("Starting migration...")
    print("=" * 60)

    # 按依赖顺序迁移
    for table in MIGRATION_ORDER:
        bytea_cols = ['data'] if table == 'kline_datasets' else []
        try:
            migrate_table(sqlite_conn, supabase, table, bytea_columns=bytea_cols)
        except Exception as e:
            print(f"  ✗ {table} migration failed: {e}")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("Validating migration...")
    print("=" * 60)

    # 验证
    all_valid = True
    for table in MIGRATION_ORDER:
        if not validate_migration(sqlite_conn, supabase, table):
            all_valid = False

    sqlite_conn.close()

    if all_valid:
        print("\n✓ Migration completed successfully!")
    else:
        print("\n✗ Migration validation failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### 5.2 迁移执行步骤

```bash
# 1. 备份现有数据库
cp backtest.db backtest.db.backup

# 2. 设置环境变量
export SUPABASE_URL="https://ooqortvtyswxruzldvjw.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="sb_secret_Wv2wqMOSYu-GlqchGQN5Iw_Lw9w3hUM"

# 3. 在 Supabase 执行 DDL(手动或通过脚本)

# 4. 执行迁移脚本
python scripts/migrate_sqlite_to_supabase.py

# 5. 验证迁移结果
# (脚本自动验证)
```

---

## 六、前端实施方案

### 6.1 环境配置

**文件**: `apps/dashboard/.env.local`

```env
NEXT_PUBLIC_SUPABASE_URL=https://ooqortvtyswxruzldvjw.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_FXiqHIHZ_rIBoXf7op3H_w_Lepspm2V
```

### 6.2 依赖安装

```bash
cd apps/dashboard
pnpm add @supabase/supabase-js
```

### 6.3 Supabase 客户端初始化

**文件**: `apps/dashboard/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

### 6.4 Realtime 订阅实现

**文件**: `apps/dashboard/hooks/useBacktestRealtime.ts`

```typescript
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

export function useBacktestRealtime(sessionId: string | null) {
  const [metrics, setMetrics] = useState<any>(null)
  const [status, setStatus] = useState<string>('idle')

  useEffect(() => {
    if (!sessionId) return

    // 订阅 backtest_sessions 状态更新
    const sessionChannel = supabase
      .channel(`session_${sessionId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'backtest_sessions',
          filter: `id=eq.${sessionId}`,
        },
        (payload) => {
          setStatus(payload.new.status)
        }
      )
      .subscribe()

    // 订阅 backtest_metrics 更新
    const metricsChannel = supabase
      .channel(`metrics_${sessionId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'backtest_metrics',
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          setMetrics(payload.new)
          setStatus('finished')
        }
      )
      .subscribe()

    return () => {
      sessionChannel.unsubscribe()
      metricsChannel.unsubscribe()
    }
  }, [sessionId])

  return { metrics, status }
}
```

**使用示例** (在 `apps/dashboard/app/backtest/new/page.tsx` 中):

```typescript
import { useBacktestRealtime } from '@/hooks/useBacktestRealtime'

export default function BacktestPage() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const { metrics, status } = useBacktestRealtime(currentSessionId)

  // 移除原有的 5 秒轮询逻辑
  // useEffect(() => { ... interval = setInterval(...) ... }, [])

  // 现在直接使用 Realtime 的 metrics 和 status
  return (
    <div>
      <p>Status: {status}</p>
      {metrics && <MetricsDisplay data={metrics} />}
    </div>
  )
}
```

### 6.5 前端 API 调用(保持不变)

现有的 axios 调用后端 API 的代码**无需修改**:

```typescript
// 仍然通过后端 API 创建回测
const response = await axios.post(`${apiUrl}/api/backtests/sessions`, requestData)

// 仍然通过后端 API 启动回测
await axios.post(`${apiUrl}/api/backtests/sessions/${sessionId}/start`)

// 查询历史数据也保持不变
const historyRes = await axios.get(`${apiUrl}/api/backtests/sessions?limit=50`)
```

**优化点**: 可选地,部分只读查询可以直接使用 Supabase 客户端:

```typescript
// 可选优化: 直接查询历史列表(减轻后端负载)
const { data: summaries } = await supabase
  .from('backtest_session_summaries')
  .select('*')
  .order('created_at', { ascending: false })
  .limit(50)
```

---

## 七、安全配置

### 7.1 Row Level Security (RLS)

由于需求明确**数据无需权限隔离**,推荐配置:

```sql
-- 启用 RLS 但设置全开放策略(便于未来收敛)
ALTER TABLE backtest_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_klines ENABLE ROW LEVEL SECURITY;
-- ... 所有表

-- 创建全开放策略
CREATE POLICY "Allow all access" ON backtest_sessions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all access" ON backtest_klines FOR ALL USING (true) WITH CHECK (true);
-- ... 所有表
```

**说明**:
- 前端使用 `anon key` 可以读写所有数据
- 后端使用 `service role key` 执行批量操作
- 未来如需细化权限,可以修改策略而无需改代码

### 7.2 密钥管理

- ✅ Secret Key 存储在后端 `.env`,不提交到 Git
- ✅ 前端仅使用 Publishable Key
- ✅ 生产环境通过环境变量注入

---

## 八、实施步骤清单

### 阶段 1: 准备与建表 (预估 1-2 天)

- [ ] **1.1** 确认 `backtest_metrics` 表结构冲突处理方案(以实际 DB 为准)
- [ ] **1.2** 备份现有 SQLite 数据库 (`cp backtest.db backtest.db.backup`)
- [ ] **1.3** 在 Supabase 项目中执行完整 DDL(所有表 + 索引)
- [ ] **1.4** 配置 RLS 策略(全开放策略)
- [ ] **1.5** 验证表结构: 查询 `information_schema` 对比 DDL

**验收标准**:
- ✅ 所有 18 个表创建成功
- ✅ 所有索引创建成功
- ✅ 外键约束正常
- ✅ RLS 策略配置完成

**风险点**:
- ⚠️ bytea 类型映射问题 → 提前测试小批量写入

---

### 阶段 2: 数据迁移 (预估 0.5-1 天)

- [ ] **2.1** 实现迁移脚本 (`scripts/migrate_sqlite_to_supabase.py`)
- [ ] **2.2** 配置环境变量 (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
- [ ] **2.3** 小批量测试迁移(选择 1-2 个小表)
- [ ] **2.4** 执行完整迁移(按依赖顺序)
- [ ] **2.5** 验证数据一致性:
  - 每表行数对比
  - 抽样记录对比(ID, 时间戳, 核心字段)
  - K线 BLOB 数据长度对比

**验收标准**:
- ✅ 所有表行数一致
- ✅ 抽样 10% 记录字段值一致
- ✅ BLOB 字段可正常读取和解压

**风险点**:
- ⚠️ 网络超时 → 调整 chunk_size
- ⚠️ BLOB 编码错误 → 验证 hex 格式

---

### 阶段 3: 后端代码重构 (预估 2-3 天)

- [ ] **3.1** 安装依赖 (`pip install supabase-py`)
- [ ] **3.2** 实现 `backtest/adapters/storage/supabase_client.py`
- [ ] **3.3** 实现 `backtest/adapters/storage/supabase_repo.py`
- [ ] **3.4** 实现 `backtest/adapters/storage/supabase_summary_repo.py`
- [ ] **3.5** 实现批量写入优化 (`batch_writer.py`)
- [ ] **3.6** 更新工厂或配置切换到 Supabase Repository
- [ ] **3.7** 集成到回测引擎和 API 路由

**验收标准**:
- ✅ 现有 API 端点返回格式不变
- ✅ 关键方法单元测试通过
- ✅ 回测引擎可正常创建和执行回测

**风险点**:
- ⚠️ API 兼容性问题 → 详细对比接口返回
- ⚠️ 批量写入性能 → Benchmark 测试

---

### 阶段 4: 前端集成 Realtime (预估 1-2 天)

- [ ] **4.1** 安装 `@supabase/supabase-js`
- [ ] **4.2** 创建 Supabase 客户端 (`apps/dashboard/lib/supabase.ts`)
- [ ] **4.3** 实现 Realtime Hook (`hooks/useBacktestRealtime.ts`)
- [ ] **4.4** 更新 `app/backtest/new/page.tsx` 使用 Realtime
- [ ] **4.5** 移除原有轮询逻辑
- [ ] **4.6** 测试实时更新功能

**验收标准**:
- ✅ 回测状态变化实时更新
- ✅ 指标完成后立即显示(无需等待轮询)
- ✅ 无多余的 API 请求

**风险点**:
- ⚠️ RLS 阻止订阅 → 验证策略配置
- ⚠️ WebSocket 连接失败 → 检查网络和 CORS

---

### 阶段 5: 测试与验证 (预估 1-2 天)

- [ ] **5.1** 端到端测试: 创建回测 → 运行 → 查看结果
- [ ] **5.2** 性能基准测试:
  - 回测总耗时对比 (SQLite vs Supabase)
  - 批量写入吞吐量测试
  - 查询响应时间对比
- [ ] **5.3** 数据一致性测试: 同一策略同一数据集结果一致
- [ ] **5.4** 历史查询测试: 分页、筛选、排序功能
- [ ] **5.5** Realtime 订阅测试: 多会话并发更新

**验收标准**:
- ✅ 所有功能正常工作
- ✅ 性能至少与 SQLite 持平或更优
- ✅ 无数据丢失或错误

**风险点**:
- ⚠️ 性能回退 → 检查索引和批量写入
- ⚠️ 并发问题 → 压力测试

---

### 阶段 6: 部署与监控 (预估 0.5-1 天)

- [ ] **6.1** 配置生产环境变量
- [ ] **6.2** 部署后端服务
- [ ] **6.3** 部署前端应用
- [ ] **6.4** 配置监控(Supabase Dashboard + 自定义日志)
- [ ] **6.5** 准备回滚方案(保留 SQLite Repository 代码)

**验收标准**:
- ✅ 生产环境正常运行
- ✅ 监控数据正常采集
- ✅ 回滚方案可用

**风险点**:
- ⚠️ 环境变量配置错误 → 详细检查
- ⚠️ Supabase 限流 → 了解配额和升级方案

---

## 九、风险评估与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| Schema 漂移导致迁移遗漏 | 高 | 中 | 以实际 DB 为准,交叉验证所有表 |
| BLOB 数据迁移失败 | 高 | 中 | 提前测试小批量,验证 hex 编码 |
| HTTP 批量写入性能瓶颈 | 中 | 中 | 使用批量写入,监控吞吐,必要时直连 PG |
| RLS 配置错误阻止访问 | 高 | 低 | 测试环境充分验证,生产前检查 |
| Realtime 订阅失败 | 中 | 低 | 保留轮询作为降级方案 |
| API 兼容性问题 | 高 | 低 | 详细集成测试,对比返回格式 |

---

## 十、后续优化方向

### 方案 B: 后端直连 Postgres (性能提升)

当迁移完成并稳定后,如果需要进一步提升性能:

- 使用 `asyncpg` 或 `psycopg3` 直连 Supabase Postgres
- 利用 `COPY` 命令或批量 `INSERT` 提升吞吐
- 减少 HTTP 往返,提升回测速度

### 方案 C: 存储分层优化 (成本优化)

当 K 线数据量增长到一定规模后:

- 将 K 线数据移至 Supabase Storage
- 数据库仅存元数据和索引
- 降低数据库成本,提升查询性能

---

## 十一、总结

### 核心原则

- **KISS**: 保持表结构和接口不变,降低迁移风险
- **YAGNI**: 不引入不必要的新模型,仅替换存储层
- **DRY**: 统一客户端初始化,复用迁移脚本
- **SOLID**: Repository 接口解耦,支持未来替换实现

### 预期收益

- ✅ 云端数据库,部署更简单
- ✅ PostgreSQL 查询性能优于 SQLite
- ✅ Realtime 订阅提升用户体验
- ✅ 可扩展性更强,支持更大数据量
- ✅ 为未来分布式部署打下基础

### 下一步行动

1. 用户确认本实施计划
2. 开始阶段 1: 在 Supabase 执行 DDL
3. 按步骤清单逐项实施
4. 每阶段完成后验收并汇报

---

**计划生成完成,等待用户批准执行**
