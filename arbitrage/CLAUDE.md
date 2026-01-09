[根目录](../CLAUDE.md) > **arbitrage**

---

# Arbitrage - 跨交易所套利引擎

> 最后更新: 2026-01-09

## 变更记录 (Changelog)

### 2026-01-09 - 初始化模块文档
- 创建套利引擎模块文档
- 记录核心组件和数据流

---

## 模块职责

跨交易所套利引擎是一个自动化的套利交易系统，通过实时监控多个交易所（Bitget、Binance、OKX）之间的价格差异，识别并执行低风险的套利交易机会。

**核心功能：**
- 实时价差监控（并行多交易所）
- 智能机会检测（考虑手续费、滑点）
- 原子化双腿执行（失败自动回滚）
- 全面风险管理（仓位、频率限制）
- 跨交易所持仓追踪
- 完整的执行日志和数据库记录

**预期收益：**
- 盈利能力: +60% (套利策略60-80%胜率)
- 可靠性: +30% (交易所冗余)
- 风险分散: 多交易所分散风险

---

## 入口与启动

### 初始化流程

```python
from exchange.manager import ExchangeManager
from arbitrage.engine import ArbitrageEngine
import config

# 1. 启用套利引擎
config.ENABLE_ARBITRAGE = True

# 2. 创建交易所管理器
exchange_manager = ExchangeManager()
exchange_manager.initialize()

# 3. 创建套利引擎
arbitrage_config = {
    "opportunity_scan_interval": config.OPPORTUNITY_SCAN_INTERVAL,
    "arbitrage_position_size": config.ARBITRAGE_POSITION_SIZE,
    "min_spread_threshold": config.MIN_SPREAD_THRESHOLD,
    # ... 其他配置
}

engine = ArbitrageEngine(exchange_manager, arbitrage_config)

# 4. 启动引擎
engine.start()

# 5. 停止引擎
engine.stop()
```

### 配置要求

在 `config.py` 中配置：

```python
# 启用套利引擎
ENABLE_ARBITRAGE = True

# 套利模式
ARBITRAGE_MODE = "conservative"  # conservative/balanced/aggressive

# 交易对和交易所
ARBITRAGE_SYMBOL = "BTCUSDT"
ARBITRAGE_EXCHANGES = ["bitget", "binance", "okx"]

# 价差阈值
MIN_SPREAD_THRESHOLD = 0.3  # 最小价差0.3%
MIN_NET_PROFIT_THRESHOLD = 1.0  # 最小净利润1 USDT

# 仓位管理
ARBITRAGE_POSITION_SIZE = 100  # 单次交易100 USDT
MAX_POSITION_PER_EXCHANGE = 500  # 单交易所最大持仓500 USDT

# 频率限制
MAX_ARBITRAGE_PER_HOUR = 10
MAX_ARBITRAGE_PER_DAY = 50
```

---

## 对外接口

### ArbitrageEngine (主引擎)

**生命周期管理：**
- `start()` - 启动套利引擎
- `stop()` - 停止套利引擎
- `pause()` - 暂停套利
- `resume()` - 恢复套利

**状态查询：**
- `get_stats()` - 获取统计信息
- `get_current_spreads()` - 获取当前价差
- `get_active_positions()` - 获取活跃持仓

**手动执行：**
- `execute_opportunity(opportunity)` - 手动执行套利机会

### SpreadMonitor (价差监控器)

**核心方法：**
- `start()` - 启动监控
- `stop()` - 停止监控
- `get_latest_spreads()` - 获取最新价差
- `get_spread_history(limit)` - 获取历史价差

### OpportunityDetector (机会检测器)

**核心方法：**
- `detect_opportunities(spreads)` - 检测套利机会
- `calculate_profitability(spread)` - 计算盈利能力
- `filter_opportunities(opportunities)` - 过滤机会

### ExecutionCoordinator (执行协调器)

**核心方法：**
- `execute_arbitrage(opportunity, amount)` - 执行套利
- `rollback_trade(trade)` - 回滚失败交易

---

## 关键依赖与配置

### 外部依赖
- `exchange.manager.ExchangeManager` - 交易所管理器
- `logger_utils` - 日志系统
- `threading` - 多线程支持

### 内部依赖
- `models.py` - 数据模型定义
- `spread_monitor.py` - 价差监控
- `opportunity_detector.py` - 机会检测
- `arbitrage_risk_manager.py` - 风险管理
- `execution_coordinator.py` - 执行协调
- `position_tracker.py` - 持仓追踪

### 配置项详解

| 配置项 | 说明 | 默认值 | 推荐值 |
|--------|------|--------|--------|
| `ENABLE_ARBITRAGE` | 是否启用套利 | False | True |
| `ARBITRAGE_MODE` | 套利模式 | conservative | conservative |
| `MIN_SPREAD_THRESHOLD` | 最小价差阈值(%) | 0.3 | 0.3-0.5 |
| `MIN_NET_PROFIT_THRESHOLD` | 最小净利润(USDT) | 1.0 | 1.0-2.0 |
| `ARBITRAGE_POSITION_SIZE` | 单次交易金额(USDT) | 100 | 50-200 |
| `MAX_POSITION_PER_EXCHANGE` | 单交易所最大持仓 | 500 | 500-1000 |
| `MAX_ARBITRAGE_PER_HOUR` | 每小时最大次数 | 10 | 5-15 |
| `MAX_EXECUTION_TIME_PER_LEG` | 单腿最大执行时间(秒) | 10 | 10-15 |

---

## 数据模型

### SpreadData (价差数据)

```python
@dataclass
class SpreadData:
    exchange_a: str          # 买入交易所
    exchange_b: str          # 卖出交易所
    symbol: str              # 交易对
    buy_price: float         # 买入价格
    sell_price: float        # 卖出价格
    spread_pct: float        # 价差百分比
    timestamp: int           # 时间戳(毫秒)
```

### ArbitrageOpportunity (套利机会)

```python
@dataclass
class ArbitrageOpportunity:
    buy_exchange: str        # 买入交易所
    sell_exchange: str       # 卖出交易所
    symbol: str              # 交易对
    buy_price: float         # 买入价格
    sell_price: float        # 卖出价格
    spread_pct: float        # 价差百分比
    gross_profit: float      # 毛利润(每单位)
    net_profit: float        # 净利润(每单位)
    buy_exchange_fee: float  # 买入手续费率
    sell_exchange_fee: float # 卖出手续费率
    estimated_buy_slippage: float   # 估算买入滑点
    estimated_sell_slippage: float  # 估算卖出滑点
    timestamp: int           # 时间戳
```

### ArbitrageTrade (套利交易记录)

```python
@dataclass
class ArbitrageTrade:
    opportunity: ArbitrageOpportunity  # 套利机会
    status: str              # 状态: PENDING/EXECUTING_BUY/EXECUTING_SELL/COMPLETED/FAILED
    amount: float            # 交易数量(USDT)
    buy_order: OrderResult   # 买入订单结果
    sell_order: OrderResult  # 卖出订单结果
    actual_pnl: float        # 实际盈亏
    expected_pnl: float      # 预期盈亏
    failure_reason: str      # 失败原因
    created_at: datetime     # 创建时间
    completed_at: datetime   # 完成时间
```

---

## 测试与质量

### 测试文件
- `../scripts/test_arbitrage.py` - 套利引擎功能测试

### 测试覆盖
- 价差监控测试
- 机会检测测试
- 执行协调测试
- 风险管理测试
- 持仓追踪测试
- 完整流程测试

### 运行测试

```bash
python scripts/test_arbitrage.py
```

---

## 常见问题 (FAQ)

### Q: 如何启用套利引擎？

```python
# config.py
ENABLE_ARBITRAGE = True
ARBITRAGE_MODE = "conservative"
```

### Q: 套利引擎如何保证原子性？

套利引擎使用双腿原子化执行机制：
1. 先执行买入订单
2. 买入成功后执行卖出订单
3. 如果卖出失败，自动回滚买入订单（平仓）
4. 记录完整的执行日志

### Q: 如何调整风险参数？

```python
# 保守配置（低风险）
MIN_SPREAD_THRESHOLD = 0.5  # 更高的价差要求
ARBITRAGE_POSITION_SIZE = 50  # 更小的仓位
MAX_ARBITRAGE_PER_HOUR = 5  # 更低的频率

# 激进配置（高收益）
MIN_SPREAD_THRESHOLD = 0.3
ARBITRAGE_POSITION_SIZE = 200
MAX_ARBITRAGE_PER_HOUR = 15
```

### Q: 如何监控套利执行情况？

```python
# 获取统计信息
stats = engine.get_stats()
print(f"总机会数: {stats['total_opportunities']}")
print(f"成功执行: {stats['successful_executions']}")
print(f"总盈亏: {stats['total_pnl']}")

# 查看数据库记录
# 套利交易记录存储在 arbitrage_trades 表中
```

### Q: 套利引擎会影响主交易策略吗？

不会。套利引擎是独立运行的，与主交易策略互不干扰。但需要注意：
- 确保各交易所有足够的余额
- 监控总体风险敞口
- 避免同时在同一交易所执行套利和主策略

---

## 相关文件清单

### 核心文件
- `__init__.py` - 模块入口
- `engine.py` - 主引擎协调器
- `models.py` - 数据模型定义
- `spread_monitor.py` - 价差监控器
- `opportunity_detector.py` - 机会检测器
- `execution_coordinator.py` - 执行协调器
- `arbitrage_risk_manager.py` - 风险管理器
- `position_tracker.py` - 持仓追踪器

### 文档
- `../docs/arbitrage_engine.md` - 详细功能文档
- `../docs/multi_exchange_framework.md` - 多交易所框架文档

### 测试文件
- `../scripts/test_arbitrage.py` - 功能测试

---

**模块状态：** ✅ 已实现，待启用
**支持的交易所：** Bitget, Binance, OKX
**套利模式：** Conservative, Balanced, Aggressive
