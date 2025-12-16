# Claude AI 集成指南

## 概述

本指南介绍如何在量化交易机器人中启用和使用 Claude AI 分析功能，以提高交易决策质量，避免逆势交易。

## 功能特性

### 1. Claude AI 分析器
- **智能信号分析**: 在执行交易前，Claude 会分析市场数据和技术指标
- **趋势判断**: 识别当前市场趋势（强上涨/弱上涨/震荡/弱下跌/强下跌）
- **风险评估**: 评估开仓风险等级（高/中/低）
- **决策建议**: 给出明确的执行/拒绝/等待建议

### 2. 趋势过滤器
- **防止逆势交易**: 自动拒绝在强趋势中的逆势信号
- **极端市场保护**: 在 RSI 极度超买/超卖时避免盲目交易
- **多指标验证**: 综合 EMA、MACD、ADX、RSI 等多个指标判断

## 安装步骤

### 1. 安装依赖

```bash
pip install anthropic
```

### 2. 配置 API Key

在项目根目录创建或编辑 `.env` 文件，添加 Claude API Key：

```bash
# Claude API 配置
CLAUDE_API_KEY=your_claude_api_key_here
```

**获取 API Key:**
1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册/登录账号
3. 在 API Keys 页面创建新的 API Key
4. 复制 API Key 并粘贴到 `.env` 文件

### 3. 启用 Claude 分析

编辑 `config.py` 文件，修改以下配置：

```python
# ==================== Claude AI 分析配置 ====================

# 是否启用 Claude AI 分析
ENABLE_CLAUDE_ANALYSIS = True  # 改为 True

# Claude 模型选择
# claude-opus-4-5-20251101: 最强大，分析最准确，但成本较高
# claude-sonnet-4-5-20250929: 平衡性能和成本（推荐）
# claude-haiku-4-20250514: 最快速，成本最低
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Claude 分析的最小信号强度阈值（低于此值不调用 Claude）
CLAUDE_MIN_SIGNAL_STRENGTH = 0.3

# Claude 分析超时时间（秒）
CLAUDE_TIMEOUT = 10

# Claude 分析失败时的默认行为
# "pass": 分析失败时默认通过信号（推荐，避免阻塞交易）
# "reject": 分析失败时默认拒绝信号（更保守）
CLAUDE_FAILURE_MODE = "pass"
```

### 4. 启用趋势过滤器

趋势过滤器默认启用。如需禁用，在 `config.py` 中添加：

```python
# 趋势过滤器配置
ENABLE_TREND_FILTER = False  # 设为 False 禁用
```

## 工作流程

### 信号处理流程

```
策略生成信号
    ↓
趋势过滤器检查
    ↓ (通过)
Claude AI 分析
    ↓ (通过)
执行交易
```

### 趋势过滤规则

**做多信号过滤:**
- ❌ 强下跌趋势中禁止做多 (ADX>25 且 EMA↓ 且 MACD↓)
- ❌ RSI < 20 时禁止抄底
- ❌ 强下跌趋势中 RSI < 35 时拒绝
- ❌ MACD < -500 时拒绝
- ❌ 布林带极低位置且下跌趋势时拒绝

**做空信号过滤:**
- ❌ 强上涨趋势中禁止做空 (ADX>25 且 EMA↑ 且 MACD↑)
- ❌ RSI > 80 时禁止追空
- ❌ 强上涨趋势中 RSI > 65 时拒绝
- ❌ MACD > 500 时拒绝
- ❌ 布林带极高位置且上涨趋势时拒绝

### Claude 分析规则

Claude 会综合分析以下因素：

1. **趋势判断**
   - EMA 趋势方向
   - MACD 位置和方向
   - ADX 趋势强度
   - DI 指标方向

2. **信号质量**
   - 是否存在逆势交易风险
   - 技术指标是否一致
   - 成交量是否配合

3. **风险评估**
   - 当前市场波动性
   - 趋势强度
   - 超买超卖程度

## 使用示例

### 启动机器人

```bash
python main.py
```

### 日志输出示例

**信号被趋势过滤器拒绝:**
```
[INFO] 📈 开多信号 [bollinger_breakthrough]: 价格连续3根K线突破布林带下轨
[WARNING] ❌ 趋势过滤拒绝: 强下跌趋势中禁止做多 (ADX=32.5, EMA↓, MACD↓)
```

**信号被 Claude 拒绝:**
```
[INFO] 📈 开多信号 [rsi_divergence]: RSI超卖(28.3)且底背离
[INFO] 正在调用 Claude API 进行分析...
[INFO] Claude 分析结果:
[INFO]   决策: REJECT
[INFO]   置信度: 0.85
[INFO]   趋势: 强下跌
[INFO]   风险: 高
[INFO]   原因: 当前处于强下跌趋势，虽然RSI超卖，但EMA、MACD均显示空头，逆势做多风险极高
[WARNING] ❌ Claude 分析拒绝: 当前处于强下跌趋势，虽然RSI超卖，但EMA、MACD均显示空头，逆势做多风险极高
[WARNING]    ⚠️  强下跌趋势中逆势做多
[WARNING]    ⚠️  MACD深度负值表明空头力量强劲
```

**信号通过所有检查:**
```
[INFO] 📈 开多信号 [macd_cross]: MACD金叉（零轴下方，反转信号）
[INFO] 正在调用 Claude API 进行分析...
[INFO] Claude 分析结果:
[INFO]   决策: EXECUTE
[INFO]   置信度: 0.78
[INFO]   趋势: 弱上涨
[INFO]   风险: 中
[INFO]   原因: MACD金叉且RSI从超卖区回升，EMA即将金叉，趋势可能反转，可以尝试做多
[INFO] ✅ 信号通过所有检查 (趋势过滤 + Claude AI)
[INFO] 执行开多...
```

## 成本估算

### Claude API 定价（2025年）

| 模型 | 输入价格 | 输出价格 | 单次分析成本 |
|------|---------|---------|-------------|
| Claude Opus 4.5 | $15/MTok | $75/MTok | ~$0.05-0.10 |
| Claude Sonnet 4.5 | $3/MTok | $15/MTok | ~$0.01-0.02 |
| Claude Haiku 4 | $0.80/MTok | $4/MTok | ~$0.003-0.005 |

**估算:**
- 每次分析约消耗 2000-3000 tokens
- 使用 Sonnet 4.5（推荐）：每次分析约 $0.01-0.02
- 如果每天分析 50 次信号：约 $0.50-1.00/天
- 月成本约：$15-30

**优化建议:**
- 设置 `CLAUDE_MIN_SIGNAL_STRENGTH` 过滤弱信号
- 使用 Haiku 模型降低成本（适合高频交易）
- 只在关键时刻启用 Claude 分析

## 测试

### 运行测试脚本

```bash
python test_claude_integration.py
```

测试脚本会验证：
- Claude API 连接
- 趋势过滤器功能
- 信号分析流程

### 手动测试

1. **测试趋势过滤器:**
```python
from trend_filter import get_trend_filter
from strategies import Signal, TradeSignal
import pandas as pd

# 创建测试数据
df = pd.DataFrame({
    'close': [100, 99, 98, 97, 96],
    'volume': [1000, 1100, 1200, 1300, 1400]
})

# 创建做多信号
signal = TradeSignal(Signal.LONG, "test", "测试信号")

# 模拟指标（强下跌趋势）
indicators = {
    'rsi': 25,
    'macd': -600,
    'ema_short': 97,
    'ema_long': 100,
    'adx': 35,
    'plus_di': 15,
    'minus_di': 35,
}

# 检查信号
trend_filter = get_trend_filter()
passed, reason = trend_filter.check_signal(df, signal, indicators)
print(f"通过: {passed}, 原因: {reason}")
# 预期输出: 通过: False, 原因: 强下跌趋势中禁止做多 (ADX=35.0, EMA↓, MACD↓)
```

2. **测试 Claude 分析器:**
```python
from claude_analyzer import get_claude_analyzer
from strategies import Signal, TradeSignal
import pandas as pd

# 创建测试数据
df = pd.DataFrame({
    'close': [100, 99, 98, 97, 96],
    'volume': [1000, 1100, 1200, 1300, 1400]
})

# 创建信号
signal = TradeSignal(Signal.LONG, "test", "测试信号")

# 模拟指标
indicators = {
    'rsi': 25,
    'macd': -600,
    'ema_short': 97,
    'ema_long': 100,
    'adx': 35,
}

# 分析信号
analyzer = get_claude_analyzer()
passed, reason, details = analyzer.analyze_signal(
    df, 96, signal, indicators
)
print(f"通过: {passed}")
print(f"原因: {reason}")
print(f"详情: {details}")
```

## 故障排查

### 问题 1: Claude API 调用失败

**错误信息:**
```
Claude 分析失败: Authentication error
```

**解决方案:**
1. 检查 `.env` 文件中的 `CLAUDE_API_KEY` 是否正确
2. 确认 API Key 有效且未过期
3. 检查网络连接

### 问题 2: anthropic 库未安装

**错误信息:**
```
警告: anthropic 库未安装，Claude 分析功能将被禁用
```

**解决方案:**
```bash
pip install anthropic
```

### 问题 3: Claude 分析超时

**错误信息:**
```
Claude 分析失败: Timeout
```

**解决方案:**
1. 增加 `CLAUDE_TIMEOUT` 配置值
2. 检查网络连接速度
3. 考虑使用更快的 Haiku 模型

### 问题 4: 所有信号都被拒绝

**可能原因:**
- 当前市场处于强趋势，策略生成的是逆势信号
- 趋势过滤器规则过于严格

**解决方案:**
1. 检查日志，了解拒绝原因
2. 调整策略配置，使用趋势跟随策略
3. 如需禁用趋势过滤器，设置 `ENABLE_TREND_FILTER = False`
4. 如需禁用 Claude 分析，设置 `ENABLE_CLAUDE_ANALYSIS = False`

## 最佳实践

### 1. 渐进式启用

建议按以下顺序启用功能：

1. **第一阶段**: 只启用趋势过滤器
   ```python
   ENABLE_TREND_FILTER = True
   ENABLE_CLAUDE_ANALYSIS = False
   ```
   观察 1-2 天，确认趋势过滤器工作正常

2. **第二阶段**: 启用 Claude 分析（使用 Haiku 模型）
   ```python
   ENABLE_TREND_FILTER = True
   ENABLE_CLAUDE_ANALYSIS = True
   CLAUDE_MODEL = "claude-haiku-4-20250514"
   ```
   观察成本和效果

3. **第三阶段**: 升级到 Sonnet 模型
   ```python
   CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
   ```

### 2. 监控和优化

- **每日检查日志**: 了解哪些信号被拒绝，原因是什么
- **统计胜率变化**: 对比启用前后的交易胜率
- **成本控制**: 监控 Claude API 使用量和成本
- **调整阈值**: 根据实际效果调整 `CLAUDE_MIN_SIGNAL_STRENGTH`

### 3. 策略配合

建议使用以下策略组合：

**趋势市场:**
```python
ENABLE_STRATEGIES = [
    "macd_cross",
    "ema_cross",
    "adx_trend",
]
```

**震荡市场:**
```python
ENABLE_STRATEGIES = [
    "bollinger_breakthrough",
    "rsi_divergence",
    "kdj_cross",
]
```

**动态策略（推荐）:**
```python
USE_DYNAMIC_STRATEGY = True  # 自动根据市场状态选择策略
```

## 性能影响

### 延迟

- **趋势过滤器**: <1ms（几乎无延迟）
- **Claude API 调用**: 1-5秒（取决于网络和模型）

### 建议

- 使用 Haiku 模型可将延迟降至 1-2 秒
- 设置合理的 `CLAUDE_TIMEOUT` 避免长时间等待
- 在高频交易场景下，考虑只使用趋势过滤器

## 总结

通过集成 Claude AI 和趋势过滤器，你的交易机器人将能够：

✅ **避免逆势交易** - 不再在强下跌趋势中盲目做多
✅ **提高信号质量** - AI 辅助判断，过滤低质量信号
✅ **降低风险** - 多层检查机制，减少亏损交易
✅ **提升胜率** - 只在高概率机会时开仓

根据你的诊断报告，当前的主要问题是"逆势抄底"，这正是 Claude 集成要解决的核心问题。启用后，类似"在 RSI=14 时做多"的信号将被智能拒绝。

## 支持

如有问题，请查看：
- 日志文件: `logs/trading_bot.log`
- 数据库: `trading_bot.db`
- Claude 文档: https://docs.anthropic.com/

祝交易顺利！🚀
