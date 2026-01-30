# Design Document

## Architecture Overview

### Component Structure
```
bot.py
├── _main_loop()                    # 主循环（添加权益曲线记录）
├── _update_daily_stats()           # 新增：每日统计更新
└── __init__()                      # 初始化（添加日期追踪）

risk/risk_manager.py
├── record_trade_result()           # 现有方法（添加风险指标更新触发）
└── _update_risk_metrics()          # 新增：风险指标更新

utils/logger_utils.py
└── db (TradeDatabase/SupabaseTradeDatabase)
    ├── log_equity()                # 已实现
    ├── update_daily_stats()        # 已实现
    └── log_risk_metrics()          # 已实现
```

### Data Flow

#### 权益曲线记录流程
```
_main_loop() 每次执行
    ↓
获取当前余额 (trader.get_balance())
    ↓
获取未实现盈亏 (risk_manager.position.unrealized_pnl)
    ↓
计算总权益 (equity = balance + unrealized_pnl)
    ↓
调用 db.log_equity()
    ↓
写入 Supabase (equity_curve 表)
```

#### 每日统计更新流程
```
_main_loop() 检测日期变化
    ↓
调用 _update_daily_stats()
    ↓
获取今日交易 (db.get_today_trades())
    ↓
计算统计指标 (总交易、盈利/亏损次数、总盈亏)
    ↓
调用 db.update_daily_stats()
    ↓
写入 Supabase (daily_stats 表)
```

#### 风险指标更新流程
```
交易完成 (record_trade_result())
    ↓
调用 _update_risk_metrics()
    ↓
获取最近100笔交易 (db.get_trades(limit=100))
    ↓
检查交易数量 >= 10
    ↓
计算风险指标 (胜率、盈亏比、期望值)
    ↓
调用 db.log_risk_metrics()
    ↓
写入 Supabase (risk_metrics 表)
```

---

## Key Design Decisions

### 1. 权益曲线记录位置
**决策**: 在 `_main_loop()` 末尾记录

**理由**:
- 每次循环执行一次，频率适中
- 可以捕获账户权益的实时变化
- 不影响交易逻辑执行

**实现**:
```python
# bot.py - _main_loop() 末尾
try:
    balance = self.trader.get_balance()
    position = self.risk_manager.position
    unrealized_pnl = position.unrealized_pnl if position else 0
    equity = balance + unrealized_pnl

    db.log_equity(
        equity=equity,
        balance=balance,
        drawdown=self.risk_manager.current_drawdown,
        peak_equity=self.risk_manager.peak_equity
    )
except Exception as e:
    logger.warning(f"记录权益曲线失败: {e}")
```

---

### 2. 每日统计触发时机
**决策**: 检测日期变化时更新前一天的统计

**理由**:
- 避免在交易高峰时段执行耗时计算
- 确保统计数据完整（包含全天交易）
- 简化实现逻辑

**实现**:
```python
# bot.py - __init__()
self.last_stats_date = datetime.now().strftime("%Y-%m-%d")
self.starting_balance = self.trader.get_balance()

# bot.py - _main_loop()
current_date = datetime.now().strftime("%Y-%m-%d")
if current_date != self.last_stats_date:
    try:
        self._update_daily_stats()
        self.last_stats_date = current_date
        self.starting_balance = self.trader.get_balance()
    except Exception as e:
        logger.warning(f"更新每日统计失败: {e}")
```

---

### 3. 风险指标更新频率
**决策**: 每次交易后检查，如果交易数>=10则更新

**理由**:
- 确保风险指标基于足够的样本量
- 避免频繁计算（交易频率通常不高）
- 及时反映风险指标变化

**实现**:
```python
# risk/risk_manager.py - _update_risk_metrics()
def _update_risk_metrics(self):
    """更新风险指标"""
    try:
        trades = db.get_trades(limit=100)

        if len(trades) < 10:
            return  # 交易数量不足，跳过

        winning = [t for t in trades if (t.get('pnl') or 0) > 0]
        losing = [t for t in trades if (t.get('pnl') or 0) < 0]

        if not trades:
            return

        win_rate = len(winning) / len(trades) if trades else 0

        total_win = sum(t.get('pnl', 0) or 0 for t in winning)
        total_loss = abs(sum(t.get('pnl', 0) or 0 for t in losing))
        profit_factor = total_win / total_loss if total_loss > 0 else 0

        db.log_risk_metrics(
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=sum(t.get('pnl', 0) or 0 for t in trades) / len(trades),
            max_drawdown=self.max_drawdown,
            kelly_fraction=self.kelly_fraction,
            consecutive_losses=self.consecutive_losses
        )
    except Exception as e:
        logger.warning(f"更新风险指标失败: {e}")
```

---

### 4. 异常处理策略
**决策**: 所有记录功能使用 try-except，失败时记录警告但不中断

**理由**:
- 数据记录失败不应影响交易执行
- 警告日志便于排查问题
- 保证系统稳定性

---

### 5. 性能优化
**决策**:
- 权益曲线：每次循环记录（频率已适中）
- 每日统计：仅在日期变化时计算（低频）
- 风险指标：仅在交易后且交易数>=10时计算（低频）

**理由**:
- 避免频繁数据库写入
- 避免不必要的计算
- 确保总延迟 < 100ms

---

## Migration Strategy

### 实施步骤
1. **Phase 1**: 实现权益曲线记录（最简单，影响最小）
2. **Phase 2**: 实现每日统计（需要日期追踪逻辑）
3. **Phase 3**: 实现风险指标记录（需要复杂计算）
4. **Phase 4**: 测试验证
5. **Phase 5**: 文档更新

### 回滚方案
如果出现问题，可以通过以下方式回滚：
1. 注释掉新增的记录代码
2. 重启 Bot
3. 数据库表不受影响（只是停止写入新数据）

---

## Performance Considerations

### 预期性能影响
- **权益曲线记录**: ~10-20ms per loop (Supabase 写入)
- **每日统计计算**: ~50-100ms per day (查询+计算)
- **风险指标计算**: ~50-100ms per trade (查询+计算)

### 优化策略
- 使用批量写入（如果适用）
- 缓存计算结果
- 异步执行（如果需要）

---

## Security Considerations

### 数据安全
- 使用现有的 Supabase 连接（已配置 RLS）
- 不涉及敏感数据处理
- 异常处理避免泄露敏感信息

---

## Testing Strategy

### 单元测试
- 测试 `_update_daily_stats()` 计算逻辑
- 测试 `_update_risk_metrics()` 计算逻辑
- 测试异常处理

### 集成测试
- 启动 Bot 运行一段时间
- 验证数据正确写入 Supabase
- 验证数据准确性

### 性能测试
- 测试记录功能的性能影响
- 确保总延迟 < 100ms

---

## Future Enhancements

### 短期优化
- 添加数据可视化功能
- 实现实时监控面板
- 优化批量写入性能

### 长期规划
- 实现更多统计指标
- 实现自动化报告生成
- 实现异常检测和告警
