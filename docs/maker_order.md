# Maker订单功能说明文档

## 概述

Maker订单功能通过使用限价单（Limit Order）替代市价单（Market Order），将交易手续费从0.06%降低到0.02%，节省67%的交易成本。该功能采用智能降级策略，在限价单未成交时自动转为市价单，确保不错过交易机会。

**核心优势：**
- 手续费降低67%（从0.06%降至0.02%）
- 年度可节省约292 USDT（基于每天10笔交易）
- 智能降级机制，不影响交易执行
- 完全向后兼容，可随时切换

## 功能特性

### 1. 智能订单类型选择
- 根据配置自动选择Maker或Taker订单
- 支持运行时动态切换
- 保持原有交易逻辑不变

### 2. 自动降级机制
- 限价单超时未成交时自动取消
- 自动转为市价单立即成交
- 避免错过交易机会

### 3. 精确价格控制
- 做多：挂单价格略低于市价（0.01%）
- 做空：挂单价格略高于市价（0.01%）
- 确保成为Maker获得费率优惠

### 4. 完整监控和日志
- 记录订单创建、等待、成交全过程
- 统计Maker订单成功率
- 便于后续优化调整

## 配置说明

### 配置文件位置
`/root/trading_bot/config.py`

### 配置项详解

```python
# ==================== Maker订单配置 ====================

# 是否启用Maker订单（限价单）
USE_MAKER_ORDER = True  # True: 使用限价单（手续费0.02%），False: 使用市价单（手续费0.06%）

# Maker订单超时时间（秒）
# 如果限价单在此时间内未成交，将自动取消并转为市价单
MAKER_ORDER_TIMEOUT = 10  # 10秒超时

# Maker订单价格偏移量（百分比）
# 做多时：挂单价格 = 当前价格 * (1 - offset)，即略低于市价
# 做空时：挂单价格 = 当前价格 * (1 + offset)，即略高于市价
MAKER_PRICE_OFFSET = 0.0001  # 0.01%的价格偏移，确保成为Maker

# Maker订单检查间隔（秒）
MAKER_ORDER_CHECK_INTERVAL = 0.5  # 每0.5秒检查一次订单状态

# 是否在Maker订单失败时自动降级为市价单
MAKER_AUTO_FALLBACK_TO_MARKET = True  # 建议开启，避免错过交易机会

# 手续费率配置
TRADING_FEE_RATE_MAKER = 0.0002  # Bitget Maker费率 0.02%
TRADING_FEE_RATE_TAKER = 0.0006  # Bitget Taker费率 0.06%

# 当前使用的手续费率（根据USE_MAKER_ORDER自动选择）
TRADING_FEE_RATE = TRADING_FEE_RATE_MAKER if USE_MAKER_ORDER else TRADING_FEE_RATE_TAKER
```

### 配置参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| USE_MAKER_ORDER | bool | True | 是否启用Maker订单 |
| MAKER_ORDER_TIMEOUT | int | 10 | 超时时间（秒） |
| MAKER_PRICE_OFFSET | float | 0.0001 | 价格偏移量（0.01%） |
| MAKER_ORDER_CHECK_INTERVAL | float | 0.5 | 检查间隔（秒） |
| MAKER_AUTO_FALLBACK_TO_MARKET | bool | True | 是否自动降级 |
| TRADING_FEE_RATE_MAKER | float | 0.0002 | Maker费率（0.02%） |
| TRADING_FEE_RATE_TAKER | float | 0.0006 | Taker费率（0.06%） |

## 使用方法

### 启用Maker订单

1. 编辑配置文件：
```bash
vim config.py
```

2. 设置启用标志：
```python
USE_MAKER_ORDER = True
```

3. 重启交易机器人：
```bash
./stop_bot.sh
./start_bot.sh
```

### 禁用Maker订单

如果需要临时禁用Maker订单，恢复使用市价单：

```python
USE_MAKER_ORDER = False
```

### 调整超时时间

根据市场流动性调整超时时间：

```python
# 高流动性市场：缩短超时时间
MAKER_ORDER_TIMEOUT = 5  # 5秒

# 低流动性市场：延长超时时间
MAKER_ORDER_TIMEOUT = 15  # 15秒
```

### 调整价格偏移

根据成交率调整价格偏移：

```python
# 提高成交率：增大偏移量
MAKER_PRICE_OFFSET = 0.0002  # 0.02%

# 降低滑点：减小偏移量
MAKER_PRICE_OFFSET = 0.00005  # 0.005%
```

## 技术实现

### 核心模块

**1. 智能下单方法（trader.py）**
```python
def create_smart_order(self, side: str, amount: float, reduce_only: bool = False) -> Optional[Dict]:
    """智能下单：根据配置选择Maker或Taker订单"""
    # 1. 检查配置
    # 2. 获取当前价格
    # 3. 计算挂单价格
    # 4. 创建限价单
    # 5. 等待成交
    # 6. 超时降级为市价单
```

**2. 限价单创建（trader.py）**
```python
def create_limit_order(self, side: str, amount: float, price: float, reduce_only: bool = False) -> Optional[Dict]:
    """创建限价单（Maker订单）"""
```

**3. 订单监控（trader.py）**
```python
def wait_for_order_fill(self, order_id: str, timeout: float = None) -> Tuple[bool, Optional[Dict]]:
    """等待订单成交"""
```

**4. 订单取消（trader.py）**
```python
def cancel_order(self, order_id: str) -> bool:
    """取消订单"""
```

### 数据流程

```
信号触发
    ↓
调用 open_long/open_short
    ↓
调用 create_smart_order
    ↓
检查 USE_MAKER_ORDER
    ↓
[是] 创建限价单 → 等待成交 → [成交] 完成
    ↓                    ↓
    |                [超时] 取消订单 → 降级为市价单
    ↓
[否] 直接创建市价单 → 完成
```

### 关键代码位置

- 配置文件：`config.py` 第127-152行
- 智能下单：`trader.py` 第463-530行
- 限价单创建：`trader.py` 第364-405行
- 订单监控：`trader.py` 第407-444行
- 订单取消：`trader.py` 第446-461行
- 开仓集成：`trader.py` 第532行（open_long）、第599行（open_short）

## 故障排查

### 问题1：限价单总是超时未成交

**原因：** 价格偏移量太小，挂单价格与市价差距不足

**解决方法：**
```python
# 增大价格偏移量
MAKER_PRICE_OFFSET = 0.0002  # 从0.01%增加到0.02%
```

### 问题2：成交价格偏离预期太多

**原因：** 价格偏移量太大，导致滑点增加

**解决方法：**
```python
# 减小价格偏移量
MAKER_PRICE_OFFSET = 0.00005  # 从0.01%减少到0.005%
```

### 问题3：订单创建失败

**原因：** API权限不足或网络问题

**解决方法：**
1. 检查API密钥权限
2. 检查网络连接
3. 查看日志文件：`logs/error.log`

### 问题4：手续费没有降低

**原因：** 限价单未成交，降级为市价单

**解决方法：**
1. 增大超时时间：`MAKER_ORDER_TIMEOUT = 15`
2. 增大价格偏移：`MAKER_PRICE_OFFSET = 0.0002`
3. 检查市场流动性

## 性能优化

### 1. 根据市场状态动态调整

```python
# 高波动市场：缩短超时，快速降级
if volatility > 0.03:
    MAKER_ORDER_TIMEOUT = 5

# 低波动市场：延长超时，提高成交率
else:
    MAKER_ORDER_TIMEOUT = 15
```

### 2. 根据成交率优化参数

监控Maker订单成交率，动态调整参数：

- 成交率 > 80%：减小价格偏移，降低滑点
- 成交率 < 50%：增大价格偏移或缩短超时

### 3. 分时段策略

```python
# 交易活跃时段：使用Maker订单
if is_active_trading_hours():
    USE_MAKER_ORDER = True

# 交易清淡时段：使用市价单
else:
    USE_MAKER_ORDER = False
```

## 扩展开发

### 添加成交率统计

在 `trader.py` 中添加统计功能：

```python
class MakerOrderStats:
    def __init__(self):
        self.total_attempts = 0
        self.successful_fills = 0
        self.fallback_to_market = 0

    def record_attempt(self, filled: bool):
        self.total_attempts += 1
        if filled:
            self.successful_fills += 1
        else:
            self.fallback_to_market += 1

    def get_fill_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_fills / self.total_attempts
```

### 添加动态价格偏移

根据订单簿深度动态调整价格偏移：

```python
def calculate_dynamic_offset(self, side: str) -> float:
    """根据订单簿深度计算动态价格偏移"""
    orderbook = self.exchange.fetch_order_book(config.SYMBOL)

    if side == 'buy':
        # 分析买单深度
        best_bid = orderbook['bids'][0][0]
        # 计算合适的偏移量

    else:
        # 分析卖单深度
        best_ask = orderbook['asks'][0][0]
        # 计算合适的偏移量
```

## 最佳实践

### 1. 初次使用建议

- 先在测试环境运行1-2天
- 监控成交率和手续费节省情况
- 根据实际情况调整参数

### 2. 参数调优建议

- 超时时间：5-15秒之间
- 价格偏移：0.005%-0.02%之间
- 检查间隔：0.5-1秒之间

### 3. 监控指标

- Maker订单成交率
- 平均等待时间
- 手续费节省金额
- 滑点损失

### 4. 风险控制

- 启用自动降级机制
- 设置合理的超时时间
- 定期检查日志

## 更新日志

### v1.0.0 (2025-12-25)
- 初始版本发布
- 实现基础Maker订单功能
- 支持智能降级机制
- 完整的配置和监控

## 相关文档

- [交易手续费对比分析报告](../README.md)
- [配置文件说明](../config.py)
- [交易执行器文档](../trader.py)
- [测试用例文档](../scripts/test_maker_order.py)
