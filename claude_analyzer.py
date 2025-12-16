"""
Claude AI 分析器
集成 Claude API 进行智能交易决策分析
"""
import json
from typing import Dict, Optional, Tuple
from datetime import datetime
import pandas as pd

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("警告: anthropic 库未安装，Claude 分析功能将被禁用")
    print("安装命令: pip install anthropic")

import config
from logger_utils import get_logger
from strategies import Signal, TradeSignal

logger = get_logger("claude_analyzer")


class ClaudeAnalyzer:
    """Claude AI 交易分析器"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Claude 分析器

        Args:
            api_key: Claude API Key，如果不提供则从 config 读取
        """
        self.api_key = api_key or getattr(config, 'CLAUDE_API_KEY', None)
        self.base_url = getattr(config, 'CLAUDE_BASE_URL', None)
        self.enabled = getattr(config, 'ENABLE_CLAUDE_ANALYSIS', False)
        self.model = getattr(config, 'CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')

        if not ANTHROPIC_AVAILABLE:
            self.enabled = False
            logger.warning("anthropic 库未安装，Claude 分析已禁用")
            return

        if not self.api_key:
            self.enabled = False
            logger.warning("未配置 CLAUDE_API_KEY，Claude 分析已禁用")
            return

        if self.enabled:
            try:
                # 如果配置了自定义base_url，使用自定义端点
                if self.base_url:
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key,
                        base_url=self.base_url
                    )
                    logger.info(f"Claude 分析器初始化成功 (模型: {self.model}, 自定义端点: {self.base_url})")
                else:
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                    logger.info(f"Claude 分析器初始化成功 (模型: {self.model})")
            except Exception as e:
                self.enabled = False
                logger.error(f"Claude 客户端初始化失败: {e}")

    def _format_market_data(
        self,
        df: pd.DataFrame,
        current_price: float,
        signal: TradeSignal,
        indicators: Dict
    ) -> str:
        """
        格式化市场数据为 Claude 可理解的文本

        Args:
            df: K线数据
            current_price: 当前价格
            signal: 策略信号
            indicators: 技术指标

        Returns:
            格式化的市场数据文本
        """
        # 计算价格变化
        price_change_24h = ((current_price - df['close'].iloc[-96]) / df['close'].iloc[-96] * 100) if len(df) >= 96 else 0
        price_change_4h = ((current_price - df['close'].iloc[-16]) / df['close'].iloc[-16] * 100) if len(df) >= 16 else 0
        price_change_1h = ((current_price - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100) if len(df) >= 4 else 0

        # 获取技术指标
        rsi = indicators.get('rsi', 'N/A')
        macd = indicators.get('macd', 'N/A')
        macd_signal = indicators.get('macd_signal', 'N/A')
        macd_histogram = indicators.get('macd_histogram', 'N/A')
        ema_short = indicators.get('ema_short', 'N/A')
        ema_long = indicators.get('ema_long', 'N/A')
        bb_upper = indicators.get('bb_upper', 'N/A')
        bb_middle = indicators.get('bb_middle', 'N/A')
        bb_lower = indicators.get('bb_lower', 'N/A')
        bb_percent = indicators.get('bb_percent_b', 'N/A')
        adx = indicators.get('adx', 'N/A')
        plus_di = indicators.get('plus_di', 'N/A')
        minus_di = indicators.get('minus_di', 'N/A')
        volume_ratio = indicators.get('volume_ratio', 'N/A')
        trend_direction = indicators.get('trend_direction', 'N/A')
        trend_strength = indicators.get('trend_strength', 'N/A')

        # 构建市场数据文本
        market_data = f"""
## 市场数据 (时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 价格信息
- 当前价格: {current_price:.2f} USDT
- 24小时变化: {price_change_24h:+.2f}%
- 4小时变化: {price_change_4h:+.2f}%
- 1小时变化: {price_change_1h:+.2f}%

### 技术指标
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
- 价格位置: {'上轨附近' if bb_percent > 0.8 else '下轨附近' if bb_percent < 0.2 else '中轨附近'}

**趋势强度:**
- ADX: {adx} ({'强趋势' if adx > 25 else '弱趋势/震荡'})
- +DI: {plus_di}
- -DI: {minus_di}
- DI方向: {'看涨' if plus_di > minus_di else '看跌'} (+DI {'>' if plus_di > minus_di else '<'} -DI)

**成交量:**
- 量比: {volume_ratio} ({'放量' if volume_ratio > 1.5 else '缩量' if volume_ratio < 0.8 else '正常'})

**综合趋势:**
- 趋势方向: {trend_direction} (1=上涨, -1=下跌, 0=震荡)
- 趋势强度: {trend_strength}

### 策略信号
- 信号类型: {signal.signal.value}
- 策略名称: {signal.strategy}
- 信号原因: {signal.reason}
- 信号强度: {signal.strength:.2f}
- 置信度: {signal.confidence:.2f}
"""
        return market_data

    def _build_analysis_prompt(
        self,
        market_data: str,
        signal: TradeSignal,
        position_info: Optional[Dict] = None
    ) -> str:
        """
        构建分析提示词（结构化打分版）

        Args:
            market_data: 格式化的市场数据
            signal: 策略信号
            position_info: 当前持仓信息（如果有）

        Returns:
            完整的提示词
        """
        position_text = ""
        if position_info:
            position_text = f"""
### 当前持仓
- 方向: {position_info.get('side', 'N/A')}
- 数量: {position_info.get('amount', 'N/A')}
- 入场价: {position_info.get('entry_price', 'N/A')}
- 未实现盈亏: {position_info.get('unrealized_pnl', 'N/A')} USDT
"""

        prompt = f"""你是一个专业的量化交易分析师，请根据以下市场数据和策略信号，给出**结构化的交易决策评分**。

{market_data}
{position_text}

## 分析要求

请从以下维度进行**量化评分**：

1. **市场状态识别** (regime)
   - trend: 趋势市（ADX>25, 方向明确）
   - mean_revert: 均值回归市（震荡，ADX<20）
   - chop: 混乱市（方向不明，高波动）

2. **信号质量评分** (signal_quality: 0-1)
   - 技术指标一致性
   - 是否顺势
   - 成交量配合度

3. **风险标记** (risk_flags)
   - counter_trend: 逆势交易
   - extreme_rsi: RSI极端值
   - high_volatility: 高波动
   - weak_volume: 成交量不足
   - conflicting_signals: 指标冲突

4. **执行建议**
   - execute: true/false
   - confidence: 0-1（综合置信度）
   - suggested_sl_pct: 建议止损百分比（可选）
   - suggested_tp_pct: 建议止盈百分比（可选）

## 关键判断规则

**逆势交易检测:**
- EMA9 < EMA21 且 MACD < 0 且 ADX > 25 → 强下跌，做多=counter_trend
- EMA9 > EMA21 且 MACD > 0 且 ADX > 25 → 强上涨，做空=counter_trend

**极端RSI检测:**
- RSI < 20 或 RSI > 80 → extreme_rsi

**高波动检测:**
- 布林带宽度 > 4% 或 量比 > 2.0 → high_volatility

**成交量检测:**
- 量比 < 0.8 → weak_volume

## 输出格式（严格JSON）

```json
{{
  "execute": true,
  "confidence": 0.75,
  "regime": "trend",
  "signal_quality": 0.8,
  "risk_flags": ["counter_trend", "extreme_rsi"],
  "risk_level": "中",
  "reason": "简短理由（1-2句）",
  "suggested_sl_pct": 0.02,
  "suggested_tp_pct": 0.04
}}
```

**重要**: 只输出JSON，不要有任何其他文字。
"""
        return prompt

    def analyze_signal(
        self,
        df: pd.DataFrame,
        current_price: float,
        signal: TradeSignal,
        indicators: Dict,
        position_info: Optional[Dict] = None
    ) -> Tuple[bool, str, Dict]:
        """
        使用 Claude 分析交易信号

        Args:
            df: K线数据
            current_price: 当前价格
            signal: 策略信号
            indicators: 技术指标
            position_info: 当前持仓信息

        Returns:
            (是否执行, 原因, 分析详情)
        """
        if not self.enabled:
            # Claude 未启用，直接通过
            return True, "Claude 分析未启用", {}

        # 只分析开仓信号，平仓信号直接通过
        if signal.signal not in [Signal.LONG, Signal.SHORT]:
            return True, "非开仓信号，直接通过", {}

        try:
            # 格式化市场数据
            market_data = self._format_market_data(df, current_price, signal, indicators)

            # 构建提示词
            prompt = self._build_analysis_prompt(market_data, signal, position_info)

            # 调用 Claude API
            logger.info("正在调用 Claude API 进行分析...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
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
                return True, "Claude 响应解析失败，默认通过", {}

            # 判断是否执行
            decision = analysis.get('decision', 'EXECUTE')
            confidence = analysis.get('confidence', 0.5)
            reason = analysis.get('reason', '无原因')
            trend = analysis.get('trend', '未知')
            risk_level = analysis.get('risk_level', '中')
            warnings = analysis.get('warnings', [])

            # 记录分析结果
            logger.info(f"Claude 分析结果:")
            logger.info(f"  决策: {decision}")
            logger.info(f"  置信度: {confidence:.2f}")
            logger.info(f"  趋势: {trend}")
            logger.info(f"  风险: {risk_level}")
            logger.info(f"  原因: {reason}")
            if warnings:
                logger.warning(f"  警告: {', '.join(warnings)}")

            # 决策逻辑
            should_execute = decision == 'EXECUTE'

            analysis_details = {
                'decision': decision,
                'confidence': confidence,
                'trend': trend,
                'risk_level': risk_level,
                'reason': reason,
                'warnings': warnings,
                'raw_response': response_text
            }

            return should_execute, reason, analysis_details

        except Exception as e:
            logger.error(f"Claude 分析失败: {e}")
            # 失败时默认通过，避免阻塞交易
            return True, f"Claude 分析异常: {str(e)}", {}

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

    def get_market_analysis(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict
    ) -> Optional[Dict]:
        """
        获取市场分析（不涉及具体交易信号）

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标

        Returns:
            市场分析结果
        """
        if not self.enabled:
            return None

        try:
            market_data = self._format_market_data(
                df, current_price,
                TradeSignal(Signal.HOLD, "analysis", "市场分析"),
                indicators
            )

            prompt = f"""请分析当前市场状态：

{market_data}

请给出：
1. 当前趋势判断
2. 市场风险评估
3. 适合的交易策略类型

以 JSON 格式输出：
```json
{{
  "trend": "趋势描述",
  "risk": "风险等级",
  "suitable_strategies": ["策略1", "策略2"],
  "summary": "简短总结"
}}
```
"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            return self._parse_response(response.content[0].text)

        except Exception as e:
            logger.error(f"市场分析失败: {e}")
            return None


# 全局实例
_claude_analyzer: Optional[ClaudeAnalyzer] = None


def get_claude_analyzer() -> ClaudeAnalyzer:
    """获取 Claude 分析器单例"""
    global _claude_analyzer
    if _claude_analyzer is None:
        _claude_analyzer = ClaudeAnalyzer()
    return _claude_analyzer
