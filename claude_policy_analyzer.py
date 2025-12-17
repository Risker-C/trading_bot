"""
Claude Policy Analyzer - 策略治理分析器

这是专门用于策略治理的 Claude 分析器，与 claude_analyzer.py 不同：
- claude_analyzer.py: 用于信号验证（EXECUTE/REJECT）
- claude_policy_analyzer.py: 用于策略参数治理（调参数/切策略/改风控）

核心职责：
1. 判断市场制度（Regime）
2. 给出策略参数与风控参数的调整建议
3. 基于历史交易 + 当前持仓 + 实时行情进行策略层治理
"""

import json
from typing import Dict, Optional
from datetime import datetime
import pandas as pd

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

import config
from logger_utils import get_logger
from policy_layer import (
    TradingContext, PolicyDecision, MarketRegime, RiskMode
)

logger = get_logger("claude_policy_analyzer")


class ClaudePolicyAnalyzer:
    """Claude 策略治理分析器"""

    def __init__(self):
        """初始化"""
        self.api_key = getattr(config, 'CLAUDE_API_KEY', None)
        self.base_url = getattr(config, 'CLAUDE_BASE_URL', None)
        self.enabled = getattr(config, 'ENABLE_CLAUDE_ANALYSIS', False)
        self.model = getattr(config, 'CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
        self.timeout = getattr(config, 'CLAUDE_TIMEOUT', 30)

        if not ANTHROPIC_AVAILABLE:
            self.enabled = False
            logger.warning("anthropic 库未安装，Claude Policy 分析已禁用")
            return

        if not self.api_key:
            self.enabled = False
            logger.warning("未配置 CLAUDE_API_KEY，Claude Policy 分析已禁用")
            return

        if self.enabled:
            try:
                if self.base_url:
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key,
                        base_url=self.base_url
                    )
                    logger.info(f"Claude Policy 分析器初始化成功 (自定义端点: {self.base_url})")
                else:
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                    logger.info("Claude Policy 分析器初始化成功")
            except Exception as e:
                self.enabled = False
                logger.error(f"Claude 客户端初始化失败: {e}")

    def _format_trading_context(
        self,
        context: TradingContext,
        df: pd.DataFrame,
        indicators: Dict
    ) -> str:
        """
        格式化交易上下文为 Claude 可理解的文本

        Args:
            context: 交易上下文
            df: K线数据
            indicators: 技术指标

        Returns:
            格式化的文本
        """
        # 计算价格变化
        current_price = context.current_price
        price_change_24h = ((current_price - df['close'].iloc[-96]) / df['close'].iloc[-96] * 100) if len(df) >= 96 else 0
        price_change_4h = ((current_price - df['close'].iloc[-16]) / df['close'].iloc[-16] * 100) if len(df) >= 16 else 0
        price_change_1h = ((current_price - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100) if len(df) >= 4 else 0

        # 获取技术指标（安全获取最后一个值）
        def get_last_value(indicators, key, default='N/A'):
            value = indicators.get(key, default)
            if hasattr(value, 'iloc'):
                return value.iloc[-1] if len(value) > 0 else default
            return value

        rsi = get_last_value(indicators, 'rsi')
        macd = get_last_value(indicators, 'macd')
        macd_signal = get_last_value(indicators, 'macd_signal')
        macd_histogram = get_last_value(indicators, 'macd_histogram')
        ema_short = get_last_value(indicators, 'ema_short')
        ema_long = get_last_value(indicators, 'ema_long')
        bb_upper = get_last_value(indicators, 'bb_upper')
        bb_middle = get_last_value(indicators, 'bb_middle')
        bb_lower = get_last_value(indicators, 'bb_lower')
        bb_percent = get_last_value(indicators, 'bb_percent_b')
        adx = get_last_value(indicators, 'adx')
        plus_di = get_last_value(indicators, 'plus_di')
        minus_di = get_last_value(indicators, 'minus_di')
        volume_ratio = get_last_value(indicators, 'volume_ratio')
        atr = get_last_value(indicators, 'atr')

        # 构建上下文文本
        context_text = f"""
## 交易系统状态 (时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### A. 历史交易状态（系统状态）
- 最近交易次数: {context.recent_trades_count}
- 胜率: {context.win_rate:.1%}
- 最近盈亏: {context.recent_pnl:+.2f} USDT
- 连续亏损: {context.consecutive_losses} 次
- 连续盈利: {context.consecutive_wins} 次
- 平均盈利: {context.avg_win:.2f} USDT
- 平均亏损: {context.avg_loss:.2f} USDT
- 当前风控模式: {context.current_risk_mode.value}

### B. 当前持仓状态（仓位状态）
"""
        if context.has_position:
            context_text += f"""- 持仓方向: {context.position_side.upper()}
- 持仓数量: {context.position_amount:.6f}
- 入场价: {context.entry_price:.2f} USDT
- 当前价: {context.current_price:.2f} USDT
- 未实现盈亏: {context.unrealized_pnl:+.2f} USDT ({context.unrealized_pnl_pct:+.2f}%)
- 持仓时间: {context.holding_time_minutes:.0f} 分钟
- 当前止损: {context.current_stop_loss:.2f} USDT
- 当前止盈: {context.current_take_profit:.2f} USDT
"""
        else:
            context_text += "- 无持仓\n"

        context_text += f"""
### C. 实时市场结构（行情状态）
- 当前价格: {current_price:.2f} USDT
- 24小时变化: {price_change_24h:+.2f}%
- 4小时变化: {price_change_4h:+.2f}%
- 1小时变化: {price_change_1h:+.2f}%

**趋势指标:**
- RSI(14): {rsi}
- MACD: {macd}
- MACD Signal: {macd_signal}
- MACD Histogram: {macd_histogram}
- EMA(9): {ema_short}
- EMA(21): {ema_long}
- EMA趋势: {'看涨' if ema_short > ema_long else '看跌'} (EMA9 {'>' if ema_short > ema_long else '<'} EMA21)

**波动指标:**
- 布林带上轨: {bb_upper}
- 布林带中轨: {bb_middle}
- 布林带下轨: {bb_lower}
- 布林带位置: {bb_percent} (0=下轨, 1=上轨)
- ATR: {atr}

**趋势强度:**
- ADX: {adx} ({'强趋势' if adx > 25 else '弱趋势/震荡'})
- +DI: {plus_di}
- -DI: {minus_di}
- DI方向: {'看涨' if plus_di > minus_di else '看跌'} (+DI {'>' if plus_di > minus_di else '<'} -DI)

**成交量:**
- 量比: {volume_ratio} ({'放量' if volume_ratio > 1.5 else '缩量' if volume_ratio < 0.8 else '正常'})

**当前市场制度判断:**
- 制度: {context.market_regime.value}
- 趋势方向: {context.trend_direction} (1=上涨, -1=下跌, 0=震荡)
- 波动率: {context.volatility:.2%}

### D. 系统运行状态
- 今日盈亏: {context.daily_pnl:+.2f} USDT
- 今日交易次数: {context.daily_trades}
"""
        return context_text

    def _build_policy_prompt(
        self,
        context_text: str,
        context: TradingContext
    ) -> str:
        """
        构建策略治理提示词

        Args:
            context_text: 格式化的交易上下文
            context: 交易上下文对象

        Returns:
            完整的提示词
        """
        prompt = f"""你是一个专业的量化交易策略治理专家。你的职责是**调整策略参数和风控参数**，而不是直接决定买卖。

{context_text}

## 你的职责（策略治理层）

你需要从以下3个维度进行分析和决策：

### 1️⃣ 判断市场制度（Regime）

根据技术指标判断当前市场处于哪种制度：

- **trend**: 趋势市（ADX > 25，方向明确，EMA排列清晰）
  - 适合趋势跟随策略
  - 可以放宽止损，提高止盈目标
  - 启用移动止损保护利润

- **mean_revert**: 均值回归/震荡市（ADX < 20，价格在布林带中轨附近波动）
  - 适合区间交易策略
  - 收紧止损，快速止盈
  - 禁用趋势跟随策略

- **chop**: 混乱市（方向不明，高波动，指标冲突）
  - 减少交易频率
  - 降低仓位
  - 收紧止损

### 2️⃣ 给出策略参数与风控参数的调整建议

**止损止盈调整:**
- suggested_stop_loss_pct: 建议的止损百分比（0.005-0.05，即0.5%-5%）
- suggested_take_profit_pct: 建议的止盈百分比（0.01-0.10，即1%-10%）
- suggested_trailing_stop_pct: 建议的移动止损百分比（0.005-0.03，即0.5%-3%）
- enable_trailing_stop: 是否启用移动止损（true/false）

**仓位调整:**
- suggested_position_multiplier: 仓位倍数（0.3-2.0）
  - 1.0 = 正常仓位
  - 0.5 = 减半仓位（高风险时）
  - 1.5 = 增加仓位（高确定性时）

**风控模式建议:**
- suggested_risk_mode: 建议的风控模式
  - "normal": 正常模式
  - "defensive": 防守模式（连续亏损 >= 3次时）
  - "recovery": 恢复模式（从防守恢复中）
  - "aggressive": 激进模式（连续盈利 >= 3次时）

### 3️⃣ 基于历史交易 + 当前持仓 + 实时行情进行策略层治理

**关键判断规则:**

1. **连续亏损处理:**
   - 连续亏损 >= 3次 → 切换到 defensive 模式，减少仓位，收紧止损
   - 连续亏损 >= 5次 → 建议暂停交易（通过极低的仓位倍数实现）

2. **持仓管理:**
   - 如果有持仓且浮亏 > 1% → 建议收紧止损
   - 如果有持仓且浮盈 > 2% → 建议启用移动止损保护利润
   - 如果持仓时间过长（> 4小时）且未盈利 → 建议降低止盈目标快速出场

3. **市场适应:**
   - 震荡市（ADX < 20）→ 禁用趋势策略，启用区间策略
   - 强趋势市（ADX > 35）→ 禁用区间策略，启用趋势策略
   - 高波动市（量比 > 2.0）→ 减少仓位，放宽止损

4. **风险控制:**
   - 今日亏损 > 100 USDT → 切换到 defensive 模式
   - 胜率 < 40% → 减少仓位，收紧止损
   - 成交量严重萎缩（量比 < 0.5）→ 降低仓位

## 输出格式（严格JSON）

```json
{{
  "regime": "trend",
  "regime_confidence": 0.75,
  "suggested_risk_mode": "normal",
  "suggested_stop_loss_pct": 0.02,
  "suggested_take_profit_pct": 0.04,
  "suggested_trailing_stop_pct": 0.015,
  "enable_trailing_stop": true,
  "suggested_position_multiplier": 1.0,
  "strategies_to_enable": [],
  "strategies_to_disable": [],
  "confidence": 0.8,
  "reason": "简短理由（2-3句话，说明为什么这样调整）",
  "ttl_minutes": 30
}}
```

**重要约束:**
1. 只输出JSON，不要有任何其他文字
2. 所有百分比参数必须是小数形式（如 0.02 表示 2%）
3. confidence 表示你对这个决策的置信度（0-1）
4. ttl_minutes 表示这个决策的有效期（分钟）
5. 如果不需要调整某个参数，设置为 null

**当前系统默认参数（供参考）:**
- 止损: 2%
- 止盈: 4%
- 移动止损: 1.5%
- 仓位倍数: 1.0x
- 风控模式: {context.current_risk_mode.value}
"""
        return prompt

    def analyze_for_policy(
        self,
        context: TradingContext,
        df: pd.DataFrame,
        indicators: Dict
    ) -> Optional[PolicyDecision]:
        """
        执行策略治理分析

        Args:
            context: 交易上下文
            df: K线数据
            indicators: 技术指标

        Returns:
            策略决策，失败返回 None
        """
        if not self.enabled:
            logger.debug("Claude Policy 分析未启用")
            return None

        try:
            # 格式化交易上下文
            context_text = self._format_trading_context(context, df, indicators)

            # 构建提示词
            prompt = self._build_policy_prompt(context_text, context)

            # 调用 Claude API
            logger.info("🤖 正在调用 Claude API 进行策略治理分析...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                timeout=self.timeout,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # 解析响应
            response_text = response.content[0].text
            logger.debug(f"Claude 响应: {response_text}")

            # 提取 JSON
            analysis = self._parse_response(response_text)

            if not analysis:
                logger.error("无法解析 Claude 响应")
                return None

            # 构建 PolicyDecision
            decision = self._build_policy_decision(analysis)

            logger.info(f"✅ Claude 策略治理分析完成:")
            logger.info(f"   市场制度: {decision.regime.value} (置信度: {decision.regime_confidence:.2f})")
            logger.info(f"   风控模式: {decision.suggested_risk_mode.value if decision.suggested_risk_mode else 'N/A'}")
            logger.info(f"   止损建议: {decision.suggested_stop_loss_pct:.2%}" if decision.suggested_stop_loss_pct else "   止损建议: 无调整")
            logger.info(f"   止盈建议: {decision.suggested_take_profit_pct:.2%}" if decision.suggested_take_profit_pct else "   止盈建议: 无调整")
            logger.info(f"   仓位倍数: {decision.suggested_position_multiplier:.2f}x" if decision.suggested_position_multiplier else "   仓位倍数: 无调整")
            logger.info(f"   原因: {decision.reason}")

            return decision

        except Exception as e:
            logger.error(f"Claude 策略治理分析失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """
        解析 Claude 响应，提取 JSON

        Args:
            response_text: Claude 响应文本

        Returns:
            解析后的字典，失败返回 None
        """
        try:
            # 尝试直接解析
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 代码块
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取任何 JSON 对象
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"无法从响应中提取 JSON: {response_text[:200]}")
        return None

    def _build_policy_decision(self, analysis: Dict) -> PolicyDecision:
        """
        从 Claude 响应构建 PolicyDecision

        Args:
            analysis: 解析后的 JSON 字典

        Returns:
            PolicyDecision 对象
        """
        # 解析市场制度
        regime_str = analysis.get('regime', 'unknown')
        try:
            regime = MarketRegime(regime_str)
        except ValueError:
            regime = MarketRegime.UNKNOWN

        # 解析风控模式
        risk_mode_str = analysis.get('suggested_risk_mode')
        suggested_risk_mode = None
        if risk_mode_str:
            try:
                suggested_risk_mode = RiskMode(risk_mode_str)
            except ValueError:
                pass

        # 构建决策对象
        decision = PolicyDecision(
            regime=regime,
            regime_confidence=analysis.get('regime_confidence', 0.0),
            suggested_risk_mode=suggested_risk_mode,
            suggested_stop_loss_pct=analysis.get('suggested_stop_loss_pct'),
            suggested_take_profit_pct=analysis.get('suggested_take_profit_pct'),
            suggested_trailing_stop_pct=analysis.get('suggested_trailing_stop_pct'),
            enable_trailing_stop=analysis.get('enable_trailing_stop'),
            suggested_position_multiplier=analysis.get('suggested_position_multiplier'),
            strategies_to_enable=analysis.get('strategies_to_enable', []),
            strategies_to_disable=analysis.get('strategies_to_disable', []),
            confidence=analysis.get('confidence', 0.0),
            reason=analysis.get('reason', ''),
            ttl_minutes=analysis.get('ttl_minutes', 30),
            raw_claude_response=analysis
        )

        return decision


# ==================== 全局实例 ====================

_claude_policy_analyzer: Optional[ClaudePolicyAnalyzer] = None


def get_claude_policy_analyzer() -> ClaudePolicyAnalyzer:
    """获取 Claude Policy 分析器单例"""
    global _claude_policy_analyzer
    if _claude_policy_analyzer is None:
        _claude_policy_analyzer = ClaudePolicyAnalyzer()
    return _claude_policy_analyzer
