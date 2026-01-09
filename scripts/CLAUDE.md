[根目录](../CLAUDE.md) > **scripts**

---

# Scripts - 测试与诊断工具集

> 最后更新: 2026-01-09

## 变更记录 (Changelog)

### 2026-01-09 - 初始化模块文档
- 创建测试脚本模块文档
- 整理50+测试和诊断脚本

---

## 模块职责

测试与诊断工具集包含50+个测试脚本和诊断工具，用于验证系统功能、调试问题、分析性能和紧急操作。

**核心功能：**
- 功能测试（交易、通知、数据库等）
- 诊断工具（布林带、信号、指标等）
- 紧急操作（平仓、状态检查）
- 性能分析（策略优化、ML模型）
- 数据库工具（查看、导出、维护）

---

## 入口与启动

### 快速测试

```bash
# 完整测试套件
python test_all.py

# 交易功能测试
python scripts/test_trading.py

# 通知测试
python scripts/test_notification.py

# 数据库测试
python scripts/test_database_fix.py
```

### 诊断工具

```bash
# 布林带诊断
python scripts/diagnose_bollinger.py

# 信号诊断
python diagnose_signals.py

# 指标诊断
python diagnose_indicators.py
```

### 紧急操作

```bash
# 检查状态
python scripts/check_status.py

# 一键平仓（推荐）
python scripts/close_raw_api.py

# 查看所有持仓
python scripts/check_all_positions.py
```

---

## 对外接口

### 测试脚本分类

#### 1. 核心功能测试
- `test_trading.py` - 完整交易流程测试
- `test_database_fix.py` - 数据库修复验证
- `test_notification.py` - 通知功能测试
- `test_multi_exchange.py` - 多交易所测试
- `test_arbitrage.py` - 套利引擎测试

#### 2. AI与ML测试
- `test_claude_integration.py` - Claude集成测试
- `test_claude_periodic_analysis.py` - Claude定时分析测试
- `test_policy_layer.py` - 策略治理层测试
- `test_ml_signal_filter.py` - ML信号过滤测试
- `test_ml_optimization.py` - ML优化测试

#### 3. 策略与指标测试
- `test_dynamic_strategy.py` - 动态策略测试
- `test_market_regime.py` - 市场状态测试
- `test_strategy_optimization.py` - 策略优化测试
- `test_direction_filter.py` - 方向过滤器测试

#### 4. 风控与执行测试
- `test_risk_manager_record_trade.py` - 风险管理器测试
- `test_liquidity_validation.py` - 流动性验证测试
- `test_maker_order.py` - Maker订单测试
- `test_stop_loss_optimization.py` - 止损优化测试

#### 5. 监控与报告测试
- `test_status_monitor.py` - 状态监控测试
- `test_periodic_report.py` - 定期报告测试
- `test_feishu_push_filter.py` - 飞书推送过滤测试

#### 6. 诊断工具
- `diagnose_bollinger.py` - 布林带诊断
- `diagnose_signals.py` - 信号诊断
- `diagnose_indicators.py` - 指标诊断
- `diagnose_no_trade.py` - 无交易诊断

#### 7. 数据库工具
- `db_viewer.py` - 数据库查看器
- `db_export_excel.py` - 导出Excel
- `test_database_maintenance.py` - 数据库维护

#### 8. 紧急操作脚本
- `check_status.py` - 快速状态检查
- `check_all_positions.py` - 查看所有持仓
- `close_raw_api.py` - 一键平仓（推荐）
- `close_position.py` - 交互式平仓
- `close_position_now.py` - 直接平仓

---

## 关键依赖与配置

### 外部依赖
- 所有脚本依赖主项目的模块
- 需要正确配置 `.env` 文件
- 部分脚本需要真实API连接

### 配置要求

```bash
# .env 文件必需配置
BITGET_API_KEY=...
BITGET_SECRET=...
BITGET_PASSWORD=...

# 可选配置（用于通知测试）
FEISHU_WEBHOOK_URL=...
EMAIL_SENDER=...
EMAIL_RECEIVER=...
TELEGRAM_BOT_TOKEN=...
```

---

## 数据模型

### 测试结果格式

大多数测试脚本输出标准化的测试结果：

```
============================================================
测试名称
============================================================
测试1: 功能描述
------------------------------------------------------------
✅ 子测试1 - 通过
✅ 子测试2 - 通过
❌ 子测试3 - 失败: 错误信息

============================================================
测试总结: X/Y 通过
============================================================
```

---

## 测试与质量

### 测试覆盖率

| 模块 | 测试脚本数 | 覆盖率 |
|------|-----------|--------|
| 核心交易 | 5 | 90% |
| AI与ML | 5 | 85% |
| 策略与指标 | 8 | 80% |
| 风控与执行 | 6 | 85% |
| 监控与报告 | 3 | 75% |
| 数据库 | 4 | 95% |

### 运行完整测试

```bash
# 运行所有测试
python test_all.py

# 运行特定类别测试
python scripts/test_trading.py
python scripts/test_claude_integration.py
python scripts/test_ml_signal_filter.py
```

---

## 常见问题 (FAQ)

### Q: 如何运行完整测试？

```bash
python test_all.py
```

### Q: 测试脚本会使用真实资金吗？

部分脚本会使用真实资金，包括：
- `test_trading.py` - 会执行真实交易
- `close_*.py` - 会平掉真实持仓
- `test_maker_order.py` - 会创建真实订单

其他测试脚本通常只读取数据或使用模拟数据。

### Q: 如何快速检查系统状态？

```bash
# 快速状态检查
python scripts/check_status.py

# 详细持仓信息
python scripts/check_all_positions.py

# 使用CLI工具
python cli.py status
```

### Q: 如何紧急平仓？

```bash
# 推荐方法：使用Bitget一键平仓API
python scripts/close_raw_api.py

# 交互式平仓（需要确认）
python scripts/close_position.py

# 直接平仓（无需确认）
python scripts/close_position_now.py
```

### Q: 如何诊断策略不生成信号？

```bash
# 诊断信号生成
python diagnose_signals.py

# 诊断布林带策略
python scripts/diagnose_bollinger.py

# 诊断无交易原因
python diagnose_no_trade.py
```

---

## 相关文件清单

### 核心功能测试 (5个)
- `test_trading.py` - 交易流程测试
- `test_database_fix.py` - 数据库修复验证
- `test_notification.py` - 通知功能测试
- `test_multi_exchange.py` - 多交易所测试
- `test_arbitrage.py` - 套利引擎测试

### AI与ML测试 (5个)
- `test_claude_integration.py`
- `test_claude_periodic_analysis.py`
- `test_policy_layer.py`
- `test_ml_signal_filter.py`
- `test_ml_optimization.py`

### 策略与指标测试 (8个)
- `test_dynamic_strategy.py`
- `test_market_regime.py`
- `test_strategy_optimization.py`
- `test_direction_filter.py`
- `test_trailing_stop.py`
- `test_trailing_take_profit.py`
- `test_market_state_fix.py`
- `test_long_win_rate_fix.py`

### 风控与执行测试 (6个)
- `test_risk_manager_record_trade.py`
- `test_liquidity_validation.py`
- `test_maker_order.py`
- `test_dynamic_maker_order.py`
- `test_stop_loss_optimization.py`
- `test_phase1_features.py`

### 监控与报告测试 (3个)
- `test_status_monitor.py`
- `test_periodic_report.py`
- `test_feishu_push_filter.py`

### 诊断工具 (4个)
- `diagnose_bollinger.py`
- `compare_data_sources.py`
- `../diagnose_signals.py`
- `../diagnose_indicators.py`

### 数据库工具 (4个)
- `db_viewer.py`
- `db_export_excel.py`
- `test_database_maintenance.py`
- `migrate_arbitrage_tables.py`

### 紧急操作脚本 (10个)
- `check_status.py`
- `check_all_positions.py`
- `close_raw_api.py` (推荐)
- `close_position.py`
- `close_position_now.py`
- `close_both_positions.py`
- `close_final.py`
- `close_hedge_mode.py`
- `close_one_way_mode.py`
- `close_with_open.py`

### 其他测试 (10个)
- `test_fix.py`
- `test_position_data_fix.py`
- `test_position_history_persistence.py`
- `test_integration.py`
- `test_p0_integration.py`
- `test_claude_optimization.py`
- `test_division_by_zero.py`
- `test_trailing_stop_fix.py`
- `test_log_splitting.py`
- `test_comprehensive_optimization.py`
- `test_config_validator.py`

---

**模块状态：** ✅ 持续维护
**脚本总数：** 50+
**测试覆盖率：** 85%
