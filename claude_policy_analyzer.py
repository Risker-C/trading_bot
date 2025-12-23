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
                        base_url=self.base_url,
                        default_headers={
                            "User-Agent": "claude-code-cli",
                            "X-Claude-Code": "1"
                        }
                    )
                    logger.info(f"Claude Policy 分析器初始化成功 (自定义端点: {self.base_url})")
                else:
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key,
                        default_headers={
                            "User-Agent": "claude-code-cli",
                            "X-Claude-Code": "1"
                        }
                    )
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
## 技术分析系统状态 - 教育研究用途 (时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

**免责声明:** 以下数据来自模拟回测系统，仅用于技术分析研究和教育目的。

### A. 历史回测数据
- 样本数量: {context.recent_trades_count}
- 成功率: {context.win_rate:.1%}
- 最近表现: {context.recent_pnl:+.2f} USDT
- 连续负向: {context.consecutive_losses} 次
- 连续正向: {context.consecutive_wins} 次
- 平均正向结果: {context.avg_win:.2f} USDT
- 平均负向结果: {context.avg_loss:.2f} USDT
- 当前分析模式: {context.current_risk_mode.value}

### B. 观察仓位状态（模拟）
"""
        if context.has_position:
            context_text += f"""- 观察方向: {context.position_side.upper()}
- 观察规模: {context.position_amount:.6f}
- 参考价格: {context.entry_price:.2f} USDT
- 当前价格: {context.current_price:.2f} USDT
- 价格变化: {context.unrealized_pnl:+.2f} USDT ({context.unrealized_pnl_pct:+.2f}%)
- 观察时长: {context.holding_time_minutes:.0f} 分钟
- 风险阈值: {context.current_stop_loss:.2f} USDT
- 目标阈值: {context.current_take_profit:.2f} USDT
"""
        else:
            context_text += "- 当前无观察仓位\n"

        context_text += f"""
### C. 市场技术指标分析
- 当前价格: {current_price:.2f} USDT
- 24小时变化: {price_change_24h:+.2f}%
- 4小时变化: {price_change_4h:+.2f}%
- 1小时变化: {price_change_1h:+.2f}%

**动量指标:**
- RSI(14): {rsi}
- MACD: {macd}
- MACD Signal: {macd_signal}
- MACD Histogram: {macd_histogram}
- EMA(9): {ema_short}
- EMA(21): {ema_long}
- EMA关系: {'上行' if ema_short > ema_long else '下行'} (EMA9 {'>' if ema_short > ema_long else '<'} EMA21)

**波动性指标:**
- 布林带上轨: {bb_upper}
- 布林带中轨: {bb_middle}
- 布林带下轨: {bb_lower}
- 布林带位置: {bb_percent} (0=下轨, 1=上轨)
- ATR: {atr}

**趋势强度指标:**
- ADX: {adx} ({'强趋势' if adx > 25 else '弱趋势/震荡'})
- +DI: {plus_di}
- -DI: {minus_di}
- DI关系: {'正向' if plus_di > minus_di else '负向'} (+DI {'>' if plus_di > minus_di else '<'} -DI)

**成交量分析:**
- 量比: {volume_ratio} ({'放量' if volume_ratio > 1.5 else '缩量' if volume_ratio < 0.8 else '正常'})

**市场状态识别:**
- 状态类型: {context.market_regime.value}
- 方向指标: {context.trend_direction} (1=正向, -1=负向, 0=中性)
- 波动率: {context.volatility:.2%}

### D. 回测系统统计
- 今日表现: {context.daily_pnl:+.2f} USDT
- 今日样本数: {context.daily_trades}
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
        prompt = f"""**重要声明：本系统仅用于技术分析教育和回测研究，不提供任何投资建议。所有输出仅为技术指标的客观分析，需由用户自行判断和决策。**

你是一个技术指标分析系统，用于教育目的的市场数据分析。你的任务是客观分析技术指标数据，识别市场状态模式，输出技术参数的量化分析结果。

{context_text}

## 分析任务

请从以下3个维度进行客观的技术指标分析：

### 1️⃣ 市场状态模式识别

基于技术指标识别当前市场状态模式：

- **trend**: 趋势性模式（ADX > 25，方向明确，EMA排列清晰）
  - 技术特征：单向运动明显
  - 指标特点：趋势指标数值较高

- **mean_revert**: 区间震荡模式（ADX < 20，价格在均值附近波动）
  - 技术特征：价格在区间内波动
  - 指标特点：均值回归特征明显

- **chop**: 混乱模式（方向不明，高波动，指标冲突）
  - 技术特征：方向不确定
  - 指标特点：指标信号质量低

### 2️⃣ 技术参数量化分析

基于市场状态模式，分析以下技术参数的量化值（仅供参考）：

**风险控制参数分析:**
- suggested_stop_loss_pct: 技术分析得出的风险控制参数值（0.005-0.05）
- suggested_take_profit_pct: 技术分析得出的目标参数值（0.01-0.10）
- suggested_trailing_stop_pct: 技术分析得出的动态调整参数值（0.005-0.03）
- enable_trailing_stop: 技术分析是否显示适合动态调整（true/false）

**规模参数分析:**
- suggested_position_multiplier: 技术分析得出的规模系数（0.3-2.0）
  - 1.0 = 标准值
  - 0.5 = 保守值（高不确定性）
  - 1.5 = 积极值（高确定性）

**模式分析:**
- suggested_risk_mode: 技术分析显示的模式类型
  - "normal": 标准模式
  - "defensive": 保守模式
  - "recovery": 恢复模式
  - "aggressive": 积极模式

### 3️⃣ 技术指标综合分析

**历史数据分析:**

1. **连续模式分析:**
   - 连续负向 >= 3次 → 技术分析显示保守模式特征
   - 连续负向 >= 5次 → 技术分析显示需要重新评估

2. **当前状态分析:**
   - 未实现变化 > 1% → 技术分析显示收紧特征
   - 未实现变化 > 2% → 技术分析显示保护特征
   - 持续时间 > 4小时 → 技术分析显示调整特征

3. **市场环境分析:**
   - 震荡环境（ADX < 20）→ 技术分析显示区间特征
   - 趋势环境（ADX > 35）→ 技术分析显示趋势特征
   - 高波动环境（量比 > 2.0）→ 技术分析显示降低规模特征

4. **风险指标分析:**
   - 当日累计变化 > 100 USDT → 技术分析显示保守模式
   - 历史成功率 < 40% → 技术分析显示降低规模
   - 成交量萎缩（量比 < 0.5）→ 技术分析显示降低参与度

## 输出格式（JSON）

请以JSON格式输出技术指标分析结果：

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
  "reason": "技术分析依据（2-3句话，说明指标分析结果）",
  "ttl_minutes": 30
}}
```

**输出说明:**
1. 只输出JSON格式，不要有其他文字
2. 所有百分比使用小数形式（如 0.02 表示 2%）
3. confidence 表示分析的置信度（0-1）
4. ttl_minutes 表示分析结果的有效期（分钟）
5. 如果某个参数无需调整，设置为 null
6. 所有输出仅为技术指标的客观分析

**当前参考值:**
- 风险控制参数: 2%
- 目标参数: 4%
- 动态调整参数: 1.5%
- 规模系数: 1.0x
- 当前模式: {context.current_risk_mode.value}

**再次声明：本输出仅为技术指标的客观分析结果，用于教育和研究目的，不构成任何投资建议。用户需自行判断和决策。**
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
