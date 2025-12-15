# 状态监控功能说明文档

## 概述

状态监控功能是交易机器人的实时状态推送系统，用于定期向飞书推送系统运行状态、市场行情变化、交易活动等信息，帮助用户实时了解机器人运行情况。

## 功能特性

### 1. 定期状态推送
- 默认每5分钟推送一次系统状态
- 推送间隔可配置（1-60分钟）
- 自动记录价格历史，计算行情变化

### 2. 多维度信息收集
- **行情变化**：最近N分钟的价格变化、涨跌幅、波动幅度
- **交易活动**：开仓/平仓次数、盈亏统计、最近交易记录
- **趋势分析**：市场状态（震荡/趋势）、置信度、趋势方向
- **服务状态**：运行时长、错误次数、系统健康状态
- **账户信息**：可用余额、持仓情况、盈亏状态

### 3. 智能降级机制
- 优先推送到飞书
- 飞书推送失败时自动发送邮件预警
- 确保用户能及时收到系统状态信息

### 4. AI分析接口（预留）
- 预留AI分析接口，可扩展集成大语言模型
- 支持对市场状态进行深度分析
- 提供智能交易建议和风险提示

## 配置说明

### 配置文件位置
`/root/trading_bot/config.py`

### 配置项详解

```python
# ==================== 状态监控配置 ====================

# 是否启用状态监控推送
ENABLE_STATUS_MONITOR = True

# 状态推送间隔（分钟）
# 范围：1-60分钟，默认5分钟
STATUS_MONITOR_INTERVAL = 5

# 是否启用AI分析（预留功能）
# 当前版本暂未实现，预留扩展
STATUS_MONITOR_ENABLE_AI = False

# 飞书推送失败时是否发送邮件预警
# 建议开启，确保能及时收到系统状态
STATUS_MONITOR_EMAIL_ON_FAILURE = True

# 状态监控包含的模块
# 可根据需要开启/关闭特定模块
STATUS_MONITOR_MODULES = {
    'market_change': True,    # 最近N分钟行情变化
    'trade_activity': True,   # 开单情况
    'trend_analysis': True,   # 趋势分析
    'service_status': True,   # 服务状态
    'account_info': True,     # 账户信息
}
```

### 依赖配置

状态监控功能依赖以下配置：

1. **飞书配置**（必需）
```python
ENABLE_FEISHU = True
FEISHU_WEBHOOK_URL = "your_feishu_webhook_url"
```

2. **邮件配置**（可选，用于降级预警）
```python
ENABLE_EMAIL = True
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_SENDER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_email_password"
EMAIL_RECEIVER = "receiver_email@gmail.com"
```

## 使用方法

### 1. 启用状态监控

在 `config.py` 中设置：
```python
ENABLE_STATUS_MONITOR = True
STATUS_MONITOR_INTERVAL = 5  # 每5分钟推送一次
```

### 2. 配置推送渠道

确保飞书配置正确：
```bash
# 在 .env 文件中配置
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook_token
```

### 3. 启动机器人

```bash
python main.py
```

启动后，状态监控会自动运行，按配置的间隔推送状态信息。

### 4. 查看推送消息

推送消息示例：

```
🔔 系统状态推送
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ 服务状态
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
时间: 2024-12-15 14:30:00
运行时长: 2小时30分钟
错误次数: 0
状态: ✅ 正常运行

📈 最近5分钟行情
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前价格: $43,250.00
价格变化: +125.50 (+0.29%) 📈
区间最高: $43,280.00
区间最低: $43,100.00
波动幅度: 0.42%

🎯 趋势分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
市场状态: 趋势市
置信度: 75%
趋势方向: 上涨
波动率: 中等
适合交易: ✅

💼 最近5分钟交易
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
开仓次数: 1
平仓次数: 0
最近交易: open long

💰 账户信息
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
可用余额: 9850.00 USDT
持仓: 🟢 多单
数量: 0.05 BTC
开仓价: $43,100.00
当前价: $43,250.00
盈亏: +7.50 USDT (+1.74%) 📈
持仓时长: 3分钟

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 下次推送: 5分钟后
```

## 技术实现

### 核心模块

1. **StatusMonitorScheduler**：调度器类
   - 管理推送时间
   - 维护价格历史记录
   - 触发状态收集和推送

2. **StatusMonitorCollector**：数据收集器类
   - 收集各维度数据
   - 格式化推送消息
   - 处理推送逻辑

3. **PriceHistory**：价格历史记录器
   - 记录最近60分钟的价格数据
   - 计算价格变化和波动率
   - 支持任意时间区间查询

### 数据流程

```
主循环 (bot.py)
    ↓
更新价格历史
    ↓
检查是否到达推送时间
    ↓
收集状态数据
    ↓
格式化消息
    ↓
推送到飞书
    ↓
失败？→ 发送邮件预警
```

### 集成方式

状态监控已集成到主循环中：

```python
# bot.py 主循环
def _main_loop(self):
    # 获取当前价格
    current_price = ticker['last']

    # 更新状态监控的价格历史
    if self.status_monitor:
        self.status_monitor.update_price(current_price)

    # 检查并推送状态监控
    if self.status_monitor:
        self.status_monitor.check_and_push(self.trader, self.risk_manager)
```

## 故障排查

### 1. 状态监控未启动

**症状**：启动机器人后没有看到状态监控相关日志

**解决方法**：
- 检查 `config.py` 中 `ENABLE_STATUS_MONITOR` 是否为 `True`
- 检查配置验证是否通过：`python config.py`

### 2. 飞书推送失败

**症状**：日志显示"飞书推送失败"

**解决方法**：
- 检查 `FEISHU_WEBHOOK_URL` 是否配置正确
- 测试 webhook 是否有效：`curl -X POST -H "Content-Type: application/json" -d '{"msg_type":"text","content":{"text":"test"}}' YOUR_WEBHOOK_URL`
- 检查网络连接是否正常

### 3. 邮件预警未收到

**症状**：飞书推送失败但未收到邮件预警

**解决方法**：
- 检查 `STATUS_MONITOR_EMAIL_ON_FAILURE` 是否为 `True`
- 检查邮件配置是否正确（SMTP服务器、端口、账号密码）
- 检查邮件是否被拦截到垃圾箱

### 4. 行情变化数据不准确

**症状**：显示的价格变化与实际不符

**解决方法**：
- 刚启动时价格历史数据不足，需要运行一段时间后才准确
- 检查系统时间是否正确
- 检查主循环是否正常运行

## 性能优化

### 1. 推送间隔建议
- **生产环境**：5-10分钟，平衡信息及时性和系统负载
- **测试环境**：1-2分钟，便于快速验证功能
- **低频监控**：15-30分钟，减少推送频率

### 2. 模块选择
根据实际需求开启/关闭特定模块：
```python
STATUS_MONITOR_MODULES = {
    'market_change': True,     # 核心模块，建议保留
    'trade_activity': True,    # 核心模块，建议保留
    'trend_analysis': True,    # 可选，需要计算资源
    'service_status': True,    # 核心模块，建议保留
    'account_info': True,      # 核心模块，建议保留
}
```

### 3. 价格历史优化
- 默认保留60分钟历史数据
- 如需更长历史，可修改 `PriceHistory` 的 `max_minutes` 参数
- 注意内存占用：60分钟 × 12次/分钟 = 720条记录

## 扩展开发

### 1. 添加新的数据收集模块

在 `StatusMonitorCollector` 类中添加新方法：

```python
def _collect_custom_data(self) -> Dict[str, Any]:
    """收集自定义数据"""
    try:
        # 实现数据收集逻辑
        return {
            'custom_field': 'custom_value'
        }
    except Exception as e:
        return {'error': str(e)}
```

在 `collect_all` 方法中调用：

```python
if modules.get('custom_data', False):
    data['custom_data'] = self._collect_custom_data()
```

### 2. 集成AI分析

实现 `AIAnalyzer` 类：

```python
class AIAnalyzer:
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # 调用大语言模型API
        # 分析市场状态
        # 提供交易建议
        return {
            'analysis': '市场处于上涨趋势...',
            'suggestion': '建议持有多单...',
            'risk_level': 'medium'
        }
```

### 3. 自定义消息格式

修改 `format_message` 方法，自定义推送消息的格式和内容。

## 最佳实践

1. **合理设置推送间隔**
   - 避免过于频繁（<1分钟），造成信息过载
   - 避免过于稀疏（>30分钟），错过重要信息

2. **启用邮件降级**
   - 确保飞书故障时能收到预警
   - 定期检查邮件配置是否有效

3. **监控日志**
   - 定期查看日志文件，了解推送状态
   - 关注错误日志，及时处理异常

4. **测试验证**
   - 新部署时先用短间隔测试（1-2分钟）
   - 确认功能正常后再调整为正常间隔

5. **数据备份**
   - 价格历史数据存储在内存中，重启后丢失
   - 如需持久化，可扩展实现数据库存储

## 更新日志

### v1.0.0 (2024-12-15)
- 初始版本发布
- 支持定期状态推送
- 支持多维度数据收集
- 支持飞书推送和邮件降级
- 预留AI分析接口

## 相关文档

- [配置文件说明](./config.md)
- [飞书通知配置](./feishu_notification.md)
- [邮件通知配置](./email_notification.md)
- [测试用例说明](./testing.md)

## 技术支持

如有问题或建议，请联系开发团队或提交Issue。
