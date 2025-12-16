# 🚀 1周升级路线图

## 核心目标
- ✅ **可验证**：每笔交易都能追溯决策链
- ✅ **可迭代**：通过数据驱动优化
- ✅ **更稳定**：减少致命错误，提升执行质量

---

## Day 1-2: 结构化输出 + 交易标签系统

### ✅ 任务 1.1: 升级 Claude 为结构化打分器（已完成）

**改进点：**
- Claude 现在输出结构化 JSON（可校验）
- 包含：execute、confidence、regime、signal_quality、risk_flags
- 可量化、可统计、可回测

**验收标准：**
```python
# Claude 输出示例
{
  "execute": true,
  "confidence": 0.75,
  "regime": "trend",
  "signal_quality": 0.8,
  "risk_flags": ["counter_trend"],
  "suggested_sl_pct": 0.02
}
```

### 🔨 任务 1.2: 创建交易标签系统

**目标：** 每笔交易记录完整的决策链

**实现文件：** `trade_tagging.py`

**功能：**
1. 记录策略信号详情
2. 记录趋势过滤结果
3. 记录 Claude 分析结果
4. 记录最终执行决策
5. 记录交易结果（盈亏、持仓时间等）

**数据结构：**
```python
TradeTag = {
    "trade_id": "uuid",
    "timestamp": "2025-01-01 12:00:00",

    # 市场状态
    "market_regime": "trend",
    "market_confidence": 0.8,
    "price": 86959,
    "volatility": 0.025,

    # 策略信号
    "strategy": "macd_cross",
    "signal": "long",
    "signal_strength": 0.7,
    "signal_confidence": 0.6,
    "signal_reason": "MACD金叉",

    # 趋势过滤
    "trend_filter_pass": true,
    "trend_filter_reason": "趋势过滤通过",

    # Claude 分析
    "claude_enabled": true,
    "claude_pass": true,
    "claude_confidence": 0.75,
    "claude_regime": "trend",
    "claude_signal_quality": 0.8,
    "claude_risk_flags": ["high_volatility"],
    "claude_reason": "...",

    # 执行决策
    "executed": true,
    "execution_reason": "通过所有检查",

    # 交易结果（平仓后填充）
    "exit_price": 87500,
    "pnl": 541,
    "pnl_pct": 0.62,
    "hold_time_minutes": 45,
    "exit_reason": "止盈"
}
```

**验收标准：**
- 每笔交易都有完整的 TradeTag
- 可以查询：哪些信号被趋势过滤拒绝？
- 可以查询：哪些信号被 Claude 拒绝？
- 可以统计：Claude 拒绝的信号中，有多少是正确的？

### 🔨 任务 1.3: 创建回测对比模块

**目标：** 对比不同配置的效果

**实现文件：** `backtest_comparison.py`

**功能：**
1. 回放历史交易
2. 对比不同配置：
   - 仅策略
   - 策略 + 趋势过滤
   - 策略 + 趋势过滤 + Claude
3. 生成对比报告

**验收标准：**
```bash
python backtest_comparison.py --start 2025-01-01 --end 2025-01-15

输出：
配置A（仅策略）：
  - 交易次数: 50
  - 胜率: 25%
  - 盈亏比: 0.8
  - 最大回撤: -15%

配置B（策略+趋势过滤）：
  - 交易次数: 30
  - 胜率: 40%
  - 盈亏比: 1.2
  - 最大回撤: -8%

配置C（策略+趋势过滤+Claude）：
  - 交易次数: 20
  - 胜率: 55%
  - 盈亏比: 1.5
  - 最大回撤: -5%
```

---

## Day 3-4: Regime 模块增强

### 🔨 任务 2.1: 增加波动率 Regime

**当前问题：** 只有 ranging/transitioning/trending，缺少波动率维度

**改进方案：**
```python
class VolatilityRegime(Enum):
    LOW = "low"           # ATR < 1%
    NORMAL = "normal"     # 1% <= ATR < 2%
    HIGH = "high"         # 2% <= ATR < 3%
    EXTREME = "extreme"   # ATR >= 3%

class EnhancedRegimeInfo:
    trend_regime: MarketRegime      # ranging/transitioning/trending
    volatility_regime: VolatilityRegime
    liquidity_score: float          # 0-1，基于成交量
    hurst_exponent: float           # 0.5=随机游走，>0.5=趋势，<0.5=均值回归
```

**验收标准：**
- 能识别 4 种波动率状态
- 高波动时自动降低仓位
- 极端波动时拒绝交易

### 🔨 任务 2.2: 策略-Regime 匹配矩阵

**目标：** 更精细的策略选择

**实现：**
```python
STRATEGY_REGIME_MATRIX = {
    # 策略: {适合的regime: 权重}
    "bollinger_breakthrough": {
        ("ranging", "low"): 1.0,      # 震荡+低波动=最佳
        ("ranging", "normal"): 0.8,
        ("trending", "low"): 0.3,     # 趋势市不适合
    },
    "macd_cross": {
        ("trending", "normal"): 1.0,  # 趋势+正常波动=最佳
        ("trending", "high"): 0.7,
        ("ranging", "normal"): 0.4,
    },
    # ...
}
```

**验收标准：**
- 震荡市不会触发趋势突破策略
- 趋势市不会触发均值回归策略
- 高波动时降低策略权重

---

## Day 5-6: 执行层风控

### 🔨 任务 3.1: 滑点/点差过滤器

**实现文件：** `execution_filter.py`

**功能：**
```python
class ExecutionFilter:
    def check_spread(self, bid, ask, threshold=0.001):
        """检查点差是否异常"""
        spread_pct = (ask - bid) / bid
        if spread_pct > threshold:
            return False, f"点差过大({spread_pct:.2%})"
        return True, "点差正常"

    def check_slippage(self, expected_price, actual_price, threshold=0.002):
        """检查滑点是否异常"""
        slippage_pct = abs(actual_price - expected_price) / expected_price
        if slippage_pct > threshold:
            return False, f"滑点过大({slippage_pct:.2%})"
        return True, "滑点正常"

    def check_liquidity(self, volume_ratio, threshold=0.5):
        """检查流动性"""
        if volume_ratio < threshold:
            return False, f"流动性不足(量比={volume_ratio:.2f})"
        return True, "流动性充足"
```

**验收标准：**
- 点差 > 0.1% 时拒绝交易
- 滑点 > 0.2% 时拒绝交易
- 量比 < 0.5 时拒绝交易

### 🔨 任务 3.2: 波动冲击过滤器

**功能：**
```python
def check_volatility_spike(self, current_atr, avg_atr, threshold=1.5):
    """检查 ATR 是否突增"""
    if current_atr > avg_atr * threshold:
        return False, f"ATR突增({current_atr/avg_atr:.1f}x)"
    return True, "波动正常"
```

**验收标准：**
- ATR 突增 50% 时延迟进场
- 等待 3 根 K 线后重新评估

### 🔨 任务 3.3: 订单类型优化

**功能：**
```python
def get_optimal_order_type(self, signal_strength, volatility):
    """根据信号强度和波动率选择订单类型"""
    if signal_strength > 0.8 and volatility < 0.02:
        return "market"  # 强信号+低波动=市价单
    elif signal_strength > 0.6:
        return "limit"   # 中等信号=限价单
    else:
        return "reject"  # 弱信号=拒绝
```

**验收标准：**
- 强信号使用市价单（快速成交）
- 弱信号使用限价单（降低成本）
- 极弱信号直接拒绝

---

## Day 7: 仓位管理升级

### 🔨 任务 4.1: 基于波动率的仓位

**当前问题：** 固定仓位比例（10%）

**改进方案：**
```python
def calculate_volatility_adjusted_position(
    self,
    base_size: float,
    current_volatility: float,
    target_volatility: float = 0.02
) -> float:
    """
    基于波动率调整仓位

    公式: adjusted_size = base_size * (target_vol / current_vol)
    """
    if current_volatility == 0:
        return base_size

    adjustment_factor = target_volatility / current_volatility
    adjustment_factor = max(0.5, min(2.0, adjustment_factor))  # 限制在 0.5-2x

    return base_size * adjustment_factor
```

**验收标准：**
- 波动率 1% 时，仓位 = 20%（2x）
- 波动率 2% 时，仓位 = 10%（1x）
- 波动率 4% 时，仓位 = 5%（0.5x）

### 🔨 任务 4.2: 连续亏损熔断

**功能：**
```python
class LossStreakThrottle:
    def get_position_multiplier(self, consecutive_losses: int) -> float:
        """根据连续亏损次数调整仓位"""
        if consecutive_losses >= 5:
            return 0.0  # 完全停止
        elif consecutive_losses >= 3:
            return 0.5  # 减半
        elif consecutive_losses >= 2:
            return 0.75  # 减少 25%
        else:
            return 1.0  # 正常
```

**验收标准：**
- 连续亏损 2 次：仓位 75%
- 连续亏损 3 次：仓位 50%
- 连续亏损 5 次：完全停止交易

### 🔨 任务 4.3: 单日最大亏损熔断

**功能：**
```python
class DailyLossKillSwitch:
    def __init__(self, max_daily_loss_pct=0.05):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_pnl = 0
        self.initial_balance = 0

    def should_stop_trading(self) -> Tuple[bool, str]:
        """检查是否触发熔断"""
        loss_pct = abs(self.daily_pnl) / self.initial_balance

        if loss_pct >= self.max_daily_loss_pct:
            return True, f"单日亏损达到{loss_pct:.1%}，触发熔断"

        return False, "正常"
```

**验收标准：**
- 单日亏损 5% 时停止交易
- 第二天自动重置

---

## 额外优化（时间允许）

### 🔨 任务 5.1: 二阶段确认

**功能：**
```python
class TwoStageConfirmation:
    def __init__(self, confirmation_bars=2):
        self.confirmation_bars = confirmation_bars
        self.pending_signals =

    def add_signal(self, signal):
        """添加待确认信号"""
        self.pending_signals[signal.id] = {
            "signal": signal,
            "trigger_time": datetime.now(),
            "bars_waited": 0
        }

    def check_confirmation(self, signal_id, current_price, key_level):
        """检查信号是否得到确认"""
        pending = self.pending_signals.get(signal_id)
        if not pending:
            return False

        pending["bars_waited"] += 1

        # 确认条件：价格回到关键位置
        if current_price >= key_level and pending["bars_waited"] >= self.confirmation_bars:
            return True

        # 超时失效
        if pending["bars_waited"] > 5:
            del self.pending_signals[signal_id]
            return False

        return False
```

**验收标准：**
- 信号触发后等待 2 根 K 线确认
- 确认条件：价格回到关键均线/突破回踩
- 减少假突破交易

### 🔨 任务 5.2: Claude 反例挖掘

**功能：**
```python
def analyze_losing_trades(self, trades: List[TradeTag]) -> Dict:
    """分析亏损交易的共性"""
    losing_trades = [t for t in trades if t["pnl"] < 0]

    # 统计共性
    common_patterns = {
        "most_common_strategy": Counter([t["strategy"] for t in losing_trades]).most_common(1),
        "most_common_regime": Counter([t["market_regime"] for t in losing_trades]).most_common(1),
        "most_common_risk_flags": Counter([flag for t in losing_trades for flag in t.get("claude_risk_flags", [])]).most_common(3),
        "avg_signal_strength": np.mean([t["signal_strength"] for t in losing_trades]),
        "avg_claude_confidence": np.mean([t["claude_confidence"] for t in losing_trades if t["claude_enabled"]]),
    }

    return common_patterns
```

**验收标准：**
- 每周自动生成亏损分析报告
- 识别最容易亏损的策略/市场状态组合
- 输出可直接变成新的过滤规则

### 🔨 任务 5.3: 多模型分层

**功能：**
```python
class MultiModelAnalyzer:
    def __init__(self):
        self.haiku = ClaudeAnalyzer(model="claude-haiku-4-20250514")
        self.sonnet = ClaudeAnalyzer(model="claude-sonnet-4-5-20250929")

    def analyze(self, signal, indicators):
        """分层分析"""
        # 第一层：Haiku 快速初筛
        haiku_result = self.haiku.analyze_signal(signal, indicators)

        if not haiku_result["execute"]:
            return haiku_result  # Haiku 拒绝，直接返回

        # 第二层：高风险时调用 Sonnet
        if self._is_high_risk(signal, indicators):
            sonnet_result = self.sonnet.analyze_signal(signal, indicators)
            return sonnet_result

        return haiku_result

    def _is_high_risk(self, signal, indicators):
        """判断是否高风险"""
        return (
            indicators["volatility"] > 0.03 or
            signal.strength < 0.6 or
            len(indicators.get("risk_flags", [])) > 2
        )
```

**验收标准：**
- 90% 的信号只用 Haiku（低成本）
- 10% 的高风险信号用 Sonnet（高准确度）
- 成本降低 70%，准确度不降低

---

## 验收总结

### 核心指标

**Day 1-2 验收：**
- ✅ Claude 输出结构化 JSON
- ✅ 每笔交易有完整 TradeTag
- ✅ 可以回测对比不同配置

**Day 3-4 验收：**
- ✅ 识别 4 种波动率状态
- ✅ 策略-Regime 匹配矩阵生效
- ✅ 震荡市不触发趋势策略

**Day 5-6 验收：**
- ✅ 点差/滑点/流动性过滤生效
- ✅ ATR 突增时延迟进场
- ✅ 根据信号强度选择订单类型

**Day 7 验收：**
- ✅ 波动率调整仓位生效
- ✅ 连续亏损自动降杠杆
- ✅ 单日最大亏损熔断生效

### 预期效果

**对比基准（当前）：**
- 胜率：25%
- 盈亏比：0.8
- 最大回撤：-15%
- 连续亏损：6 次

**预期改善（1周后）：**
- 胜率：40-50%（提升 15-25%）
- 盈亏比：1.2-1.5（提升 50-87%）
- 最大回撤：-8%（改善 47%）
- 连续亏损：≤3 次（熔断机制）

---

## 实施建议

### 优先级排序

**必做（P0）：**
1. 结构化输出（Day 1）
2. 交易标签系统（Day 1-2）
3. 执行层风控（Day 5-6）
4. 仓位管理升级（Day 7）

**推荐做（P1）：**
1. Regime 增强（Day 3-4）
2. 回测对比模块（Day 2）

**可选做（P2）：**
1. 二阶段确认
2. Claude 反例挖掘
3. 多模型分层

### 迭代策略

**第1周：** 实现 P0 任务
**第2周：** 实现 P1 任务 + 数据收集
**第3周：** 分析数据，调整参数
**第4周：** 实现 P2 任务（可选）

---

## 下一步行动

1. **立即开始：** 实现交易标签系统（`trade_tagging.py`）
2. **今天完成：** 结构化输出测试
3. **明天开始：** 执行层风控模块

需要我提供具体的代码实现吗？我可以立即生成：
- `trade_tagging.py`（交易标签系统）
- `execution_filter.py`（执行层风控）
- `backtest_comparison.py`（回测对比）
- 或其他任何模块
