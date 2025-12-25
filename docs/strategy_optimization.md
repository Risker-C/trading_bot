# 策略优化功能说明文档

## 概述

本文档描述了交易系统的策略优化功能，包括策略筛选、reason字段记录修复、以及策略级差异化止损配置。这些优化基于历史交易数据分析，旨在提高系统的整体盈利能力和风险控制水平。

## 功能特性

### 1. 策略筛选优化
- 基于历史数据分析，禁用表现差的策略
- 启用表现优秀的策略（multi_timeframe、adx_trend）
- 保留表现中等的基础策略

### 2. 策略记录修复
- 修复开单时reason字段为空的bug
- 完整记录策略名称和开单原因
- 便于后续分析和追溯决策依据

### 3. 策略级差异化止损
- 根据策略历史表现设置不同的止损参数
- 表现优秀的策略获得更大的止损空间
- 表现中等的策略使用标准止损配置

## 配置说明

### 配置文件位置
`config.py`

### 配置项详解

#### 1. 策略启用配置
```python
ENABLE_STRATEGIES: List[str] = [
    "bollinger_trend",        # 顺势策略
    "macd_cross",
    "ema_cross",
    "composite_score",
    "multi_timeframe",        # 启用：胜率30%但盈亏比1.76
    "adx_trend",              # 启用：胜率50%，盈亏比0.97
]
```

#### 2. 全局止损配置
```python
STOP_LOSS_PERCENT = 0.045      # 止损比例 4.5%
TAKE_PROFIT_PERCENT = 0.03     # 止盈比例 3%
TRAILING_STOP_PERCENT = 0.03   # 移动止损 3%
ATR_STOP_MULTIPLIER = 4.0      # ATR倍数 4.0
```

#### 3. 策略级差异化止损配置
```python
# 是否启用策略级差异化止损
USE_STRATEGY_SPECIFIC_STOPS = True

# 策略级止损配置
STRATEGY_STOP_CONFIGS = {
    "multi_timeframe": {
        "stop_loss_pct": 0.05,      # 5% 止损
        "take_profit_pct": 0.04,    # 4% 止盈
        "trailing_stop_pct": 0.035, # 3.5% 移动止损
        "atr_multiplier": 4.5,      # ATR倍数4.5
    },
    "adx_trend": {
        "stop_loss_pct": 0.045,     # 4.5% 止损
        "take_profit_pct": 0.03,    # 3% 止盈
        "trailing_stop_pct": 0.03,  # 3% 移动止损
        "atr_multiplier": 4.0,      # ATR倍数4.0
    },
}
```

## 使用方法

### 1. 启用策略优化
策略优化功能默认启用，无需额外配置。

### 2. 查看策略表现
使用分析脚本查看策略历史表现：
```bash
python3 analyze_strategy_performance.py
```

### 3. 调整策略配置
根据分析结果，在`config.py`中调整：
- `ENABLE_STRATEGIES`：启用/禁用策略
- `STRATEGY_STOP_CONFIGS`：调整策略级止损参数

### 4. 重启服务
修改配置后需要重启服务：
```bash
./stop_bot.sh
./start_bot.sh
```

## 技术实现

### 核心模块

#### 1. 策略分析模块
- **文件**：`analyze_strategy_performance.py`
- **功能**：分析历史交易数据，统计各策略表现
- **输出**：策略胜率、盈亏比、总盈亏等指标

#### 2. 配置模块
- **文件**：`config.py`
- **功能**：存储策略配置和止损参数
- **新增配置**：
  - `USE_STRATEGY_SPECIFIC_STOPS`
  - `STRATEGY_STOP_CONFIGS`

#### 3. 风控模块
- **文件**：`risk_manager.py`
- **新增方法**：
  - `_calculate_strategy_specific_stop_loss()`：计算策略级止损
  - `calculate_stop_loss()`：支持strategy参数
  - `calculate_take_profit()`：支持strategy参数
  - `set_position()`：支持strategy参数

#### 4. 交易模块
- **文件**：`trader.py`
- **修改方法**：
  - `open_long()`：添加strategy和reason参数
  - `open_short()`：添加strategy和reason参数

#### 5. 主程序
- **文件**：`bot.py`
- **修改**：调用`open_long/open_short`时传递strategy和reason

### 数据流程

```
策略生成信号 (strategies.py)
    ↓
TradeSignal (包含strategy和reason)
    ↓
bot.py 执行开仓
    ↓
trader.open_long/open_short (传递strategy和reason)
    ↓
risk_manager.set_position (传递strategy)
    ↓
计算策略级差异化止损
    ↓
db.log_trade (记录strategy和reason)
```

## 故障排查

### 问题1：策略记录仍然为空
**症状**：trades表中strategy和reason字段为空

**排查步骤**：
1. 检查bot.py中是否正确传递了signal.strategy和signal.reason
2. 检查trader.py中是否正确接收了参数
3. 检查db.log_trade()调用是否包含strategy和reason参数

**解决方法**：
```python
# bot.py中确保这样调用
result = self.trader.open_long(
    amount,
    df,
    strategy=signal.strategy,
    reason=signal.reason
)
```

### 问题2：差异化止损未生效
**症状**：所有策略使用相同的止损

**排查步骤**：
1. 检查`USE_STRATEGY_SPECIFIC_STOPS`是否为True
2. 检查`STRATEGY_STOP_CONFIGS`中是否有对应策略的配置
3. 查看日志中是否有"使用策略 XXX 的差异化止损"的信息

**解决方法**：
```python
# 确保config.py中配置正确
USE_STRATEGY_SPECIFIC_STOPS = True
STRATEGY_STOP_CONFIGS = {
    "multi_timeframe": {...},
    "adx_trend": {...},
}
```

### 问题3：策略未按预期启用/禁用
**症状**：禁用的策略仍在生成信号

**排查步骤**：
1. 检查`ENABLE_STRATEGIES`列表
2. 检查是否启用了动态策略选择（`USE_DYNAMIC_STRATEGY`）
3. 重启服务确保配置生效

**解决方法**：
```bash
# 修改config.py后重启
./stop_bot.sh
./start_bot.sh
```

## 性能优化

### 1. 策略筛选优化
- **优化前**：7个策略，整体胜率45.3%
- **优化后**：6个策略，禁用表现最差的rsi_divergence
- **预期效果**：提高整体胜率和盈亏比

### 2. 止损优化
- **优化前**：固定4%止损，ATR倍数3.5
- **优化后**：全局4.5%止损，ATR倍数4.0
- **策略级**：multi_timeframe 5%止损，ATR倍数4.5
- **预期效果**：减少止损触发频率，提高盈利单持有时间

### 3. 记录完整性
- **优化前**：strategy和reason字段为空
- **优化后**：完整记录策略信息
- **效果**：便于后续分析和优化

## 扩展开发

### 添加新策略的差异化配置

1. 在`config.py`中添加配置：
```python
STRATEGY_STOP_CONFIGS = {
    # 现有配置...
    "new_strategy": {
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.03,
        "trailing_stop_pct": 0.03,
        "atr_multiplier": 4.0,
    },
}
```

2. 重启服务使配置生效

### 动态调整策略参数

可以基于实时表现动态调整策略参数：
```python
# 在risk_manager.py中添加
def update_strategy_config(self, strategy: str, new_config: dict):
    """动态更新策略配置"""
    if hasattr(config, 'STRATEGY_STOP_CONFIGS'):
        config.STRATEGY_STOP_CONFIGS[strategy] = new_config
        logger.info(f"更新策略 {strategy} 配置: {new_config}")
```

## 最佳实践

### 1. 定期分析策略表现
建议每周运行一次策略分析：
```bash
python3 analyze_strategy_performance.py
```

### 2. 渐进式调整
- 不要一次性大幅调整参数
- 每次只调整一个参数
- 观察1-2天后再做下一步调整

### 3. 保留历史配置
修改配置前备份：
```bash
cp config.py config.py.backup_$(date +%Y%m%d_%H%M%S)
```

### 4. 监控关键指标
重点关注：
- 开单频率
- 胜率变化
- 盈亏比变化
- 止损触发频率

## 更新日志

### v1.0.0 (2025-12-25)
- 初始版本
- 实现策略筛选优化
- 修复reason字段记录bug
- 实现策略级差异化止损

## 相关文档

- [数据库开发规范](database_standards.md)
- [功能开发标准流程](../README.md)
- [风险管理文档](risk_management.md)
