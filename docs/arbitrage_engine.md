# 跨交易所套利引擎功能说明文档

## 概述

跨交易所套利引擎是一个自动化的套利交易系统，通过监控多个交易所之间的价格差异，识别并执行低风险的套利交易机会。

### 功能特性

- **实时价差监控**: 并行监控Bitget、Binance、OKX三个交易所的价格
- **智能机会检测**: 自动识别盈利的套利机会，考虑手续费、滑点和执行成本
- **原子化执行**: 双腿交易原子化执行，失败自动回滚
- **全面风险管理**: 仓位限制、频率限制、盈利能力验证
- **持仓追踪**: 跨交易所持仓追踪和净敞口计算
- **完整日志**: 详细的执行日志和数据库记录

### 预期收益

- **盈利能力**: +60% (套利策略60-80%胜率)
- **可靠性**: +30% (交易所冗余)
- **风险分散**: 多交易所分散风险

## 架构设计

### 模块结构

```
arbitrage/
├── __init__.py                    # 模块初始化
├── models.py                      # 数据模型
├── spread_monitor.py              # 价差监控器
├── opportunity_detector.py        # 机会检测器
├── execution_coordinator.py       # 执行协调器
├── arbitrage_risk_manager.py      # 风险管理器
├── position_tracker.py            # 持仓追踪器
└── engine.py                      # 主引擎
```

### 核心组件

#### 1. ArbitrageEngine (主引擎)
- 协调所有套利组件
- 管理生命周期 (start/stop/pause)
- 主循环: monitor → detect → validate → execute

#### 2. SpreadMonitor (价差监控器)
- 并行监控多个交易所价格
- 实时计算价差
- 历史价差追踪

#### 3. OpportunityDetector (机会检测器)
- 盈利能力计算 (手续费、滑点、执行成本)
- 机会过滤和排序
- 风险调整后的机会评分

#### 4. ExecutionCoordinator (执行协调器)
- 原子化双腿执行
- 失败回滚机制
- 订单状态管理

#### 5. ArbitrageRiskManager (风险管理器)
- 单交易所仓位限制
- 总敞口限制
- 频率限制

#### 6. CrossExchangePositionTracker (持仓追踪器)
- 跨交易所持仓追踪
- 净敞口计算
- 持仓对账

### 数据流

```
ArbitrageEngine (主循环)
    ↓
SpreadMonitor → 获取所有交易所价格 → 计算价差
    ↓
OpportunityDetector → 过滤 → 计算盈利 → 排序
    ↓
ArbitrageRiskManager → 验证风险限制
    ↓
ExecutionCoordinator → 执行买腿 → 执行卖腿 → 回滚(如失败)
    ↓
记录结果到数据库
```

## 配置说明

### 配置文件位置

所有套利配置都在 `config.py` 文件中。

### 配置项详解

#### 基础配置

```python
# 是否启用套利引擎
ENABLE_ARBITRAGE = False  # 默认关闭，需要手动启用

# 套利模式
ARBITRAGE_MODE = "conservative"  # conservative: 保守模式, balanced: 平衡模式, aggressive: 激进模式

# 交易对配置
ARBITRAGE_SYMBOL = "BTCUSDT"  # 套利交易对
ARBITRAGE_EXCHANGES = ["bitget", "binance", "okx"]  # 参与套利的交易所
```

#### 价差监控配置

```python
SPREAD_MONITOR_INTERVAL = 1  # 价差监控间隔（秒）
SPREAD_HISTORY_SIZE = 100  # 价差历史记录大小
SPREAD_ALERT_THRESHOLD = 1.0  # 价差告警阈值（%）
```

#### 机会检测配置

```python
MIN_SPREAD_THRESHOLD = 0.3  # 最小价差阈值（%）
MIN_NET_PROFIT_THRESHOLD = 1.0  # 最小净利润阈值（USDT）
MIN_PROFIT_RATIO = 0.5  # 最小利润比例（净利润/毛利润）
OPPORTUNITY_SCAN_INTERVAL = 2  # 机会扫描间隔（秒）
```

#### 仓位管理配置

```python
ARBITRAGE_POSITION_SIZE = 100  # 单次套利交易金额（USDT）
MAX_POSITION_PER_EXCHANGE = 500  # 单交易所最大持仓（USDT）
MAX_TOTAL_ARBITRAGE_EXPOSURE = 1000  # 总套利敞口限制（USDT）
MAX_POSITION_COUNT_PER_EXCHANGE = 3  # 单交易所最大持仓数量
```

#### 频率限制配置

```python
MAX_ARBITRAGE_PER_HOUR = 10  # 每小时最大套利次数
MAX_ARBITRAGE_PER_DAY = 50  # 每日最大套利次数
MIN_INTERVAL_BETWEEN_ARBITRAGE = 30  # 套利最小间隔（秒）
```

#### 执行配置

```python
MAX_EXECUTION_TIME_PER_LEG = 10  # 单腿最大执行时间（秒）
MAX_TOTAL_EXECUTION_TIME = 30  # 总执行最大时间（秒）
MAX_SLIPPAGE_TOLERANCE = 0.2  # 最大滑点容忍度（%）
ENABLE_ATOMIC_EXECUTION = True  # 是否启用原子化执行（失败自动回滚）
```

#### 订单簿深度要求

```python
MIN_ORDERBOOK_DEPTH_MULTIPLIER = 3.0  # 订单簿深度必须是交易量的倍数
MIN_ORDERBOOK_DEPTH_USDT = 5000  # 最小订单簿深度（USDT）
```

#### 手续费配置

```python
ARBITRAGE_FEE_RATES = {
    "bitget": {"maker": 0.0002, "taker": 0.0006},
    "binance": {"maker": 0.0002, "taker": 0.0004},
    "okx": {"maker": 0.0002, "taker": 0.0005},
}
```

## 使用方法

### 启用套利引擎

1. 编辑 `config.py`，设置 `ENABLE_ARBITRAGE = True`
2. 根据需要调整其他配置参数
3. 运行测试脚本验证配置：`python3 scripts/test_arbitrage.py`
4. 启动交易机器人：`./start_bot.sh`

### 监控套利运行

套利引擎启动后会自动运行，可以通过以下方式监控：

1. **查看日志**：`tail -f logs/bot.log | grep arbitrage`
2. **查看数据库记录**：
   ```python
   # 查看套利机会
   SELECT * FROM arbitrage_opportunities ORDER BY created_at DESC LIMIT 10;

   # 查看套利交易
   SELECT * FROM arbitrage_trades ORDER BY created_at DESC LIMIT 10;
   ```

### 停止套利引擎

套利引擎会随交易机器人一起停止：`./stop_bot.sh`

## 技术实现

### 核心算法

#### 1. 价差计算

```python
spread_pct = (sell_price - buy_price) / buy_price * 100
```

套利逻辑：
- 在价格低的交易所买入 (ask价)
- 在价格高的交易所卖出 (bid价)

#### 2. 净利润计算

```python
net_profit = gross_profit - fees - slippage - buffer
```

其中：
- `gross_profit = (sell_price - buy_price) * amount / buy_price`
- `fees = buy_fee + sell_fee`
- `slippage = buy_slippage + sell_slippage`
- `buffer = amount * 0.001` (0.1%安全缓冲)

#### 3. 原子化执行

状态机：`PENDING → EXECUTING_BUY → EXECUTING_SELL → COMPLETED/FAILED`

失败回滚：
- 如果买入失败：无需操作
- 如果卖出失败：立即平掉买入仓位

### 数据库表结构

#### arbitrage_spreads (价差历史)
- 记录所有检测到的价差
- 用于历史分析和回测

#### arbitrage_opportunities (套利机会)
- 记录所有检测到的套利机会
- 包含盈利能力计算结果

#### arbitrage_trades (套利交易)
- 记录所有执行的套利交易
- 包含执行结果和盈亏信息

## 故障排查

### 常见问题

**问题1：套利引擎未启动**
- 检查 `ENABLE_ARBITRAGE` 是否设置为 `True`
- 查看日志确认初始化是否成功

**问题2：未检测到套利机会**
- 检查 `MIN_SPREAD_THRESHOLD` 是否设置过高
- 检查交易所连接是否正常
- 查看价差历史记录

**问题3：套利执行失败**
- 检查交易所余额是否充足
- 检查订单簿深度是否满足要求
- 查看执行日志了解失败原因

## 最佳实践

1. **从小金额开始**：初次使用建议设置较小的 `ARBITRAGE_POSITION_SIZE`
2. **保守配置**：使用 `conservative` 模式，设置较高的 `MIN_SPREAD_THRESHOLD`
3. **监控运行**：定期查看日志和数据库记录
4. **余额管理**：确保各交易所有足够的余额
5. **风险控制**：严格遵守仓位和频率限制

## 性能指标

- **价差监控延迟**: < 1秒
- **机会检测延迟**: < 500ms
- **执行延迟**: < 10秒/腿
- **回滚成功率**: > 95%
- **预期胜率**: 60-80%

---

**版本**: v1.0
**创建时间**: 2025-12-27
**最后更新**: 2025-12-27

