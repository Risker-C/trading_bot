# Claude API 调用优化功能说明文档

## 概述

本文档描述了对 Claude API 调用频率的优化方案。通过精简调用场景，将 Claude API 调用限制为三种核心场景，既保证了分析质量，又大幅降低了API调用成本。

## 功能特性

### 优化前的问题

1. **调用过于频繁**：启动时立即调用、每30分钟定时调用、每次交易信号都调用
2. **成本较高**：不必要的调用增加了API使用成本
3. **缺少重要功能**：没有每日报告和交易复盘功能

### 优化后的三种调用场景

#### 场景1：实时交易信号分析（保留）

**触发条件**：当量化机器人判断出现交易信号时

**调用位置**：`bot.py:330` 和 `bot.py:431`（开多/开空信号分析）

**功能说明**：
- 在策略生成 LONG/SHORT 信号后触发
- 通过趋势过滤和 Claude 护栏检查
- 执行交易前的最后一道智能风控
- 分析市场状态、技术指标、风险因素
- 决策是否执行交易

**频率控制**：
- 由交易信号自然频率决定
- 通过 Claude 护栏限制：
  - 5分钟缓存（相同条件复用结果）
  - 日调用上限：500次
  - 日成本上限：$10.00

#### 场景2：30分钟定时市场分析（优化）

**触发条件**：每30分钟执行一次

**调用位置**：`bot.py:208-211`

**功能说明**：
- 定期分析市场整体状态和趋势
- 评估当前风险等级
- 识别潜在的入场机会
- 提供持仓建议（如有持仓）
- 分析市场情绪

**配置项**：
```python
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True  # 是否启用
CLAUDE_PERIODIC_INTERVAL = 30           # 分析间隔（分钟）
CLAUDE_ANALYZE_ON_STARTUP = False       # 启动时不立即分析（优化）
CLAUDE_PUSH_TO_FEISHU = True            # 推送到飞书
```

**优化点**：
- 关闭启动时立即分析（避免不必要的调用）
- 保持30分钟间隔，提供持续的市场洞察

#### 场景3：每日报告（新增）

**触发条件**：每天早上8点（北京时间）

**调用位置**：`bot.py:214-221`

**功能说明**：
- 昨日市场回顾和走势分析
- 昨日交易历史回顾和评价
- 交易决策的反思和经验教训
- 结合实时网络信息预测今日行情
- 提供今日交易策略建议
- 风险因素和黑天鹅事件提示

**配置项**：
```python
ENABLE_CLAUDE_DAILY_REPORT = True              # 是否启用每日报告
CLAUDE_DAILY_REPORT_HOUR = 8                   # 报告时间（小时）
CLAUDE_DAILY_REPORT_TIMEZONE = 'Asia/Shanghai' # 时区
CLAUDE_DAILY_INCLUDE_TRADE_REVIEW = True       # 包含交易回顾
CLAUDE_DAILY_INCLUDE_WEB_SEARCH = True         # 包含网络信息
CLAUDE_DAILY_REVIEW_DAYS = 1                   # 回顾天数
```

**报告内容**：
1. 📅 昨日市场回顾
   - 市场概况
   - 交易评价（优点、不足）
   - 经验教训

2. 📍 当前市场状态
   - 价格走势
   - 技术分析
   - 关键价位

3. 🔮 今日行情预测
   - 趋势预测
   - 影响因素（含网络信息）
   - 多空倾向和置信度

4. 💡 交易建议
   - 交易策略
   - 入场建议
   - 止损建议
   - 风险回报比

5. ⚠️ 风险提示
   - 主要风险
   - 可能的黑天鹅事件
   - 风险控制建议

6. 🌐 网络信息洞察
   - 最新加密货币新闻
   - 市场动态和重大事件
   - 可能影响价格的因素

## 配置说明

### 配置文件位置

所有配置项在 `config.py` 文件中

### 配置项详解

#### Claude 基础配置
```python
ENABLE_CLAUDE_ANALYSIS = True          # 启用实时信号分析
CLAUDE_API_KEY = "your-api-key"        # API密钥
CLAUDE_BASE_URL = "https://..."        # 自定义API端点（可选）
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"  # 使用模型
CLAUDE_TIMEOUT = 30                    # API超时（秒）
```

#### 频率和成本控制
```python
CLAUDE_CACHE_TTL = 300                 # 缓存有效期（秒）
CLAUDE_MAX_DAILY_CALLS = 500           # 日调用上限
CLAUDE_MAX_DAILY_COST = 10.0           # 日成本上限（美元）
```

#### 定时分析配置
```python
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True  # 启用定时分析
CLAUDE_PERIODIC_INTERVAL = 30           # 分析间隔（分钟）
CLAUDE_ANALYZE_ON_STARTUP = False       # 启动时不立即分析
CLAUDE_PUSH_TO_FEISHU = True            # 推送到飞书
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'standard'  # 分析详细程度
```

#### 每日报告配置
```python
ENABLE_CLAUDE_DAILY_REPORT = True           # 启用每日报告
CLAUDE_DAILY_REPORT_HOUR = 8                # 报告时间（小时）
CLAUDE_DAILY_REPORT_TIMEZONE = 'Asia/Shanghai'  # 时区
CLAUDE_DAILY_INCLUDE_TRADE_REVIEW = True    # 包含交易回顾
CLAUDE_DAILY_INCLUDE_WEB_SEARCH = True      # 包含网络信息
CLAUDE_DAILY_REVIEW_DAYS = 1                # 回顾天数
```

## 使用方法

### 1. 启用/禁用功能

**启用所有功能**（默认）：
```python
# config.py
ENABLE_CLAUDE_ANALYSIS = True           # 场景1：实时信号分析
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True  # 场景2：定时分析
ENABLE_CLAUDE_DAILY_REPORT = True       # 场景3：每日报告
```

**仅启用实时分析**：
```python
ENABLE_CLAUDE_ANALYSIS = True
ENABLE_CLAUDE_PERIODIC_ANALYSIS = False
ENABLE_CLAUDE_DAILY_REPORT = False
```

**仅启用每日报告**：
```python
ENABLE_CLAUDE_ANALYSIS = False
ENABLE_CLAUDE_PERIODIC_ANALYSIS = False
ENABLE_CLAUDE_DAILY_REPORT = True
```

### 2. 调整分析频率

**修改定时分析间隔**：
```python
# 改为1小时分析一次
CLAUDE_PERIODIC_INTERVAL = 60

# 改为15分钟分析一次
CLAUDE_PERIODIC_INTERVAL = 15
```

**修改每日报告时间**：
```python
# 改为早上9点
CLAUDE_DAILY_REPORT_HOUR = 9

# 改为晚上8点
CLAUDE_DAILY_REPORT_HOUR = 20
```

### 3. 控制成本

**降低日调用上限**：
```python
# 降低到300次/天
CLAUDE_MAX_DAILY_CALLS = 300
```

**降低日成本上限**：
```python
# 降低到5美元/天
CLAUDE_DAILY_COST = 5.0
```

**增加缓存时间**：
```python
# 增加到10分钟缓存
CLAUDE_CACHE_TTL = 600  # 秒
```

### 4. 查看运行日志

```bash
# 查看 Claude 相关日志
grep "claude" logs/bot_*.log

# 查看定时分析日志
grep "定期市场分析" logs/bot_*.log

# 查看每日报告日志
grep "每日市场报告" logs/bot_*.log
```

## 技术实现

### 核心模块

1. **claude_analyzer.py**
   - 实时交易信号分析
   - 场景1的实现

2. **claude_periodic_analyzer.py**
   - 定时市场分析（场景2）
   - 每日报告生成（场景3）
   - 新增方法：
     - `should_generate_daily_report()`: 判断是否生成报告
     - `generate_daily_report()`: 生成每日报告
     - `_analyze_daily_report()`: 执行报告分析
     - `_format_trade_history()`: 格式化交易历史
     - `_build_daily_report_prompt()`: 构建报告提示词
     - `_format_daily_report_message()`: 格式化飞书消息

3. **bot.py**
   - 主循环集成
   - 三种场景的调用协调
   - 新增方法：
     - `_get_yesterday_trades()`: 获取昨日交易

4. **claude_guardrails.py**
   - 频率和成本控制
   - 缓存机制
   - 护栏决策

### 数据流程

```
主循环 (bot.py:run_loop)
    ↓
获取市场数据
    ↓
计算技术指标
    ↓
    ├─→ 场景2：定时分析 (每30分钟)
    │   └─→ claude_periodic_analyzer.check_and_analyze()
    │       └─→ 推送到飞书
    │
    ├─→ 场景3：每日报告 (每天8点)
    │   └─→ should_generate_daily_report() → 是否生成？
    │       └─→ generate_daily_report()
    │           ├─→ _get_yesterday_trades()
    │           ├─→ _analyze_daily_report()
    │           └─→ 推送到飞书
    │
    └─→ 检查交易信号
        ↓
        有信号？
        ↓
        场景1：实时分析
        └─→ claude_analyzer.analyze_signal()
            ├─→ 检查护栏和缓存
            ├─→ 调用 Claude API
            └─→ 决策是否执行
```

### API调用参数

**实时信号分析**（场景1）：
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=2000,
    timeout=30,
    messages=[{"role": "user", "content": prompt}]
)
```

**定时市场分析**（场景2）：
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=3000,
    timeout=30,
    messages=[{"role": "user", "content": prompt}]
)
```

**每日报告**（场景3）：
```python
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4000,  # 更长的报告
    timeout=30,
    messages=[{"role": "user", "content": prompt}]
)
```

## 故障排查

### 问题1：每日报告没有生成

**可能原因**：
1. 未到报告时间
2. 今天已经生成过
3. 功能未启用

**检查步骤**：
```python
# 1. 检查配置
ENABLE_CLAUDE_DAILY_REPORT = True
CLAUDE_DAILY_REPORT_HOUR = 8

# 2. 检查当前时间
from datetime import datetime
import pytz
tz = pytz.timezone('Asia/Shanghai')
now = datetime.now(tz)
print(f"当前时间：{now.hour}点")

# 3. 查看日志
grep "每日报告" logs/bot_*.log
```

### 问题2：定时分析太频繁

**解决方案**：
```python
# 增加间隔时间
CLAUDE_PERIODIC_INTERVAL = 60  # 改为1小时
```

### 问题3：API超时

**解决方案**：
```python
# 增加超时时间
CLAUDE_TIMEOUT = 60  # 改为60秒

# 或者使用更快的模型
CLAUDE_MODEL = "claude-haiku-4-5-20250929"
```

### 问题4：成本超限

**解决方案**：
```python
# 方案1：降低调用上限
CLAUDE_MAX_DAILY_CALLS = 200

# 方案2：降低成本上限
CLAUDE_MAX_DAILY_COST = 5.0

# 方案3：禁用某些功能
ENABLE_CLAUDE_PERIODIC_ANALYSIS = False  # 关闭定时分析
```

### 问题5：缓存不生效

**检查步骤**：
```bash
# 查看缓存日志
grep "缓存命中" logs/bot_*.log

# 检查配置
echo $CLAUDE_CACHE_TTL
```

## 性能优化

### 优化1：减少API调用

**策略**：
1. 关闭启动时立即分析
2. 增加定时分析间隔
3. 增加缓存时间
4. 降低日调用上限

**配置示例**：
```python
CLAUDE_ANALYZE_ON_STARTUP = False
CLAUDE_PERIODIC_INTERVAL = 60  # 1小时
CLAUDE_CACHE_TTL = 600  # 10分钟
CLAUDE_MAX_DAILY_CALLS = 200
```

**效果**：
- 启动调用：0次（减少1次）
- 定时调用：24次/天（减少24次）
- 实时调用：取决于信号频率（缓存优化）
- 每日报告：1次/天
- **总计节省**：约25次/天 × 30天 = 750次/月

### 优化2：使用更快的模型

```python
# 使用 Haiku 模型（更快、更便宜）
CLAUDE_MODEL = "claude-haiku-4-5-20250929"
```

**对比**：
- Sonnet：高质量、较慢、较贵
- Haiku：快速、便宜、质量稍低

### 优化3：调整分析详细程度

```python
# 简化分析（更快、更便宜）
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'simple'

# 标准分析（平衡）
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'standard'

# 详细分析（更慢、更贵）
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'detailed'
```

## 扩展开发

### 添加自定义调用场景

```python
# bot.py
def _check_custom_condition(self):
    """自定义场景判断"""
    # 实现你的判断逻辑
    return should_analyze

# 在主循环中调用
if self.claude_periodic_analyzer and self._check_custom_condition():
    self.claude_periodic_analyzer.analyze_now(...)
```

### 自定义报告内容

修改 `claude_periodic_analyzer.py` 中的提示词：

```python
def _build_daily_report_prompt(self, market_data, trade_review):
    prompt = f"""
    自定义你的报告要求...

    {market_data}
    {trade_review}

    自定义输出格式...
    """
    return prompt
```

### 集成其他通知渠道

```python
# claude_periodic_analyzer.py
def generate_daily_report(self, ...):
    # ...生成报告...

    # 推送到飞书
    if self.push_to_feishu:
        notifier.feishu.send_message(message)

    # 添加其他渠道
    # notifier.telegram.send_message(message)
    # notifier.email.send(message)
```

## 最佳实践

### 1. 合理设置调用频率

**推荐配置**（平衡性能和成本）：
```python
# 实时分析：保持启用
ENABLE_CLAUDE_ANALYSIS = True

# 定时分析：30-60分钟
CLAUDE_PERIODIC_INTERVAL = 30

# 每日报告：早上8点
CLAUDE_DAILY_REPORT_HOUR = 8
```

### 2. 监控API使用

```bash
# 每天检查API调用次数
grep "Claude API 调用" logs/bot_*.log | wc -l

# 检查超时情况
grep "超时" logs/bot_*.log

# 检查成本
grep "成本" logs/bot_*.log
```

### 3. 定期回顾报告

- 每周回顾每日报告
- 评估分析质量
- 根据市场变化调整配置

### 4. 成本控制策略

**保守策略**（低成本）：
```python
CLAUDE_PERIODIC_INTERVAL = 60  # 1小时
CLAUDE_MAX_DAILY_CALLS = 100
CLAUDE_MAX_DAILY_COST = 3.0
```

**平衡策略**（推荐）：
```python
CLAUDE_PERIODIC_INTERVAL = 30  # 30分钟
CLAUDE_MAX_DAILY_CALLS = 300
CLAUDE_MAX_DAILY_COST = 8.0
```

**激进策略**（高质量）：
```python
CLAUDE_PERIODIC_INTERVAL = 15  # 15分钟
CLAUDE_MAX_DAILY_CALLS = 500
CLAUDE_MAX_DAILY_COST = 15.0
```

## 更新日志

### v2.0.0 (2024-12-16)
- 🎯 优化：关闭启动时立即分析，减少不必要的API调用
- ✨ 新增：每日报告功能（场景3）
- ✨ 新增：昨日交易历史回顾
- ✨ 新增：结合网络信息的今日行情预测
- ✨ 新增：交易反思和经验教训总结
- 📝 新增：每日报告相关配置项
- 🐛 修复：时区处理问题
- 📚 文档：完善功能说明文档

### v1.0.0 (2024-12-15)
- ✨ 初始版本
- ✨ 实现场景1：实时交易信号分析
- ✨ 实现场景2：30分钟定时市场分析
- ✨ 实现 Claude 护栏和缓存机制
- ✨ 实现飞书推送功能

## 相关文档

- [Claude AI 功能总览](./claude_features.md)
- [状态监控功能说明](./status_monitor.md)
- [风险管理配置](./risk_management.md)
- [策略配置说明](./strategies.md)
