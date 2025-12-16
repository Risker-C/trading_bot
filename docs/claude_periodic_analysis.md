# Claude AI 定时分析功能说明文档

## 概述

Claude AI 定时分析功能是一个智能市场分析系统，能够定期自动分析市场状态、评估风险、识别交易机会，并通过飞书推送分析报告。该功能基于 Anthropic 的 Claude AI 模型，提供专业的量化交易分析建议。

**核心价值**：
- 🤖 自动化市场分析，无需人工盯盘
- 📊 多维度分析（趋势、风险、机会、情绪）
- 📱 实时推送到飞书，随时掌握市场动态
- 🎯 基于技术指标的专业分析建议
- ⏰ 可配置的分析间隔和详细程度

## 功能特性

### 1. 定时自动分析
- 按配置的时间间隔自动执行市场分析
- 默认间隔：30分钟（可配置10-360分钟）
- 支持启动时立即分析一次

### 2. 多维度分析模块

#### 市场趋势分析 (market_trend)
- 趋势方向识别（上涨/下跌/震荡）
- 趋势强度评估（强/中/弱）
- 趋势可持续性判断（高/中/低）
- 基于 EMA、MACD、ADX 等指标

#### 风险评估 (risk_assessment)
- 风险等级评定（低/中/高）
- 主要风险因素识别
- 风险来源分析（波动、逆势、极端指标等）

#### 入场机会识别 (entry_opportunities)
- 是否存在入场机会
- 建议的交易方向（做多/做空/观望）
- 建议的入场价位
- 机会置信度评分（0-1）

#### 持仓建议 (position_advice)
- 无持仓时：是否适合开仓、建议仓位大小
- 有持仓时：持有/加仓/减仓/平仓建议
- 建议原因和依据

#### 市场情绪分析 (market_sentiment)
- 市场情绪识别（极度恐慌/恐慌/中性/贪婪/极度贪婪）
- 情绪对价格的影响分析
- 基于 RSI、布林带位置等指标

### 3. 飞书推送
- 格式化的分析报告
- 使用 emoji 增强可读性
- 包含关键指标和建议
- 推送失败时记录错误日志

### 4. 灵活配置
- 可配置分析间隔
- 可配置分析详细程度（simple/standard/detailed）
- 可选择启用的分析模块
- 可配置是否推送到飞书

## 配置说明

### 配置文件位置
`config.py`

### 配置项详解

```python
# ==================== Claude定时分析配置 ====================

# 是否启用Claude定时分析
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True

# 定时分析间隔（分钟）
# 范围：10-360分钟
# 建议：30-60分钟
CLAUDE_PERIODIC_INTERVAL = 30

# 分析详细程度
# - 'simple': 简要分析，每个维度1-2句话
# - 'standard': 标准分析，每个维度2-3句话（推荐）
# - 'detailed': 详细分析，包含具体数据支撑
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'standard'

# 是否在启动时立即分析一次
CLAUDE_ANALYZE_ON_STARTUP = True

# 是否通过飞书推送分析结果
CLAUDE_PUSH_TO_FEISHU = True

# 分析包含的模块（可选择性启用）
CLAUDE_ANALYSIS_MODULES = {
    'market_trend': True,      # 市场趋势分析
    'risk_assessment': True,   # 风险评估
    'entry_opportunities': True,  # 入场机会
    'position_advice': True,   # 持仓建议
    'market_sentiment': True,  # 市场情绪
}
```

### 依赖配置

Claude定时分析依赖以下配置：

```python
# Claude AI 基础配置
ENABLE_CLAUDE_ANALYSIS = True
CLAUDE_API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
CLAUDE_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")  # 可选
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# 飞书推送配置（如果启用飞书推送）
ENABLE_FEISHU = True
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
```

### 环境变量

需要在 `.env` 文件中配置：

```bash
# Claude API 配置
ANTHROPIC_AUTH_TOKEN=your_claude_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com  # 可选，自定义端点

# 飞书 Webhook
FEISHU_WEBHOOK_URL=your_feishu_webhook_url
```

## 使用方法

### 1. 启用功能

在 `config.py` 中设置：

```python
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True
CLAUDE_PERIODIC_INTERVAL = 30  # 30分钟分析一次
```

### 2. 配置环境变量

确保 `.env` 文件包含必要的配置：

```bash
ANTHROPIC_AUTH_TOKEN=sk-ant-xxx
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 3. 启动交易机器人

```bash
python main.py
```

或使用启动脚本：

```bash
./start_bot.sh
```

### 4. 查看分析结果

- **飞书通知**：分析结果会自动推送到配置的飞书群
- **日志文件**：查看 `logs/trading_bot.log` 中的分析日志

### 5. 手动触发分析（可选）

如果需要立即执行一次分析，可以重启服务（如果配置了 `CLAUDE_ANALYZE_ON_STARTUP = True`）。

## 技术实现

### 核心模块

**文件**：`claude_periodic_analyzer.py`

**主要类**：`ClaudePeriodicAnalyzer`

**关键方法**：

1. `should_analyze()` - 判断是否应该执行分析
2. `analyze_market()` - 执行市场分析
3. `check_and_analyze()` - 检查并执行分析
4. `analyze_now()` - 立即执行分析并推送

### 数据流程

```
主循环 (bot.py)
    ↓
获取K线数据和当前价格
    ↓
计算技术指标
    ↓
准备持仓信息
    ↓
ClaudePeriodicAnalyzer.check_and_analyze()
    ↓
判断是否到达分析时间
    ↓ (是)
格式化市场数据
    ↓
构建分析提示词
    ↓
调用 Claude API
    ↓
解析 JSON 响应
    ↓
格式化飞书消息
    ↓
推送到飞书
    ↓
记录日志
```

### 技术指标使用

分析基于以下技术指标：

- **趋势指标**：RSI, MACD, EMA(9), EMA(21)
- **波动指标**：布林带（上轨、中轨、下轨）、ATR
- **趋势强度**：ADX, +DI, -DI
- **成交量**：量比
- **价格变化**：1小时、4小时、24小时涨跌幅

### Claude API 调用

```python
response = self.client.messages.create(
    model=self.model,  # claude-sonnet-4-5-20250929
    max_tokens=3000,
    messages=[
        {"role": "user", "content": prompt}
    ]
)
```

### 飞书消息格式

```
📊 Claude AI 市场分析报告 #1

⏰ 时间: 2025-12-16 10:30:00
💰 当前价格: 42500.00 USDT

📈 市场趋势
方向: 上涨 | 强度: 强
当前市场处于强势上涨趋势...

🟢 风险评估
风险等级: 低
市场风险较低，技术指标健康...

✅ 入场机会
方向: 做多 | 置信度: 75%
存在较好的做多机会...

💡 持仓建议
操作: 持有 | 仓位: 10%
建议继续持有当前仓位...

😐 市场情绪
情绪: 中性
市场情绪相对平稳...

📝 整体总结
市场处于健康的上涨趋势中...

🔑 关键点
1. EMA9 > EMA21，趋势向上
2. RSI 处于健康区间
3. 成交量配合良好

---
🤖 由 Claude AI 生成 | 间隔: 30分钟
```

## 故障排查

### 问题1：分析未触发

**可能原因**：
- `ENABLE_CLAUDE_PERIODIC_ANALYSIS` 未设置为 `True`
- `CLAUDE_API_KEY` 未配置或无效
- 分析间隔未到

**解决方法**：
1. 检查 `config.py` 配置
2. 检查 `.env` 文件中的 API Key
3. 查看日志：`grep "Claude定时分析" logs/trading_bot.log`

### 问题2：飞书推送失败

**可能原因**：
- `FEISHU_WEBHOOK_URL` 未配置或无效
- 飞书机器人未启用
- 网络连接问题

**解决方法**：
1. 检查飞书 Webhook URL 是否正确
2. 测试 Webhook：`curl -X POST -H "Content-Type: application/json" -d '{"msg_type":"text","content":{"text":"test"}}' YOUR_WEBHOOK_URL`
3. 查看日志：`grep "飞书" logs/trading_bot.log`

### 问题3：Claude API 调用失败

**可能原因**：
- API Key 无效或过期
- API 配额用尽
- 网络连接问题
- 自定义端点配置错误

**解决方法**：
1. 验证 API Key 是否有效
2. 检查 API 使用量和配额
3. 检查 `CLAUDE_BASE_URL` 配置（如果使用自定义端点）
4. 查看详细错误日志

### 问题4：分析结果解析失败

**可能原因**：
- Claude 响应格式不符合预期
- JSON 解析错误

**解决方法**：
1. 查看日志中的 Claude 响应内容
2. 检查是否有网络传输错误
3. 尝试使用不同的 `CLAUDE_ANALYSIS_DETAIL_LEVEL`

### 日志查看命令

```bash
# 查看所有Claude定时分析日志
grep "claude_periodic_analyzer" logs/trading_bot.log

# 查看分析成功日志
grep "Claude 市场分析完成" logs/trading_bot.log

# 查看分析失败日志
grep "Claude定时分析失败" logs/trading_bot.log

# 查看飞书推送日志
grep "飞书" logs/trading_bot.log

# 实时监控日志
tail -f logs/trading_bot.log | grep "Claude"
```

## 性能优化

### 1. 调整分析间隔

根据交易频率和市场波动性调整：

- **高频交易**：15-30分钟
- **中频交易**：30-60分钟（推荐）
- **低频交易**：60-120分钟

### 2. 选择合适的详细程度

- **simple**：快速分析，降低 API 成本
- **standard**：平衡性能和详细度（推荐）
- **detailed**：深度分析，适合重要决策

### 3. 选择性启用模块

如果只关注特定维度，可以禁用不需要的模块：

```python
CLAUDE_ANALYSIS_MODULES = {
    'market_trend': True,      # 保留
    'risk_assessment': True,   # 保留
    'entry_opportunities': False,  # 禁用
    'position_advice': True,   # 保留
    'market_sentiment': False,  # 禁用
}
```

### 4. API 成本控制

- 使用 Claude 护栏功能限制日调用次数
- 配置 `CLAUDE_MAX_DAILY_CALLS` 和 `CLAUDE_MAX_DAILY_COST`
- 监控 API 使用量

### 5. 缓存优化

系统会自动记录上次分析时间，避免重复调用。

## 扩展开发

### 添加新的分析模块

1. 在 `config.py` 中添加模块配置：

```python
CLAUDE_ANALYSIS_MODULES = {
    # ... 现有模块
    'custom_module': True,  # 新模块
}
```

2. 在 `claude_periodic_analyzer.py` 中更新提示词：

```python
if self.modules.get('custom_module', True):
    analysis_modules.append("6. **自定义模块**: 自定义分析内容")
```

3. 更新 JSON 输出格式和解析逻辑。

### 自定义飞书消息格式

修改 `_format_feishu_message()` 方法：

```python
def _format_feishu_message(self, analysis: Dict) -> str:
    # 自定义消息格式
    message = "自定义格式..."
    return message
```

### 集成其他通知渠道

在 `analyze_now()` 方法中添加：

```python
# 推送到 Telegram
if self.push_to_telegram:
    notifier.telegram.send_message(message)

# 推送到邮件
if self.push_to_email:
    notifier.email.send_message(message)
```

### 添加历史分析记录

在数据库中记录分析历史：

```python
db.log_claude_analysis(
    timestamp=datetime.now(),
    analysis=analysis,
    current_price=current_price
)
```

## 最佳实践

### 1. 配置建议

- **生产环境**：
  - 间隔：30-60分钟
  - 详细程度：standard
  - 启用所有模块
  - 启用飞书推送

- **测试环境**：
  - 间隔：10-15分钟
  - 详细程度：detailed
  - 启用所有模块
  - 启用飞书推送

### 2. 监控建议

- 定期检查日志，确保分析正常执行
- 监控 API 调用次数和成本
- 关注飞书推送成功率
- 定期审查分析质量

### 3. 安全建议

- 不要在代码中硬编码 API Key
- 使用环境变量管理敏感信息
- 定期轮换 API Key
- 限制飞书 Webhook 的访问权限

### 4. 使用建议

- 结合人工判断，不要完全依赖 AI 分析
- 关注分析的置信度评分
- 注意风险警告和风险因素
- 在重要决策前查看详细分析

### 5. 成本优化

- 合理设置分析间隔，避免过于频繁
- 使用 simple 模式降低 token 消耗
- 配置日调用上限和成本上限
- 监控 API 使用情况

## 更新日志

### v1.0.0 (2025-12-16)

**新增功能**：
- ✅ Claude AI 定时市场分析
- ✅ 多维度分析（趋势、风险、机会、持仓、情绪）
- ✅ 飞书推送分析报告
- ✅ 可配置的分析间隔和详细程度
- ✅ 模块化分析配置
- ✅ 启动时立即分析选项

**技术实现**：
- 新增 `claude_periodic_analyzer.py` 核心模块
- 集成到 `bot.py` 主循环
- 新增配置项到 `config.py`
- 完善的错误处理和日志记录

**文档**：
- 完整的功能说明文档
- 配置说明和使用指南
- 故障排查指南
- 最佳实践建议

## 相关文档

- [Claude AI 分析器文档](./claude_analyzer.md)（如果存在）
- [状态监控功能文档](./status_monitor.md)（如果存在）
- [飞书通知配置文档](./feishu_notification.md)（如果存在）
- [配置文件说明](./config.md)（如果存在）

## 技术支持

如有问题或建议，请：

1. 查看日志文件：`logs/trading_bot.log`
2. 检查配置文件：`config.py`
3. 查看测试用例：`scripts/test_claude_periodic_analysis.py`
4. 提交 Issue 或联系开发团队

---

**注意**：本功能依赖 Claude API，会产生 API 调用费用。请合理配置分析间隔和详细程度，控制成本。
