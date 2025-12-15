# 定期市场分析通知功能技术设计文档

**文档版本:** 1.0
**创建日期:** 2025-12-15
**设计者:** Claude Sonnet 4.5
**关联需求:** periodic_market_report_requirements.md

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Bot (bot.py)                 │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │         Main Trading Loop                      │    │
│  │  - Market monitoring                           │    │
│  │  - Strategy execution                          │    │
│  │  - Position management                         │    │
│  └────────────────────────────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│  ┌────────────────────────────────────────────────┐    │
│  │    Periodic Report Scheduler (NEW)             │    │
│  │  - Timer management                            │    │
│  │  - Report generation trigger                   │    │
│  └────────────────────────────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│  ┌────────────────────────────────────────────────┐    │
│  │    Market Report Generator (NEW)               │    │
│  │  - Data collection                             │    │
│  │  - Analysis generation                         │    │
│  │  - Message formatting                          │    │
│  └────────────────────────────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│  ┌────────────────────────────────────────────────┐    │
│  │    Notification System (logger_utils.py)       │    │
│  │  - Feishu notification                         │    │
│  │  - Error handling                              │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 1.2 模块关系

```
bot.py
  ├── imports market_report.py (NEW)
  ├── initializes PeriodicReportScheduler
  └── calls scheduler.check_and_send() in main loop

market_report.py (NEW)
  ├── class PeriodicReportScheduler
  │   ├── manages timing
  │   └── triggers report generation
  └── class MarketReportGenerator
      ├── collects data from trader, risk_manager, market_state
      ├── formats message
      └── sends via notifier

config.py
  └── adds new configuration options
```

---

## 2. 核心组件设计

### 2.1 PeriodicReportScheduler 类

**职责:**
- 管理报告发送的时间调度
- 跟踪上次发送时间
- 判断是否应该发送报告
- 触发报告生成和发送

**接口设计:**

```python
class PeriodicReportScheduler:
    """定期报告调度器"""

    def __init__(self, interval_minutes: int = 120, enabled: bool = True):
        """
        初始化调度器

        Args:
            interval_minutes: 发送间隔（分钟）
            enabled: 是否启用
        """
        pass

    def should_send_report(self) -> bool:
        """
        判断是否应该发送报告

        Returns:
            bool: True表示应该发送
        """
        pass

    def check_and_send(self, trader, risk_manager, market_state_detector) -> bool:
        """
        检查并发送报告（如果需要）

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例
            market_state_detector: 市场状态检测器实例

        Returns:
            bool: True表示发送成功
        """
        pass

    def send_now(self, trader, risk_manager, market_state_detector) -> bool:
        """
        立即发送报告（用于测试）

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例
            market_state_detector: 市场状态检测器实例

        Returns:
            bool: True表示发送成功
        """
        pass

    def reset_timer(self):
        """重置计时器"""
        pass

    def get_next_report_time(self) -> datetime:
        """
        获取下次报告时间

        Returns:
            datetime: 下次报告时间
        """
        pass

    def get_time_until_next_report(self) -> timedelta:
        """
        获取距离下次报告的时间

        Returns:
            timedelta: 剩余时间
        """
        pass
```

**状态管理:**

```python
class PeriodicReportScheduler:
    def __init__(self, ...):
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.last_report_time = None  # 上次发送时间
        self.start_time = datetime.now()  # 启动时间
        self.report_count = 0  # 已发送报告数
        self.logger = get_logger("periodic_report")
```

### 2.2 MarketReportGenerator 类

**职责:**
- 收集市场数据
- 收集账户数据
- 收集持仓数据
- 生成分析报告
- 格式化消息

**接口设计:**

```python
class MarketReportGenerator:
    """市场报告生成器"""

    def __init__(self, trader, risk_manager, market_state_detector):
        """
        初始化报告生成器

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例
            market_state_detector: 市场状态检测器实例
        """
        pass

    def generate_report(self) -> dict:
        """
        生成完整报告数据

        Returns:
            dict: 报告数据字典
        """
        pass

    def format_message(self, report_data: dict) -> str:
        """
        格式化报告消息

        Args:
            report_data: 报告数据

        Returns:
            str: 格式化的消息文本
        """
        pass

    def send_report(self) -> bool:
        """
        生成并发送报告

        Returns:
            bool: True表示发送成功
        """
        pass

    # 私有方法
    def _collect_system_info(self) -> dict:
        """收集系统信息"""
        pass

    def _collect_market_info(self) -> dict:
        """收集市场信息"""
        pass

    def _collect_market_state(self) -> dict:
        """收集市场状态"""
        pass

    def _collect_strategy_info(self) -> dict:
        """收集策略信息"""
        pass

    def _collect_position_info(self) -> dict:
        """收集持仓信息"""
        pass

    def _collect_account_info(self) -> dict:
        """收集账户信息"""
        pass

    def _collect_trade_stats(self) -> dict:
        """收集交易统计"""
        pass
```

**数据结构:**

```python
# 报告数据结构
report_data = {
    'system': {
        'timestamp': '2025-12-15 10:00:00',
        'uptime': '2小时30分钟',
        'uptime_seconds': 9000,
    },
    'market': {
        'symbol': 'BTC/USDT',
        'price': 88421.10,
        'change_24h': 2.35,
        'volume_24h': 1200000000,
    },
    'market_state': {
        'state': 'RANGING',
        'confidence': 75,
        'adx': 33.2,
        'bb_width': 1.03,
        'trend': '横盘整理',
        'volatility': '中等',
        'tradeable': True,
    },
    'strategy': {
        'enabled': ['bollinger_breakthrough', 'rsi_divergence', 'kdj_cross'],
        'recommended': ['bollinger_breakthrough', 'rsi_divergence', 'kdj_cross'],
        'reason': '震荡市 → 使用均值回归策略',
    },
    'position': {
        'has_position': False,
        # 如有持仓:
        # 'side': 'long',
        # 'amount': 0.001,
        # 'entry_price': 87500.0,
        # 'current_price': 88421.10,
        # 'pnl': 0.92,
        # 'pnl_percent': 10.52,
        # 'duration': '1小时23分钟',
        # 'stop_loss': 86625.0,
        # 'take_profit': 91000.0,
        # 'liquidation': 78750.0,
    },
    'account': {
        'balance': 50.48,
        # 如有持仓:
        # 'equity': 51.40,
        # 'margin_used': 8.75,
    },
    'stats': {
        'trades_24h': 0,
        'pnl_24h': 0.0,
        'last_trade': None,
        # 如有最近交易:
        # 'last_trade': {
        #     'time': '2025-12-15 08:30:00',
        #     'side': 'long',
        #     'action': 'open',
        #     'result': 'success',
        # }
    },
}
```

---

## 3. 配置设计

### 3.1 新增配置项

在 `config.py` 中添加以下配置:

```python
# ==================== 定期市场报告配置 ====================

# 是否启用定期市场报告
ENABLE_PERIODIC_REPORT = True

# 报告发送间隔（分钟）
PERIODIC_REPORT_INTERVAL = 120  # 默认2小时

# 报告详细程度: 'simple', 'standard', 'detailed'
PERIODIC_REPORT_DETAIL_LEVEL = 'standard'

# 是否在启动时立即发送一次报告
SEND_REPORT_ON_STARTUP = True

# 报告包含的模块（可选配置）
PERIODIC_REPORT_MODULES = {
    'system_info': True,      # 系统信息
    'market_info': True,      # 市场信息
    'market_state': True,     # 市场状态
    'strategy_info': True,    # 策略信息
    'position_info': True,    # 持仓信息
    'account_info': True,     # 账户信息
    'trade_stats': True,      # 交易统计
}
```

### 3.2 配置验证

在 `config.py` 的 `validate_config()` 函数中添加验证:

```python
def validate_config():
    errors = []

    # ... 现有验证 ...

    # 验证定期报告配置
    if ENABLE_PERIODIC_REPORT:
        if not isinstance(PERIODIC_REPORT_INTERVAL, int):
            errors.append("PERIODIC_REPORT_INTERVAL 必须是整数")
        elif PERIODIC_REPORT_INTERVAL < 30:
            errors.append("PERIODIC_REPORT_INTERVAL 不能小于30分钟")
        elif PERIODIC_REPORT_INTERVAL > 720:
            errors.append("PERIODIC_REPORT_INTERVAL 不能大于720分钟（12小时）")

        if PERIODIC_REPORT_DETAIL_LEVEL not in ['simple', 'standard', 'detailed']:
            errors.append("PERIODIC_REPORT_DETAIL_LEVEL 必须是 'simple', 'standard' 或 'detailed'")

        # 检查飞书配置
        if not ENABLE_FEISHU:
            errors.append("启用定期报告需要启用飞书通知 (ENABLE_FEISHU=True)")
        elif not FEISHU_WEBHOOK_URL:
            errors.append("启用定期报告需要配置飞书 Webhook URL")

    return errors
```

---

## 4. 集成设计

### 4.1 在 bot.py 中集成

**步骤1: 导入模块**

```python
# 在 bot.py 顶部添加
from market_report import PeriodicReportScheduler
```

**步骤2: 初始化调度器**

```python
class TradingBot:
    def __init__(self):
        # ... 现有初始化代码 ...

        # 初始化定期报告调度器
        if config.ENABLE_PERIODIC_REPORT:
            self.report_scheduler = PeriodicReportScheduler(
                interval_minutes=config.PERIODIC_REPORT_INTERVAL,
                enabled=True
            )
            self.logger.info(f"✅ 定期报告已启用，间隔: {config.PERIODIC_REPORT_INTERVAL}分钟")

            # 启动时发送一次报告
            if config.SEND_REPORT_ON_STARTUP:
                self.report_scheduler.send_now(
                    self.trader,
                    self.risk_manager,
                    self.market_state_detector
                )
        else:
            self.report_scheduler = None
            self.logger.info("⏭️  定期报告已禁用")
```

**步骤3: 在主循环中调用**

```python
def run(self):
    """主运行循环"""
    self.running = True
    self.logger.info("开始监控，检查间隔: {} 秒".format(config.CHECK_INTERVAL))

    while self.running:
        try:
            # ... 现有交易逻辑 ...

            # 检查并发送定期报告
            if self.report_scheduler:
                try:
                    self.report_scheduler.check_and_send(
                        self.trader,
                        self.risk_manager,
                        self.market_state_detector
                    )
                except Exception as e:
                    self.logger.error(f"定期报告发送失败: {e}")
                    # 不影响主流程，继续运行

            # 等待下一次检查
            time.sleep(config.CHECK_INTERVAL)

        except KeyboardInterrupt:
            # ... 现有中断处理 ...
```

### 4.2 文件结构

```
trading_bot/
├── bot.py                          # 主程序（修改）
├── config.py                       # 配置文件（修改）
├── market_report.py                # 新增：市场报告模块
├── logger_utils.py                 # 通知系统（已有）
├── trader.py                       # 交易器（已有）
├── risk_manager.py                 # 风险管理（已有）
├── market_state.py                 # 市场状态检测（已有）
├── docs/
│   ├── periodic_market_report_requirements.md  # 需求文档
│   ├── periodic_market_report_design.md        # 设计文档（本文档）
│   └── periodic_market_report_test_cases.md    # 测试用例文档
└── scripts/
    └── test_periodic_report.py     # 新增：测试脚本
```

---

## 5. 数据流设计

### 5.1 正常流程

```
1. 主循环每次迭代
   ↓
2. 调用 report_scheduler.check_and_send()
   ↓
3. 检查是否到达发送时间
   ├─ 否 → 返回，继续主循环
   └─ 是 → 继续
   ↓
4. 创建 MarketReportGenerator
   ↓
5. 收集各模块数据
   ├─ trader.get_ticker() → 市场价格
   ├─ trader.get_balance() → 账户余额
   ├─ trader.get_positions() → 持仓信息
   ├─ market_state_detector.detect() → 市场状态
   ├─ risk_manager.position → 风险管理信息
   └─ database.get_trades() → 交易统计
   ↓
6. 生成报告数据字典
   ↓
7. 格式化消息文本
   ↓
8. 调用 notifier.send_feishu()
   ↓
9. 更新 last_report_time
   ↓
10. 记录日志
   ↓
11. 返回主循环
```

### 5.2 异常流程

```
数据收集失败:
  ├─ API调用超时 → 使用默认值 + 记录警告
  ├─ 数据格式错误 → 跳过该模块 + 记录错误
  └─ 网络异常 → 重试3次 → 失败则跳过

消息发送失败:
  ├─ 飞书API错误 → 重试3次 → 记录错误
  ├─ 网络超时 → 重试3次 → 记录错误
  └─ 限流 → 延迟下次发送时间 + 记录警告

所有异常:
  └─ 不影响主交易循环，仅记录日志
```

---

## 6. 错误处理设计

### 6.1 异常分类

| 异常类型 | 处理策略 | 影响范围 |
|---------|---------|---------|
| 数据收集失败 | 使用默认值/跳过模块 | 单个模块 |
| 网络超时 | 重试3次 | 单次发送 |
| API限流 | 延迟发送 | 单次发送 |
| 格式化错误 | 使用简化格式 | 单次发送 |
| 发送失败 | 记录日志，下次重试 | 单次发送 |
| 严重错误 | 禁用功能 | 整个功能 |

### 6.2 重试机制

```python
def send_with_retry(message: str, max_retries: int = 3) -> bool:
    """
    带重试的发送函数

    Args:
        message: 消息内容
        max_retries: 最大重试次数

    Returns:
        bool: 发送是否成功
    """
    for attempt in range(max_retries):
        try:
            notifier.send_feishu(message)
            return True
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            else:
                logger.error(f"发送失败，已重试{max_retries}次")
                return False
        except Exception as e:
            logger.error(f"发送异常: {e}")
            return False

    return False
```

### 6.3 降级策略

```python
def generate_report_with_fallback(self) -> dict:
    """
    带降级的报告生成

    Returns:
        dict: 报告数据（可能不完整）
    """
    report =

    # 尝试收集各模块数据，失败则使用默认值
    try:
        report['system'] = self._collect_system_info()
    except Exception as e:
        logger.warning(f"系统信息收集失败: {e}")
        report['system'] = {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    try:
        report['market'] = self._collect_market_info()
    except Exception as e:
        logger.warning(f"市场信息收集失败: {e}")
        report['market'] = {'error': '数据获取失败'}

    # ... 其他模块类似处理 ...

    return report
```

---

## 7. 性能优化

### 7.1 优化策略

**1. 数据缓存**
```python
class MarketReportGenerator:
    def __init__(self, ...):
        self._cache = {}
        self._cache_ttl = 60  # 缓存60秒

    def _get_cached_data(self, key: str, fetch_func):
        """获取缓存数据或重新获取"""
        now = time.time()
        if key in self._cache:
            data, timestamp = self._cache[key]
            if now - timestamp < self._cache_ttl:
                return data

        # 缓存过期或不存在，重新获取
        data = fetch_func()
        self._cache[key] = (data, now)
        return data
```

**2. 异步发送**
```python
import threading

def send_report_async(self) -> bool:
    """异步发送报告"""
    def _send():
        try:
            report_data = self.generate_report()
            message = self.format_message(report_data)
            notifier.send_feishu(message)
        except Exception as e:
            logger.error(f"异步发送失败: {e}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    return True
```

**3. 延迟加载**
```python
def _collect_trade_stats(self) -> dict:
    """延迟加载交易统计（仅在需要时）"""
    if not config.PERIODIC_REPORT_MODULES.get('trade_stats', True):
        return {}

    # 只有启用时才查询数据库
    return self._query_trade_stats()
```

### 7.2 性能指标

| 指标 | 目标值 | 测量方法 |
|-----|-------|---------|
| 报告生成时间 | < 2秒 | time.time() 计时 |
| 内存占用增加 | < 10MB | memory_profiler |
| CPU占用增加 | < 5% | psutil |
| 主循环延迟 | < 100ms | 异步发送 |

---

## 8. 测试策略

### 8.1 单元测试

**测试 PeriodicReportScheduler:**
- 测试时间判断逻辑
- 测试计时器重置
- 测试启用/禁用功能
- 测试立即发送功能

**测试 MarketReportGenerator:**
- 测试数据收集（模拟数据）
- 测试消息格式化
- 测试异常处理
- 测试降级策略

### 8.2 集成测试

**测试完整流程:**
- 启动机器人 → 等待发送 → 验证消息
- 修改配置 → 重启 → 验证生效
- 模拟异常 → 验证容错
- 长时间运行 → 验证稳定性

### 8.3 回归测试

**验证不影响现有功能:**
- 交易功能正常
- 风险管理正常
- 其他通知正常
- 性能无明显下降

---

## 9. 部署计划

### 9.1 部署步骤

1. **代码开发**
   - 创建 market_report.py
   - 修改 config.py
   - 修改 bot.py
   - 创建测试脚本

2. **本地测试**
   - 运行单元测试
   - 运行集成测试
   - 验证消息格式

3. **配置更新**
   - 更新 config.py 配置
   - 验证配置有效性

4. **灰度发布**
   - 先在测试环境运行24小时
   - 监控日志和性能
   - 验证消息发送正常

5. **正式部署**
   - 停止机器人
   - 更新代码
   - 启动机器人
   - 监控运行状态

### 9.2 回滚计划

如果出现问题：
1. 立即停止机器人
2. 设置 `ENABLE_PERIODIC_REPORT = False`
3. 重启机器人
4. 分析问题原因
5. 修复后重新部署

---

## 10. 监控与维护

### 10.1 监控指标

- 报告发送成功率
- 报告发送延迟
- 数据收集失败次数
- 异常发生频率
- 飞书API调用次数

### 10.2 日志记录

```python
# 关键操作日志
logger.info("📊 定期报告: 开始生成报告")
logger.info(f"📊 定期报告: 报告生成完成，耗时{elapsed:.2f}秒")
logger.info("📊 定期报告: 发送成功")

# 警告日志
logger.warning("📊 定期报告: 数据收集部分失败，使用降级方案")
logger.warning("📊 定期报告: 发送失败，将在下次重试")

# 错误日志
logger.error(f"📊 定期报告: 严重错误 - {error}")
```

### 10.3 维护建议

- 每周检查发送成功率
- 每月优化消息格式
- 根据用户反馈调整内容
- 定期更新文档

---

## 11. 安全考虑

### 11.1 数据安全

- 敏感信息脱敏（API密钥、完整余额等）
- 使用HTTPS传输
- 不在日志中记录完整消息内容

### 11.2 API安全

- 遵守飞书API限流规则
- 实现指数退避重试
- 避免频繁调用

### 11.3 错误处理

- 所有异常都要捕获
- 不暴露系统内部信息
- 失败不影响主功能

---

## 12. 附录

### 12.1 消息格式示例

见需求文档第5节。

### 12.2 配置示例

```python
# 最小配置（使用默认值）
ENABLE_PERIODIC_REPORT = True
PERIODIC_REPORT_INTERVAL = 120

# 完整配置
ENABLE_PERIODIC_REPORT = True
PERIODIC_REPORT_INTERVAL = 120
PERIODIC_REPORT_DETAIL_LEVEL = 'standard'
SEND_REPORT_ON_STARTUP = True
PERIODIC_REPORT_MODULES = {
    'system_info': True,
    'market_info': True,
    'market_state': True,
    'strategy_info': True,
    'position_info': True,
    'account_info': True,
    'trade_stats': True,
}
```

### 12.3 相关文件

- 需求文档: `docs/periodic_market_report_requirements.md`
- 测试用例: `docs/periodic_market_report_test_cases.md`
- 实现代码: `market_report.py`
- 测试脚本: `scripts/test_periodic_report.py`

---

**文档状态:** ✅ 已完成
**审核状态:** 待审核
**下一步:** 开始代码实现
