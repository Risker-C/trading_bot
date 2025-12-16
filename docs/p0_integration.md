# P0模块集成功能说明文档

## 概述

本文档说明P0核心模块（影子模式、Claude护栏、性能分析器）的集成方案。这些模块为交易系统提供了**可验证、可迭代、更稳定**的基础架构。

**版本**: v1.0.0
**创建日期**: 2025-01-15
**状态**: 开发中

## 功能特性

### 1. 影子模式（Shadow Mode）
- **记录完整决策链**：记录每个信号在各阶段的决策（策略→趋势过滤→Claude→执行层风控）
- **A/B对比分析**：对比不同配置的效果（仅策略 vs 策略+趋势 vs 策略+趋势+Claude）
- **不影响执行**：影子模式只记录，不影响实际交易决策

### 2. Claude护栏（Claude Guardrails）
- **预算控制**：日调用次数和成本上限
- **缓存机制**：同一K线/同一信号不重复调用（5分钟缓存）
- **响应验证**：JSON Schema严格校验
- **降级策略**：失败时自动降级（pass/reject模式）

### 3. 性能分析器（Performance Analyzer）
- **6大核心指标**：最大回撤、连续亏损P95、盈亏比、单笔期望、平均滑点、胜率
- **分阶段拒绝分析**：统计各阶段拒绝的信号数量和原因
- **Claude性能分析**：按置信度分组分析Claude的准确率
- **策略对比**：对比不同策略的表现

## 配置说明

### 配置文件位置
`config.py`

### 配置项详解

```python
# ==================== 影子模式配置 ====================

# 是否启用影子模式（记录所有决策但不影响执行）
ENABLE_SHADOW_MODE = False  # 默认关闭，建议先观察1-2天再启用

# ==================== Claude护栏配置 ====================

# Claude缓存时间（秒）
CLAUDE_CACHE_TTL = 300  # 5分钟

# Claude日调用上限
CLAUDE_MAX_DAILY_CALLS = 500

# Claude日成本上限（美元）
CLAUDE_MAX_DAILY_COST = 10.0
```

**配置建议：**
- **ENABLE_SHADOW_MODE**: 建议先设为False，观察系统稳定性后再启用
- **CLAUDE_CACHE_TTL**: 5分钟适合15分钟K线，如果使用5分钟K线可以缩短到180秒
- **CLAUDE_MAX_DAILY_CALLS**: 根据交易频率调整，高频交易建议设为1000
- **CLAUDE_MAX_DAILY_COST**: 根据预算调整，Sonnet模型约$0.015/次

## 使用方法

### 1. 启用影子模式

**步骤1**: 修改配置
```python
# config.py
ENABLE_SHADOW_MODE = True
```

**步骤2**: 重启服务
```bash
./stop_bot.sh
./start_bot.sh
```

**步骤3**: 观察日志
```bash
tail -f logs/trading_bot.log | grep "影子模式"
```

**步骤4**: 查看数据
```bash
sqlite3 trading_bot.db "SELECT COUNT(*) FROM shadow_decisions;"
```

### 2. 查看性能分析

**方法1**: 使用命令行工具
```bash
python performance_analyzer.py --start 2025-01-01 --end 2025-01-15
```

**方法2**: 使用Python API
```python
from performance_analyzer import PerformanceAnalyzer

analyzer = PerformanceAnalyzer()
report = analyzer.analyze_period(
    start_date='2025-01-01',
    end_date='2025-01-15'
)
analyzer.print_report(report)
```

**方法3**: 使用SQL查询
```bash
# 查看6大核心指标
sqlite3 trading_bot.db < SQL_ANALYSIS_TEMPLATES.md
```

### 3. 查看Claude护栏统计

```python
from claude_guardrails import get_guardrails

guardrails = get_guardrails()
guardrails.print_stats()
```

**输出示例：**
```
============================================================
Claude护栏统计
============================================================
总调用次数: 150
今日调用: 45 / 500
今日成本: $0.68 / $10.00

缓存命中: 23 (15.3%)
缓存大小: 12

验证失败: 2
超时失败: 0
预算停止: 0

剩余调用: 455
剩余预算: $9.32
============================================================
```

## 技术实现

### 核心模块

1. **shadow_mode.py**
   - `ShadowModeTracker`: 影子模式追踪器
   - `record_decision()`: 记录决策
   - `update_actual_result()`: 更新实际结果
   - `get_ab_comparison()`: 获取A/B对比

2. **claude_guardrails.py**
   - `ClaudeGuardrails`: Claude护栏
   - `check_budget()`: 预算检查
   - `check_cache()`: 缓存检查
   - `validate_response()`: 响应验证
   - `record_call()`: 记录调用

3. **performance_analyzer.py**
   - `PerformanceAnalyzer`: 性能分析器
   - `analyze_period()`: 分析时期
   - `_calculate_core_metrics()`: 计算核心指标
   - `_analyze_rejections()`: 分析拒绝

### 数据流程

```
信号生成
  ↓
[shadow_mode] 记录: would_execute_strategy=True
  ↓
趋势过滤
  ↓
[shadow_mode] 记录: would_execute_after_trend
  ↓
[guardrails] 预算检查 + 缓存检查
  ↓
Claude分析
  ↓
[guardrails] 记录调用成本
[shadow_mode] 记录: would_execute_after_claude
  ↓
执行开仓
  ↓
[shadow_mode] 记录: actually_executed=True
  ↓
平仓
  ↓
[shadow_mode] 更新: actual_pnl
[performance_analyzer] 计算指标
```

### 数据库表结构

**shadow_decisions表**（25个字段）
- 记录每个信号的完整决策链
- 支持A/B对比分析

**trade_tags表**（42个字段）
- 记录完整的交易信息
- 支持性能分析和回测

详见：`SQL_ANALYSIS_TEMPLATES.md`

## 故障排查

### 问题1: 影子模式未记录数据

**症状**: `shadow_decisions`表为空

**排查步骤**:
```bash
# 1. 检查配置
grep ENABLE_SHADOW_MODE config.py

# 2. 检查日志
tail -f logs/trading_bot.log | grep "影子模式"

# 3. 检查数据库
sqlite3 trading_bot.db "SELECT COUNT(*) FROM shadow_decisions;"
```

**解决方案**:
- 确认`ENABLE_SHADOW_MODE = True`
- 确认服务已重启
- 确认有信号生成

### 问题2: Claude护栏总是拒绝

**症状**: 所有Claude调用都被预算限制拒绝

**排查步骤**:
```python
from claude_guardrails import get_guardrails
guardrails = get_guardrails()
stats = guardrails.get_stats()
print(f"今日调用: {stats['daily_calls']} / {guardrails.max_daily_calls}")
print(f"今日成本: ${stats['daily_cost']:.2f} / ${guardrails.max_daily_cost:.2f}")
```

**解决方案**:
- 增加`CLAUDE_MAX_DAILY_CALLS`
- 增加`CLAUDE_MAX_DAILY_COST`
- 等待第二天自动重置

### 问题3: 性能分析器报错

**症状**: `performance_analyzer.py`执行失败

**排查步骤**:
```bash
# 检查数据库
sqlite3 trading_bot.db ".tables"

# 检查trade_tags表
sqlite3 trading_bot.db "SELECT COUNT(*) FROM trade_tags WHERE executed = 1;"
```

**解决方案**:
- 确认`trade_tags`表存在
- 确认有已执行的交易记录
- 检查日期范围是否正确

### 问题4: 缓存命中率过低

**症状**: Claude缓存命中率<5%

**原因分析**:
- 缓存TTL过短
- 信号变化频繁
- 指标波动大

**解决方案**:
```python
# 增加缓存时间
CLAUDE_CACHE_TTL = 600  # 10分钟
```

## 性能优化

### 1. 减少Claude调用成本

**策略1**: 提高缓存命中率
```python
# 增加缓存时间
CLAUDE_CACHE_TTL = 600  # 10分钟

# 降低信号强度阈值（只分析强信号）
CLAUDE_MIN_SIGNAL_STRENGTH = 0.6
```

**策略2**: 使用Haiku模型
```python
# 成本降低75%
CLAUDE_MODEL = "claude-haiku-4-20250514"
```

**策略3**: 分层调用
```python
# 弱信号用Haiku，强信号用Sonnet
if signal.strength < 0.7:
    model = "haiku"
else:
    model = "sonnet"
```

### 2. 优化影子模式性能

**策略1**: 异步写入
```python
# 使用线程池异步写入数据库
import concurrent.futures
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
executor.submit(shadow_tracker.record_decision, ...)
```

**策略2**: 批量写入
```python
# 累积10条记录后批量写入
if len(pending_records) >= 10:
    batch_insert(pending_records)
```

### 3. 优化性能分析器

**策略1**: 定期分析
```python
# 每天凌晨自动生成报告
import schedule
schedule.every().day.at("00:00").do(generate_daily_report)
```

**策略2**: 增量分析
```python
# 只分析新增的交易
analyzer.analyze_period(start_date=last_analysis_date)
```

## 扩展开发

### 1. 添加新的性能指标

```python
# 在performance_analyzer.py中添加
def _calculate_sharpe_ratio(self, trades):
    """计算夏普比率"""
    returns = [t['pnl_pct'] for t in trades]
    return np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
```

### 2. 添加新的影子模式记录

```python
# 在shadow_mode.py中添加新字段
def record_decision(self, ..., custom_field=None):
    data['custom_field'] = custom_field
```

### 3. 自定义Claude护栏规则

```python
# 在claude_guardrails.py中添加
def check_custom_rule(self, signal):
    """自定义规则检查"""
    if signal.strength < 0.3:
        return False, "信号强度过低"
    return True, "通过"
```

## 最佳实践

### 1. 渐进式启用

**第1天**: 只启用影子模式，不启用Claude
```python
ENABLE_SHADOW_MODE = True
ENABLE_CLAUDE_ANALYSIS = False
```

**第2-3天**: 观察影子模式数据，确认无问题

**第4天**: 启用Claude分析
```python
ENABLE_CLAUDE_ANALYSIS = True
CLAUDE_MODEL = "claude-haiku-4-20250514"  # 先用便宜的
```

**第5-7天**: 观察效果，考虑升级到Sonnet

### 2. 定期监控

**每天**:
- 查看Claude成本：`guardrails.print_stats()`
- 查看影子模式记录数：`SELECT COUNT(*) FROM shadow_decisions`

**每周**:
- 生成性能报告：`python performance_analyzer.py --export weekly.csv`
- 分析A/B对比：`shadow_tracker.get_ab_comparison()`

**每月**:
- 全面性能评估
- 参数调优
- 成本优化

### 3. 数据备份

```bash
# 每天备份数据库
cp trading_bot.db backups/trading_bot_$(date +%Y%m%d).db

# 导出CSV
python performance_analyzer.py --export monthly_$(date +%Y%m).csv
```

## 更新日志

### v1.0.0 (2025-01-15)
- 初始版本
- 实现影子模式、Claude护栏、性能分析器
- 完成基础集成

## 相关文档

- [SQL分析模板](../SQL_ANALYSIS_TEMPLATES.md)
- [集成示例](../INTEGRATION_EXAMPLE.md)
- [升级路线图](../UPGRADE_ROADMAP.md)
- [Claude集成指南](../CLAUDE_INTEGRATION_GUIDE.md)

## 支持

如有问题，请查看：
- 日志文件: `logs/trading_bot.log`
- 数据库: `trading_bot.db`
- 测试脚本: `scripts/test_p0_integration.py`
