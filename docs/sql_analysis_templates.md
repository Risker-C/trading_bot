# SQL分析模板

## 数据库表结构

### 1. trade_tags 表（交易标签）

```sql
CREATE TABLE trade_tags (
    trade_id TEXT PRIMARY KEY,
    timestamp TEXT,

    -- 市场状态
    market_regime TEXT,              -- ranging/transitioning/trending
    market_confidence REAL,
    volatility_regime TEXT,          -- low/normal/high/extreme
    price REAL,
    volatility REAL,
    atr REAL,
    volume_ratio REAL,

    -- 策略信号
    strategy TEXT,
    signal TEXT,                     -- long/short/close_long/close_short
    signal_strength REAL,
    signal_confidence REAL,
    signal_reason TEXT,
    signal_indicators TEXT,          -- JSON

    -- 趋势过滤
    trend_filter_enabled INTEGER,
    trend_filter_pass INTEGER,
    trend_filter_reason TEXT,

    -- Claude 分析
    claude_enabled INTEGER,
    claude_pass INTEGER,
    claude_confidence REAL,
    claude_regime TEXT,
    claude_signal_quality REAL,
    claude_risk_flags TEXT,          -- JSON
    claude_reason TEXT,
    claude_suggested_sl REAL,
    claude_suggested_tp REAL,

    -- 执行层风控
    execution_filter_enabled INTEGER,
    execution_filter_pass INTEGER,
    execution_filter_reason TEXT,
    spread_check INTEGER,
    slippage_check INTEGER,
    liquidity_check INTEGER,

    -- 执行决策
    executed INTEGER,
    execution_reason TEXT,
    rejection_stage TEXT,            -- trend_filter/claude/execution_filter/risk_manager

    -- 仓位信息
    position_size REAL,
    position_size_pct REAL,
    leverage REAL,
    entry_price REAL,
    stop_loss_price REAL,
    take_profit_price REAL,

    -- 交易结果
    exit_price REAL,
    exit_time TEXT,
    pnl REAL,
    pnl_pct REAL,
    hold_time_minutes INTEGER,
    exit_reason TEXT,
    max_favorable_excursion REAL,    -- MFE
    max_adverse_excursion REAL       -- MAE
);
```

### 2. shadow_decisions 表（影子模式）

```sql
CREATE TABLE shadow_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    trade_id TEXT,

    -- 市场状态
    price REAL,
    market_regime TEXT,
    volatility REAL,

    -- 策略信号
    strategy TEXT,
    signal TEXT,
    signal_strength REAL,
    signal_confidence REAL,

    -- 各阶段决策（would_execute_xxx）
    would_execute_strategy INTEGER,
    would_execute_after_trend INTEGER,
    would_execute_after_claude INTEGER,
    would_execute_after_exec INTEGER,
    final_would_execute INTEGER,

    -- 拒绝原因
    rejection_stage TEXT,
    rejection_reason TEXT,

    -- 详细信息
    trend_filter_pass INTEGER,
    claude_pass INTEGER,
    exec_filter_pass INTEGER,

    -- 实际执行
    actually_executed INTEGER,
    actual_pnl REAL,
    actual_pnl_pct REAL
);
```

---

## 核心分析SQL模板

### 1. 六大核心指标（一键查询）

```sql
-- 1. 基础统计
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(pnl), 2) as avg_pnl_per_trade
FROM trade_tags
WHERE executed = 1 AND pnl != 0;

-- 2. 最大回撤（Max Drawdown）
WITH cumulative AS (
    SELECT
        timestamp,
        pnl,
        SUM(pnl) OVER (ORDER BY timestamp) as cumulative_pnl
    FROM trade_tags
    WHERE executed = 1 AND pnl != 0
),
peaks AS (
    SELECT
        timestamp,
        cumulative_pnl,
        MAX(cumulative_pnl) OVER (ORDER BY timestamp) as peak
    FROM cumulative
)
SELECT
    ROUND(MAX(peak - cumulative_pnl), 2) as max_drawdown,
    ROUND(MAX(peak - cumulative_pnl) / NULLIF(MAX(peak), 0) * 100, 2) as max_drawdown_pct
FROM peaks;

-- 3. 连续亏损P95（Loss Streak P95）
-- 需要在应用层计算，SQL较复杂

-- 4. 盈亏比（Profit Factor）
SELECT
    ROUND(
        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
        NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0),
        2
    ) as profit_factor,
    ROUND(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 2) as total_profit,
    ROUND(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 2) as total_loss
FROM trade_tags
WHERE executed = 1 AND pnl != 0;

-- 5. 单笔期望（Expectancy per Trade）
SELECT
    ROUND(AVG(pnl), 2) as expectancy_per_trade,
    ROUND(AVG(pnl_pct), 2) as expectancy_pct
FROM trade_tags
WHERE executed = 1 AND pnl != 0;

-- 6. 平均滑点（需要在trade_tags中添加expected_price字段）
-- 暂时无法计算
```

### 2. 分阶段拒绝贡献度

```sql
-- 各阶段拒绝统计
SELECT
    COUNT(*) as total_signals,
    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
    ROUND(CAST(SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as execution_rate_pct,

    -- 各阶段拒绝
    SUM(CASE WHEN trend_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_trend,
    SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 0 THEN 1 ELSE 0 END) as rejected_by_claude,
    SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 1 AND execution_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_exec,

    -- 拒绝率
    ROUND(CAST(SUM(CASE WHEN trend_filter_pass = 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as trend_rejection_rate_pct,
    ROUND(CAST(SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as claude_rejection_rate_pct,
    ROUND(CAST(SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 1 AND execution_filter_pass = 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as exec_rejection_rate_pct
FROM trade_tags
WHERE timestamp >= date('now', '-7 days');  -- 最近7天
```

### 3. Claude性能分析

```sql
-- Claude通过vs拒绝的对比
SELECT
    'Claude通过' as category,
    COUNT(*) as count,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(AVG(claude_confidence), 2) as avg_confidence
FROM trade_tags
WHERE claude_enabled = 1 AND claude_pass = 1 AND executed = 1 AND pnl != 0

UNION ALL

SELECT
    'Claude拒绝' as category,
    COUNT(*) as count,
    NULL as wins,
    NULL as win_rate_pct,
    NULL as avg_pnl,
    ROUND(AVG(claude_confidence), 2) as avg_confidence
FROM trade_tags
WHERE claude_enabled = 1 AND claude_pass = 0;

-- Claude置信度分组分析
SELECT
    CASE
        WHEN claude_confidence >= 0.7 THEN '高置信度(≥0.7)'
        WHEN claude_confidence >= 0.5 THEN '中置信度(0.5-0.7)'
        ELSE '低置信度(<0.5)'
    END as confidence_group,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(AVG(claude_confidence), 3) as avg_confidence
FROM trade_tags
WHERE claude_enabled = 1 AND claude_pass = 1 AND executed = 1 AND pnl != 0
GROUP BY confidence_group
ORDER BY avg_confidence DESC;
```

### 4. 策略表现对比

```sql
-- 各策略表现
SELECT
    strategy,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(AVG(signal_strength), 2) as avg_signal_strength,
    ROUND(AVG(hold_time_minutes), 0) as avg_hold_minutes
FROM trade_tags
WHERE executed = 1 AND pnl != 0
GROUP BY strategy
ORDER BY total_pnl DESC;
```

### 5. 市场状态分析

```sql
-- 不同市场状态下的表现
SELECT
    market_regime,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(AVG(volatility), 4) as avg_volatility
FROM trade_tags
WHERE executed = 1 AND pnl != 0
GROUP BY market_regime
ORDER BY total_pnl DESC;
```

### 6. 风险标记分析

```sql
-- Claude风险标记统计
SELECT
    claude_risk_flags,
    COUNT(*) as count,
    SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
    SUM(CASE WHEN executed = 1 AND pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN executed = 1 AND pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) /
          NULLIF(SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END), 0) * 100, 2) as win_rate_pct
FROM trade_tags
WHERE claude_enabled = 1 AND claude_risk_flags != '[]'
GROUP BY claude_risk_flags
ORDER BY count DESC
LIMIT 10;
```

### 7. 影子模式A/B对比

```sql
-- 各阶段执行率对比
SELECT
    'Strategy Only' as stage,
    SUM(would_execute_strategy) as would_execute,
    ROUND(CAST(SUM(would_execute_strategy) AS FLOAT) / COUNT(*) * 100, 2) as execution_rate_pct
FROM shadow_decisions

UNION ALL

SELECT
    'After Trend Filter' as stage,
    SUM(would_execute_after_trend) as would_execute,
    ROUND(CAST(SUM(would_execute_after_trend) AS FLOAT) / COUNT(*) * 100, 2) as execution_rate_pct
FROM shadow_decisions

UNION ALL

SELECT
    'After Claude' as stage,
    SUM(would_execute_after_claude) as would_execute,
    ROUND(CAST(SUM(would_execute_after_claude) AS FLOAT) / COUNT(*) * 100, 2) as execution_rate_pct
FROM shadow_decisions

UNION ALL

SELECT
    'Final (After Exec Filter)' as stage,
    SUM(final_would_execute) as would_execute,
    ROUND(CAST(SUM(final_would_execute) AS FLOAT) / COUNT(*) * 100, 2) as execution_rate_pct
FROM shadow_decisions;
```

### 8. 时间序列分析

```sql
-- 按日统计
SELECT
    DATE(timestamp) as date,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
    ROUND(SUM(pnl), 2) as daily_pnl,
    ROUND(AVG(pnl), 2) as avg_pnl
FROM trade_tags
WHERE executed = 1 AND pnl != 0
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 30;
```

---

## 快速分析脚本

### Python脚本：一键生成完整报告

```python
#!/usr/bin/env python3
"""
一键生成完整性能报告
"""
import sqlite3
import sys

def generate_report(db_path='trading_bot.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("交易系统性能报告")
    print("=" * 80)

    # 1. 基础统计
    print("\n1. 基础统计")
    print("-" * 80)
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
            ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
            ROUND(SUM(pnl), 2) as total_pnl,
            ROUND(AVG(pnl), 2) as avg_pnl
        FROM trade_tags
        WHERE executed = 1 AND pnl != 0
    """)
    row = cursor.fetchone()
    if row:
        print(f"总交易: {row['total_trades']}")
        print(f"胜率: {row['win_rate_pct']}% ({row['winning_trades']}胜 / {row['losing_trades']}负)")
        print(f"总盈亏: {row['total_pnl']} USDT")
        print(f"单笔期望: {row['avg_pnl']} USDT")

    # 2. 盈亏比
    print("\n2. 盈亏比")
    print("-" * 80)
    cursor = conn.execute("""
        SELECT
            ROUND(
                SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) /
                NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0),
                2
            ) as profit_factor,
            ROUND(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 2) as total_profit,
            ROUND(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 2) as total_loss
        FROM trade_tags
        WHERE executed = 1 AND pnl != 0
    """)
    row = cursor.fetchone()
    if row:
        print(f"盈亏比: {row['profit_factor']}")
        print(f"总盈利: {row['total_profit']} USDT")
        print(f"总亏损: {row['total_loss']} USDT")

    # 3. 拒绝分析
    print("\n3. 拒绝率分布")
    print("-" * 80)
    cursor = conn.execute("""
        SELECT
            COUNT(*) as total_signals,
            SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed,
            SUM(CASE WHEN trend_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_trend,
            SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 0 THEN 1 ELSE 0 END) as rejected_by_claude,
            SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 1 AND execution_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_exec
        FROM trade_tags
    """)
    row = cursor.fetchone()
    if row:
        total = row['total_signals']
        print(f"总信号: {total}")
        print(f"执行: {row['executed']} ({row['executed']/total*100:.1f}%)")
        print(f"趋势过滤拒绝: {row['rejected_by_trend']} ({row['rejected_by_trend']/total*100:.1f}%)")
        print(f"Claude拒绝: {row['rejected_by_claude']} ({row['rejected_by_claude']/total*100:.1f}%)")
        print(f"执行层拒绝: {row['rejected_by_exec']} ({row['rejected_by_exec']/total*100:.1f}%)")

    # 4. Claude性能
    print("\n4. Claude性能")
    print("-" * 80)
    cursor = conn.execute("""
        SELECT
            COUNT(*) as trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
            ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
            ROUND(AVG(claude_confidence), 2) as avg_confidence
        FROM trade_tags
        WHERE claude_enabled = 1 AND claude_pass = 1 AND executed = 1 AND pnl != 0
    """)
    row = cursor.fetchone()
    if row:
        print(f"Claude交易: {row['trades']}")
        print(f"Claude胜率: {row['win_rate_pct']}%")
        print(f"平均置信度: {row['avg_confidence']}")

    # 5. 策略对比
    print("\n5. 策略表现")
    print("-" * 80)
    cursor = conn.execute("""
        SELECT
            strategy,
            COUNT(*) as trades,
            ROUND(CAST(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as win_rate_pct,
            ROUND(SUM(pnl), 2) as total_pnl
        FROM trade_tags
        WHERE executed = 1 AND pnl != 0
        GROUP BY strategy
        ORDER BY total_pnl DESC
    """)
    for row in cursor.fetchall():
        print(f"{row['strategy']}: {row['trades']}笔, 胜率{row['win_rate_pct']}%, 盈亏{row['total_pnl']}")

    print("\n" + "=" * 80)
    conn.close()

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'trading_bot.db'
    generate_report(db_path)
```

**使用方法：**
```bash
# 保存为 quick_report.py
chmod +x quick_report.py
./quick_report.py

# 或指定数据库路径
./quick_report.py /path/to/trading_bot.db
```

---

## 样例数据

### trade_tags 样例记录

```sql
INSERT INTO trade_tags VALUES (
    'uuid-123',                    -- trade_id
    '2025-01-15 10:30:00',        -- timestamp
    'trending', 0.8,              -- market_regime, market_confidence
    'normal',                      -- volatility_regime
    86500, 0.025, 450, 1.2,       -- price, volatility, atr, volume_ratio
    'macd_cross', 'long',         -- strategy, signal
    0.75, 0.7,                    -- signal_strength, signal_confidence
    'MACD金叉',                    -- signal_reason
    '{"rsi": 45, "macd": 200}',   -- signal_indicators
    1, 1, '趋势过滤通过',          -- trend_filter_enabled, pass, reason
    1, 1, 0.78,                   -- claude_enabled, pass, confidence
    'trend', 0.8,                 -- claude_regime, signal_quality
    '[]',                         -- claude_risk_flags
    '趋势明确，可以执行',          -- claude_reason
    0.02, 0.04,                   -- claude_suggested_sl, tp
    1, 1, '执行层检查通过',        -- exec_filter_enabled, pass, reason
    1, 1, 1,                      -- spread_check, slippage_check, liquidity_check
    1, '通过所有检查', '',        -- executed, execution_reason, rejection_stage
    0.1, 0.1, 10,                 -- position_size, position_size_pct, leverage
    86500, 85000, 88000,          -- entry_price, stop_loss_price, take_profit_price
    87200, '2025-01-15 11:15:00', -- exit_price, exit_time
    70, 0.81, 45,                 -- pnl, pnl_pct, hold_time_minutes
    '止盈', 800, -150             -- exit_reason, mfe, mae
);
```

---

## 使用建议

### 1. 日常监控（每天）

```bash
# 查看今日表现
sqlite3 trading_bot.db "
SELECT
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(pnl), 2) as pnl
FROM trade_tags
WHERE DATE(timestamp) = DATE('now')
  AND executed = 1 AND pnl != 0;
"
```

### 2. 周度分析（每周）

```bash
# 运行完整报告
python performance_analyzer.py --start $(date -d '7 days ago' +%Y-%m-%d) --export weekly_report.csv
```

### 3. 参数调优（发现问题时）

```bash
# 找出最常见的拒绝原因
sqlite3 trading_bot.db "
SELECT rejection_stage, COUNT(*) as count
FROM trade_tags
WHERE executed = 0
GROUP BY rejection_stage
ORDER BY count DESC;
"

# 找出Claude最常标记的风险
sqlite3 trading_bot.db "
SELECT claude_risk_flags, COUNT(*) as count
FROM trade_tags
WHERE claude_enabled = 1
GROUP BY claude_risk_flags
ORDER BY count DESC
LIMIT 10;
"
```

---

## 验收标准

使用这些SQL模板，你应该能够：

✅ **1分钟内**查看6个核心指标
✅ **5分钟内**生成完整性能报告
✅ **10分钟内**找出系统的主要问题（哪个阶段拒绝最多、哪个策略表现最差）
✅ **30分钟内**完成一轮参数调优（基于数据而非猜测）

这就是"数据驱动迭代"的基础设施。
