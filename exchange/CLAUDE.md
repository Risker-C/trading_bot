[根目录](../CLAUDE.md) > **exchange**

---

# Exchange - 多交易所框架

> 最后更新: 2026-01-09

## 变更记录 (Changelog)

### 2026-01-09 - 初始化模块文档
- 创建多交易所框架文档
- 记录模块结构和接口定义

---

## 模块职责

多交易所框架提供统一的交易所接口抽象层，支持 Bitget、Binance、OKX 等多个交易所的无缝切换。采用适配器模式和工厂模式，实现了交易所 API 的标准化封装。

**核心功能：**
- 统一的交易所接口定义
- 适配器模式实现多交易所支持
- 工厂模式管理实例创建
- 单例模式确保资源复用
- 标准化的数据结构（TickerData、PositionData、OrderResult）

---

## 入口与启动

### 初始化流程

```python
from exchange.manager import ExchangeManager

# 创建管理器（单例）
manager = ExchangeManager()

# 初始化（自动从 config.py 读取配置）
manager.initialize()

# 获取当前交易所
exchange = manager.get_current_exchange()

# 使用交易所接口
ticker = exchange.get_ticker("BTCUSDT")
```

### 配置要求

在 `config.py` 中配置：

```python
ACTIVE_EXCHANGE = "bitget"  # 当前使用的交易所

EXCHANGES_CONFIG = {
    "bitget": {
        "api_key": "...",
        "api_secret": "...",
        "api_password": "...",
        "symbol": "BTCUSDT",
        "leverage": 10,
    },
    "binance": {...},
    "okx": {...},
}
```

---

## 对外接口

### ExchangeInterface (抽象基类)

**生命周期管理：**
- `connect()` - 连接交易所
- `disconnect()` - 断开连接
- `is_connected()` - 检查连接状态

**市场数据接口：**
- `get_ticker(symbol)` - 获取行情数据
- `get_klines(symbol, timeframe, limit)` - 获取K线数据
- `get_orderbook(symbol, limit)` - 获取订单簿

**账户接口：**
- `get_balance()` - 获取账户余额
- `get_positions(symbol)` - 获取持仓信息

**交易接口：**
- `create_market_order(symbol, side, amount)` - 创建市价单
- `create_limit_order(symbol, side, amount, price)` - 创建限价单
- `cancel_order(order_id, symbol)` - 取消订单
- `get_order(order_id, symbol)` - 查询订单状态

**杠杆与保证金：**
- `set_leverage(symbol, leverage)` - 设置杠杆
- `set_margin_mode(symbol, margin_mode)` - 设置保证金模式

### 数据结构

**TickerData:**
```python
@dataclass
class TickerData:
    symbol: str
    last: float          # 最新价
    bid: float          # 买一价
    ask: float          # 卖一价
    volume: float       # 成交量
    timestamp: int      # 时间戳
    raw_data: Dict      # 原始数据
```

**PositionData:**
```python
@dataclass
class PositionData:
    side: str           # 'long' or 'short'
    amount: float       # 持仓数量
    entry_price: float  # 开仓价格
    unrealized_pnl: float  # 未实现盈亏
    leverage: int       # 杠杆倍数
    margin_mode: str    # 保证金模式
    raw_data: Dict
```

**OrderResult:**
```python
@dataclass
class OrderResult:
    success: bool
    order_id: str
    price: float
    amount: float
    side: str           # 'buy' or 'sell'
    error: str          # 错误信息（如果失败）
    filled_quantity: float  # 已成交数量
    avg_price: float    # 平均成交价
    status: str         # 'open', 'closed', 'canceled'
```

---

## 关键依赖与配置

### 外部依赖
- `ccxt` - 交易所连接库（核心依赖）
- `logger_utils` - 日志系统

### 内部依赖
- `config.py` - 全局配置
- `exchange/errors.py` - 自定义异常

### 配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ACTIVE_EXCHANGE` | 当前使用的交易所 | "bitget" |
| `EXCHANGES_CONFIG` | 交易所配置字典 | {...} |
| `api_key` | API密钥 | 必填 |
| `api_secret` | API密钥 | 必填 |
| `api_password` | API密码（部分交易所需要） | 可选 |

---

## 数据模型

### 适配器注册机制

```python
# 在 exchange/__init__.py 中自动注册
ExchangeFactory.register('bitget', BitgetAdapter)
ExchangeFactory.register('binance', BinanceAdapter)
ExchangeFactory.register('okx', OKXAdapter)
```

### 工厂模式

```python
# ExchangeFactory 提供三种创建方式
factory.create(name, config)           # 创建新实例
factory.get_or_create(name, config)    # 获取或创建（单例）
factory.get_supported_exchanges()      # 获取支持的交易所列表
```

### 管理器模式

```python
# ExchangeManager 管理多个交易所实例
manager.initialize()                   # 初始化
manager.get_current_exchange()         # 获取当前交易所
manager.switch_exchange(name)          # 切换交易所
manager.get_all_exchanges()            # 获取所有交易所
```

---

## 测试与质量

### 测试文件
- `scripts/test_multi_exchange.py` - 多交易所功能测试

### 测试覆盖
- 交易所连接测试
- 市场数据获取测试
- 订单创建与查询测试
- 持仓查询测试
- 切换交易所测试

### 运行测试

```bash
python scripts/test_multi_exchange.py
```

---

## 常见问题 (FAQ)

### Q: 如何添加新的交易所支持？

1. 在 `exchange/adapters/` 创建新适配器类
2. 继承 `ExchangeInterface` 并实现所有抽象方法
3. 在 `exchange/__init__.py` 中注册适配器
4. 在 `config.py` 中添加配置

示例：
```python
# exchange/adapters/new_exchange_adapter.py
class NewExchangeAdapter(ExchangeInterface):
    def connect(self):
        # 实现连接逻辑
        pass

    # 实现其他接口...

# exchange/__init__.py
from .adapters.new_exchange_adapter import NewExchangeAdapter
ExchangeFactory.register('new_exchange', NewExchangeAdapter)
```

### Q: 如何切换交易所？

```python
# 方法1: 修改配置文件
# config.py
ACTIVE_EXCHANGE = "binance"

# 方法2: 运行时切换
manager = ExchangeManager()
manager.switch_exchange("binance")
```

### Q: 如何处理交易所特定功能？

使用 `raw_data` 字段访问原始数据：
```python
ticker = exchange.get_ticker("BTCUSDT")
raw_ticker = ticker.raw_data  # 交易所原始返回数据
```

### Q: 连接失败如何处理？

框架会抛出自定义异常：
```python
from exchange.errors import NetworkError, AuthenticationError

try:
    exchange.connect()
except AuthenticationError:
    # API密钥错误
    pass
except NetworkError:
    # 网络连接失败
    pass
```

---

## 相关文件清单

### 核心文件
- `__init__.py` - 模块入口，注册适配器
- `interface.py` - 统一接口定义
- `factory.py` - 工厂类，创建适配器实例
- `manager.py` - 管理器，管理多个交易所
- `errors.py` - 自定义异常类
- `decorators.py` - 装饰器（错误处理、重试等）
- `legacy_adapter.py` - 兼容旧版代码的适配器

### 适配器实现
- `adapters/__init__.py` - 适配器模块入口
- `adapters/bitget_adapter.py` - Bitget 适配器
- `adapters/binance_adapter.py` - Binance 适配器
- `adapters/okx_adapter.py` - OKX 适配器

### 测试文件
- `../scripts/test_multi_exchange.py` - 功能测试

---

## 架构设计

### 设计模式

1. **适配器模式** - 统一不同交易所的API接口
2. **工厂模式** - 创建和管理适配器实例
3. **单例模式** - 确保交易所实例唯一性
4. **策略模式** - 不同交易所的不同实现策略

### 扩展性

- 新增交易所：只需实现 `ExchangeInterface` 接口
- 新增功能：在接口中添加抽象方法，各适配器实现
- 向后兼容：通过 `legacy_adapter.py` 支持旧版代码

### 错误处理

```python
# 统一的异常体系
ExchangeError           # 基础异常
├── NetworkError        # 网络错误
├── AuthenticationError # 认证错误
├── RateLimitError      # 限流错误
└── InsufficientBalanceError  # 余额不足
```

---

**模块状态：** ✅ 稳定运行
**支持的交易所：** Bitget, Binance, OKX
**接口版本：** v1.0
