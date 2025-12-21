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
                        base_url=self.base_url,
                        default_headers={
                            "User-Agent": "claude-code-cli",
                            "X-Claude-Code": "1"
                        }
                    )
                    logger.info(f"Claude 分析器初始化成功 (模型: {self.model}, 自定义端点: {self.base_url})")
                else:
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key,
                        default_headers={
                            "User-Agent": "claude-code-cli",
                            "X-Claude-Code": "1"
                        }
                    )
                    logger.info(f"Claude 分析器初始化成功 (模型: {self.model})")
            except Exception as e:
                self.enabled = False
                logger.error(f"Claude 客户端初始化失败: {e}")

    def _calculate_support_resistance(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        计算支撑位和阻力位

        Args:
            df: K线数据
            lookback: 回看周期

        Returns:
            包含支撑位和阻力位的字典
        """
        if len(df) < lookback:
            return {'support': None, 'resistance': None, 'levels': []}

        recent_df = df.tail(lookback)

        # 找出局部高点和低点
        highs = []
        lows = []

        for i in range(1, len(recent_df) - 1):
            # 局部高点：比前后都高
            if recent_df['high'].iloc[i] > recent_df['high'].iloc[i-1] and \
               recent_df['high'].iloc[i] > recent_df['high'].iloc[i+1]:
                highs.append(recent_df['high'].iloc[i])

            # 局部低点：比前后都低
            if recent_df['low'].iloc[i] < recent_df['low'].iloc[i-1] and \
               recent_df['low'].iloc[i] < recent_df['low'].iloc[i+1]:
                lows.append(recent_df['low'].iloc[i])

        # 计算关键支撑位和阻力位
        current_price = df['close'].iloc[-1]

        # 支撑位：当前价格下方的最高低点
        support_levels = [low for low in lows if low < current_price]
        support = max(support_levels) if support_levels else min(lows) if lows else None

        # 阻力位：当前价格上方的最低高点
        resistance_levels = [high for high in highs if high > current_price]
        resistance = min(resistance_levels) if resistance_levels else max(highs) if highs else None

        return {
            'support': support,
            'resistance': resistance,
            'support_distance': ((current_price - support) / current_price * 100) if support else None,
            'resistance_distance': ((resistance - current_price) / current_price * 100) if resistance else None,
            'all_supports': sorted(support_levels, reverse=True)[:3] if support_levels else [],
            'all_resistances': sorted(resistance_levels)[:3] if resistance_levels else []
        }

    def _analyze_volume_detail(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        详细分析成交量

        Args:
            df: K线数据
            lookback: 回看周期

        Returns:
            成交量分析结果
        """
        if len(df) < lookback:
            return {}

        recent_df = df.tail(lookback)
        current_volume = df['volume'].iloc[-1]
        avg_volume = recent_df['volume'].mean()

        # 成交量趋势（最近5根K线 vs 之前15根）
        recent_5_avg = df['volume'].tail(5).mean()
        previous_15_avg = df['volume'].tail(20).head(15).mean()
        volume_trend = "上升" if recent_5_avg > previous_15_avg * 1.1 else "下降" if recent_5_avg < previous_15_avg * 0.9 else "平稳"

        # 成交量分布
        volume_std = recent_df['volume'].std()
        volume_cv = volume_std / avg_volume if avg_volume > 0 else 0  # 变异系数

        # 检测成交量异常
        volume_spikes = []
        for i in range(len(recent_df)):
            if recent_df['volume'].iloc[i] > avg_volume * 2:
                volume_spikes.append({
                    'index': i,
                    'volume': recent_df['volume'].iloc[i],
                    'ratio': recent_df['volume'].iloc[i] / avg_volume
                })

        # 价量关系
        price_changes = recent_df['close'].pct_change()
        volume_changes = recent_df['volume'].pct_change()
        price_volume_corr = price_changes.corr(volume_changes) if len(price_changes) > 1 else 0

        return {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 1,
            'volume_trend': volume_trend,
            'volume_trend_ratio': recent_5_avg / previous_15_avg if previous_15_avg > 0 else 1,
            'volume_volatility': volume_cv,
            'spike_count': len(volume_spikes),
            'price_volume_correlation': price_volume_corr,
            'volume_quality': "强" if current_volume > avg_volume * 1.5 and price_volume_corr > 0.3 else "弱" if current_volume < avg_volume * 0.8 else "中等"
        }

    def _calculate_market_sentiment(self, df: pd.DataFrame, lookback: int = 10) -> Dict:
        """
        计算市场情绪指标

        Args:
            df: K线数据
            lookback: 回看周期

        Returns:
            市场情绪分析结果
        """
        if len(df) < lookback:
            return {}

        recent_df = df.tail(lookback)

        # 多空力量对比（阳线vs阴线）
        bullish_candles = sum(recent_df['close'] > recent_df['open'])
        bearish_candles = sum(recent_df['close'] < recent_df['open'])

        # 实体大小（反映力度）
        bullish_body_sum = sum((recent_df['close'] - recent_df['open'])[recent_df['close'] > recent_df['open']])
        bearish_body_sum = sum((recent_df['open'] - recent_df['close'])[recent_df['close'] < recent_df['open']])

        # 上下影线比例（反映犹豫程度）
        upper_shadow = (recent_df['high'] - recent_df[['open', 'close']].max(axis=1)).mean()
        lower_shadow = (recent_df[['open', 'close']].min(axis=1) - recent_df['low']).mean()
        body_size = abs(recent_df['close'] - recent_df['open']).mean()

        # 动量指标
        momentum_3 = (df['close'].iloc[-1] - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100 if len(df) >= 4 else 0
        momentum_7 = (df['close'].iloc[-1] - df['close'].iloc[-8]) / df['close'].iloc[-8] * 100 if len(df) >= 8 else 0

        # 综合情绪评分
        sentiment_score = (bullish_candles - bearish_candles) / lookback
        if bullish_body_sum + bearish_body_sum > 0:
            sentiment_score = sentiment_score * 0.5 + (bullish_body_sum - bearish_body_sum) / (bullish_body_sum + bearish_body_sum) * 0.5

        sentiment = "强烈看涨" if sentiment_score > 0.4 else "看涨" if sentiment_score > 0.2 else "中性" if sentiment_score > -0.2 else "看跌" if sentiment_score > -0.4 else "强烈看跌"

        return {
            'bullish_candles': bullish_candles,
            'bearish_candles': bearish_candles,
            'bullish_strength': bullish_body_sum,
            'bearish_strength': bearish_body_sum,
            'upper_shadow_ratio': upper_shadow / body_size if body_size > 0 else 0,
            'lower_shadow_ratio': lower_shadow / body_size if body_size > 0 else 0,
            'momentum_3bar': momentum_3,
            'momentum_7bar': momentum_7,
            'sentiment_score': sentiment_score,
            'sentiment': sentiment
        }

    def _analyze_market_structure(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        分析市场结构

        Args:
            df: K线数据
            lookback: 回看周期

        Returns:
            市场结构分析结果
        """
        if len(df) < lookback:
            return {}

        recent_df = df.tail(lookback)

        # 识别高点和低点序列
        highs = recent_df['high'].values
        lows = recent_df['low'].values

        # 检测更高高点和更高低点（上升趋势）
        higher_highs = 0
        higher_lows = 0
        for i in range(5, len(highs)):
            if highs[i] > max(highs[i-5:i]):
                higher_highs += 1
            if lows[i] > max(lows[i-5:i]):
                higher_lows += 1

        # 检测更低高点和更低低点（下降趋势）
        lower_highs = 0
        lower_lows = 0
        for i in range(5, len(highs)):
            if highs[i] < min(highs[i-5:i]):
                lower_highs += 1
            if lows[i] < min(lows[i-5:i]):
                lower_lows += 1

        # 判断市场结构
        if higher_highs >= 2 and higher_lows >= 2:
            structure = "上升趋势结构"
            structure_strength = (higher_highs + higher_lows) / (lookback - 5)
        elif lower_highs >= 2 and lower_lows >= 2:
            structure = "下降趋势结构"
            structure_strength = (lower_highs + lower_lows) / (lookback - 5)
        else:
            structure = "震荡结构"
            structure_strength = 0.5

        # 波动范围
        price_range = (recent_df['high'].max() - recent_df['low'].min()) / recent_df['close'].iloc[-1] * 100

        return {
            'structure': structure,
            'structure_strength': structure_strength,
            'higher_highs': higher_highs,
            'higher_lows': higher_lows,
            'lower_highs': lower_highs,
            'lower_lows': lower_lows,
            'price_range_pct': price_range
        }

    def _format_market_data(
        self,
        df: pd.DataFrame,
        current_price: float,
        signal: TradeSignal,
        indicators: Dict
    ) -> str:
        """
        格式化市场数据为 Claude 可理解的文本（增强版）

        Args:
            df: K线数据
            current_price: 当前价格
            signal: 策略信号
            indicators: 技术指标

        Returns:
            格式化的市场数据文本
        """
        # 计算价格变化（多时间周期）
        price_change_24h = ((current_price - df['close'].iloc[-96]) / df['close'].iloc[-96] * 100) if len(df) >= 96 else 0
        price_change_12h = ((current_price - df['close'].iloc[-48]) / df['close'].iloc[-48] * 100) if len(df) >= 48 else 0
        price_change_4h = ((current_price - df['close'].iloc[-16]) / df['close'].iloc[-16] * 100) if len(df) >= 16 else 0
        price_change_1h = ((current_price - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100) if len(df) >= 4 else 0
        price_change_15m = ((current_price - df['close'].iloc[-1]) / df['close'].iloc[-1] * 100) if len(df) >= 1 else 0

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

        # 计算增强指标
        sr_levels = self._calculate_support_resistance(df)
        volume_detail = self._analyze_volume_detail(df)
        sentiment = self._calculate_market_sentiment(df)
        structure = self._analyze_market_structure(df)

        # 构建市场数据文本
        market_data = f"""
## 市场深度分析报告 (BTCUSDT)
**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**当前价格**: {current_price:.2f} USDT

---

### 一、价格走势分析

**多时间周期价格变化:**
- 24小时: {price_change_24h:+.2f}% {'📈' if price_change_24h > 0 else '📉'}
- 12小时: {price_change_12h:+.2f}% {'📈' if price_change_12h > 0 else '📉'}
- 4小时: {price_change_4h:+.2f}% {'📈' if price_change_4h > 0 else '📉'}
- 1小时: {price_change_1h:+.2f}% {'📈' if price_change_1h > 0 else '📉'}
- 15分钟: {price_change_15m:+.2f}% {'📈' if price_change_15m > 0 else '📉'}

**趋势判断:**
- 短期趋势(1-4h): {'上涨' if price_change_1h > 0 and price_change_4h > 0 else '下跌' if price_change_1h < 0 and price_change_4h < 0 else '震荡'}
- 中期趋势(12-24h): {'上涨' if price_change_12h > 0 and price_change_24h > 0 else '下跌' if price_change_12h < 0 and price_change_24h < 0 else '震荡'}

---

### 二、关键价格位（支撑/阻力）

**当前支撑位:**
- 主要支撑: {sr_levels.get('support', 'N/A'):.2f} USDT (距离: {sr_levels.get('support_distance', 0):.2f}%)
- 次要支撑: {', '.join([f'{s:.2f}' for s in sr_levels.get('all_supports', [])[:2]])}

**当前阻力位:**
- 主要阻力: {sr_levels.get('resistance', 'N/A'):.2f} USDT (距离: {sr_levels.get('resistance_distance', 0):.2f}%)
- 次要阻力: {', '.join([f'{r:.2f}' for r in sr_levels.get('all_resistances', [])[:2]])}

**价格位置分析:**
- 距离支撑位: {sr_levels.get('support_distance', 0):.2f}% {'⚠️ 接近支撑' if sr_levels.get('support_distance', 100) < 1 else ''}
- 距离阻力位: {sr_levels.get('resistance_distance', 0):.2f}% {'⚠️ 接近阻力' if sr_levels.get('resistance_distance', 100) < 1 else ''}

---

### 三、成交量深度分析

**成交量统计:**
- 当前成交量: {volume_detail.get('current_volume', 0):.2f}
- 平均成交量(20周期): {volume_detail.get('avg_volume', 0):.2f}
- 量比: {volume_detail.get('volume_ratio', 1):.2f}x {'🔥 放量' if volume_detail.get('volume_ratio', 1) > 1.5 else '❄️ 缩量' if volume_detail.get('volume_ratio', 1) < 0.8 else ''}

**成交量趋势:**
- 趋势方向: {volume_detail.get('volume_trend', 'N/A')}
- 趋势强度: {volume_detail.get('volume_trend_ratio', 1):.2f}x
- 成交量波动率: {volume_detail.get('volume_volatility', 0):.2f}
- 异常放量次数: {volume_detail.get('spike_count', 0)}次

**价量关系:**
- 价量相关性: {volume_detail.get('price_volume_correlation', 0):.2f} {'✅ 价量配合' if abs(volume_detail.get('price_volume_correlation', 0)) > 0.3 else '⚠️ 价量背离'}
- 成交量质量: {volume_detail.get('volume_quality', 'N/A')}

---

### 四、市场情绪分析

**多空力量对比:**
- 看涨K线: {sentiment.get('bullish_candles', 0)}根
- 看跌K线: {sentiment.get('bearish_candles', 0)}根
- 多头力量: {sentiment.get('bullish_strength', 0):.2f}
- 空头力量: {sentiment.get('bearish_strength', 0):.2f}

**K线形态特征:**
- 上影线比例: {sentiment.get('upper_shadow_ratio', 0):.2f} {'⚠️ 上方压力大' if sentiment.get('upper_shadow_ratio', 0) > 1 else ''}
- 下影线比例: {sentiment.get('lower_shadow_ratio', 0):.2f} {'✅ 下方支撑强' if sentiment.get('lower_shadow_ratio', 0) > 1 else ''}

**动量指标:**
- 3根K线动量: {sentiment.get('momentum_3bar', 0):+.2f}%
- 7根K线动量: {sentiment.get('momentum_7bar', 0):+.2f}%

**综合情绪:**
- 情绪评分: {sentiment.get('sentiment_score', 0):+.2f}
- 市场情绪: {sentiment.get('sentiment', 'N/A')} {'🔥' if '看涨' in sentiment.get('sentiment', '') else '❄️' if '看跌' in sentiment.get('sentiment', '') else ''}

---

### 五、市场结构分析

**趋势结构:**
- 市场结构: {structure.get('structure', 'N/A')}
- 结构强度: {structure.get('structure_strength', 0):.2f}

**结构特征:**
- 更高高点: {structure.get('higher_highs', 0)}次
- 更高低点: {structure.get('higher_lows', 0)}次
- 更低高点: {structure.get('lower_highs', 0)}次
- 更低低点: {structure.get('lower_lows', 0)}次

**波动范围:**
- 近期波动幅度: {structure.get('price_range_pct', 0):.2f}%

---

### 六、技术指标详情

**趋势指标:**
- RSI(14): {rsi} {'🔥 超买' if isinstance(rsi, (int, float)) and rsi > 70 else '❄️ 超卖' if isinstance(rsi, (int, float)) and rsi < 30 else ''}
- MACD: {macd}
- MACD Signal: {macd_signal}
- MACD柱状图: {macd_histogram} {'✅ 金叉' if isinstance(macd_histogram, (int, float)) and macd_histogram > 0 else '❌ 死叉'}
- EMA(9): {ema_short}
- EMA(21): {ema_long}
- EMA趋势: {'看涨' if ema_short > ema_long else '看跌'} (EMA9 {'>' if ema_short > ema_long else '<'} EMA21)

**波动指标:**
- 布林带上轨: {bb_upper}
- 布林带中轨: {bb_middle}
- 布林带下轨: {bb_lower}
- 布林带位置: {bb_percent} {'⚠️ 上轨附近' if isinstance(bb_percent, (int, float)) and bb_percent > 0.8 else '⚠️ 下轨附近' if isinstance(bb_percent, (int, float)) and bb_percent < 0.2 else '中轨区域'}

**趋势强度:**
- ADX: {adx} {'💪 强趋势' if isinstance(adx, (int, float)) and adx > 25 else '😴 弱趋势/震荡'}
- +DI: {plus_di}
- -DI: {minus_di}
- DI方向: {'看涨' if plus_di > minus_di else '看跌'} (+DI {'>' if plus_di > minus_di else '<'} -DI)

**综合趋势:**
- 趋势方向: {trend_direction} (1=上涨, -1=下跌, 0=震荡)
- 趋势强度: {trend_strength}

---

### 七、策略信号信息

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
        构建分析提示词（资深分析师版）

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

        prompt = f"""你是一位拥有10年以上经验的资深加密货币交易分析师，专注于BTCUSDT市场分析。请基于以下完整的市场数据，提供**深度专业的交易决策分析**。

{market_data}
{position_text}

---

## 分析任务

作为资深分析师，请从以下维度进行**全面深入的市场分析**：

### 1. 市场宏观环境评估

**请分析：**
- 当前市场处于什么阶段？（趋势启动、趋势延续、趋势衰竭、震荡整理、反转酝酿）
- 多时间周期（15分钟、1小时、4小时、24小时）的趋势是否一致？
- 市场结构是否健康？（更高高点/更高低点 vs 更低高点/更低低点）
- 当前价格在整体波动范围中的位置如何？是否接近关键支撑/阻力？

### 2. 成交量与市场参与度分析

**请深入分析：**
- 当前成交量是否支持价格走势？（价量配合 vs 价量背离）
- 成交量趋势如何？（放量 vs 缩量，是否有异常放量）
- 成交量质量如何？（强势放量 vs 弱势缩量）
- 价量相关性说明了什么？（多头主导 vs 空头主导 vs 犹豫不决）

### 3. 市场情绪与多空力量对比

**请评估：**
- 近期K线形态反映出什么市场情绪？（强烈看涨、看涨、中性、看跌、强烈看跌）
- 多空力量对比如何？（多头占优 vs 空头占优 vs 势均力敌）
- 上下影线比例说明了什么？（上方压力 vs 下方支撑）
- 短期动量（3根K线、7根K线）指向哪里？

### 4. 关键价格位与风险收益比

**请识别：**
- 当前最关键的支撑位和阻力位在哪里？
- 距离这些关键价格位有多远？（百分比和绝对值）
- 如果执行该信号，风险收益比如何？
- 是否存在明显的止损位和止盈位？

### 5. 技术指标综合研判

**请综合分析：**
- RSI是否处于极端区域？是否存在超买/超卖？
- MACD金叉/死叉的有效性如何？（是否在零轴上方/下方）
- EMA趋势是否明确？（多头排列 vs 空头排列）
- 布林带位置说明了什么？（突破上轨 vs 跌破下轨 vs 中轨震荡）
- ADX趋势强度如何？（强趋势 vs 弱趋势/震荡）
- 各指标之间是否存在冲突？

### 6. 策略信号质量评估

**请评估当前策略信号：**
- 信号类型：{signal.signal.value}
- 策略名称：{signal.strategy}
- 信号原因：{signal.reason}
- 信号强度：{signal.strength:.2f}
- 置信度：{signal.confidence:.2f}

**请判断：**
- 该信号是否顺势？（顺势 vs 逆势）
- 该信号的时机是否合适？（最佳入场点 vs 次优 vs 不佳）
- 该信号的风险等级如何？（低风险 vs 中风险 vs 高风险）

### 7. 风险因素识别

**请识别所有潜在风险：**
- 是否存在逆势交易风险？
- 是否存在极端RSI风险？
- 是否存在高波动风险？
- 是否存在成交量不足风险？
- 是否存在技术指标冲突风险？
- 是否存在接近关键价格位的风险？
- 是否存在其他需要注意的风险？

### 8. 执行建议与理由

**请给出明确的执行建议：**
- 是否建议执行该交易？（EXECUTE vs REJECT）
- 综合置信度是多少？（0-1，考虑所有因素）
- 建议的止损百分比是多少？（基于支撑/阻力位和波动率）
- 建议的止盈百分比是多少？（基于风险收益比）
- 核心理由是什么？（2-3句话，说明关键决策依据）

---

## 输出格式（严格JSON）

请以以下JSON格式输出你的分析结果：

```json
{{
  "execute": true,
  "confidence": 0.75,
  "regime": "trend_continuation",
  "signal_quality": 0.8,
  "risk_flags": ["接近阻力位", "成交量略显不足"],
  "risk_level": "中",
  "reason": "市场处于健康的上升趋势延续阶段，多时间周期趋势一致，价量配合良好，技术指标多头排列，当前信号顺势且时机合适。主要风险是价格接近前期阻力位，建议适当收紧止损。",
  "market_phase": "趋势延续",
  "volume_quality": "良好",
  "sentiment": "看涨",
  "key_support": 87500.00,
  "key_resistance": 89000.00,
  "suggested_sl_pct": 0.035,
  "suggested_tp_pct": 0.06,
  "risk_reward_ratio": 1.7,
  "analyst_notes": "建议执行。市场结构健康，多头力量占优，成交量支持价格上涨。止损设在关键支撑位下方，止盈目标为前期阻力位。"
}}
```

**字段说明：**
- `execute`: 是否执行（true/false）
- `confidence`: 综合置信度（0-1）
- `regime`: 市场状态（trend_start/trend_continuation/trend_exhaustion/range_bound/reversal_setup）
- `signal_quality`: 信号质量评分（0-1）
- `risk_flags`: 风险标记列表（中文描述）
- `risk_level`: 风险等级（低/中/高）
- `reason`: 核心决策理由（2-3句话）
- `market_phase`: 市场阶段（中文描述）
- `volume_quality`: 成交量质量（优秀/良好/一般/较差）
- `sentiment`: 市场情绪（强烈看涨/看涨/中性/看跌/强烈看跌）
- `key_support`: 关键支撑位（数值）
- `key_resistance`: 关键阻力位（数值）
- `suggested_sl_pct`: 建议止损百分比（小数）
- `suggested_tp_pct`: 建议止盈百分比（小数）
- `risk_reward_ratio`: 风险收益比（数值）
- `analyst_notes`: 分析师备注（简短总结）

**重要提示：**
1. 只输出JSON，不要有任何其他文字
2. 所有分析必须基于提供的市场数据
3. 理由和备注要具体、专业、有说服力
4. 风险标记要全面、准确
5. 数值建议要合理、可执行
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
            execute = analysis.get('execute', True)
            confidence = analysis.get('confidence', 0.5)
            reason = analysis.get('reason', '无原因')
            regime = analysis.get('regime', '未知')
            signal_quality = analysis.get('signal_quality', 0.5)
            risk_level = analysis.get('risk_level', '中')
            risk_flags = analysis.get('risk_flags', [])
            market_phase = analysis.get('market_phase', '未知')
            volume_quality = analysis.get('volume_quality', '未知')
            sentiment = analysis.get('sentiment', '未知')
            key_support = analysis.get('key_support', None)
            key_resistance = analysis.get('key_resistance', None)
            suggested_sl_pct = analysis.get('suggested_sl_pct', None)
            suggested_tp_pct = analysis.get('suggested_tp_pct', None)
            risk_reward_ratio = analysis.get('risk_reward_ratio', None)
            analyst_notes = analysis.get('analyst_notes', '')

            # 记录分析结果
            logger.info(f"Claude 资深分析师分析结果:")
            logger.info(f"  执行建议: {'✅ 执行' if execute else '❌ 拒绝'}")
            logger.info(f"  综合置信度: {confidence:.2f}")
            logger.info(f"  市场状态: {regime}")
            logger.info(f"  市场阶段: {market_phase}")
            logger.info(f"  信号质量: {signal_quality:.2f}")
            logger.info(f"  市场情绪: {sentiment}")
            logger.info(f"  成交量质量: {volume_quality}")
            logger.info(f"  风险等级: {risk_level}")
            if key_support:
                logger.info(f"  关键支撑: {key_support:.2f}")
            if key_resistance:
                logger.info(f"  关键阻力: {key_resistance:.2f}")
            if suggested_sl_pct:
                logger.info(f"  建议止损: {suggested_sl_pct*100:.2f}%")
            if suggested_tp_pct:
                logger.info(f"  建议止盈: {suggested_tp_pct*100:.2f}%")
            if risk_reward_ratio:
                logger.info(f"  风险收益比: {risk_reward_ratio:.2f}")
            logger.info(f"  核心理由: {reason}")
            if risk_flags:
                logger.warning(f"  风险标记: {', '.join(risk_flags)}")
            if analyst_notes:
                logger.info(f"  分析师备注: {analyst_notes}")

            # 决策逻辑
            should_execute = execute

            analysis_details = {
                'execute': execute,
                'confidence': confidence,
                'regime': regime,
                'signal_quality': signal_quality,
                'risk_level': risk_level,
                'risk_flags': risk_flags,
                'reason': reason,
                'market_phase': market_phase,
                'volume_quality': volume_quality,
                'sentiment': sentiment,
                'key_support': key_support,
                'key_resistance': key_resistance,
                'suggested_sl_pct': suggested_sl_pct,
                'suggested_tp_pct': suggested_tp_pct,
                'risk_reward_ratio': risk_reward_ratio,
                'analyst_notes': analyst_notes,
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
