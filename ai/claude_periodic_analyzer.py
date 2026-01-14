"""
Claude AI 定时分析器
定期分析市场状态并通过飞书推送分析结果
"""
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import pandas as pd

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("警告: anthropic 库未安装，Claude 定时分析功能将被禁用")

import config
from utils.logger_utils import get_logger, notifier

logger = get_logger("claude_periodic_analyzer")


class ClaudePeriodicAnalyzer:
    """Claude AI 定时市场分析器"""

    def __init__(
        self,
        interval_minutes: int = 30,
        enabled: bool = True,
        detail_level: str = 'standard'
    ):
        """
        初始化 Claude 定时分析器

        Args:
            interval_minutes: 分析间隔（分钟）
            enabled: 是否启用
            detail_level: 分析详细程度 ('simple', 'standard', 'detailed')
        """
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.detail_level = detail_level
        # 初始化为当前时间，避免启动时立即分析
        self.last_analysis_time = datetime.now()
        self.analysis_count = 0

        # 每日报告相关状态
        self.last_daily_report_date = None  # 记录上次生成每日报告的日期

        # Claude API 配置
        self.api_key = getattr(config, 'CLAUDE_API_KEY', None)
        self.base_url = getattr(config, 'CLAUDE_BASE_URL', None)
        self.model = getattr(config, 'CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
        self.push_to_feishu = getattr(config, 'CLAUDE_PUSH_TO_FEISHU', True)
        self.timeout = getattr(config, 'CLAUDE_TIMEOUT', 30)  # 默认30秒超时

        # 分析模块配置
        self.modules = getattr(config, 'CLAUDE_ANALYSIS_MODULES', {
            'market_trend': True,
            'risk_assessment': True,
            'entry_opportunities': True,
            'position_advice': True,
            'market_sentiment': True,
        })

        if not ANTHROPIC_AVAILABLE:
            self.enabled = False
            logger.warning("anthropic 库未安装，Claude 定时分析已禁用")
            return

        if not self.api_key:
            self.enabled = False
            logger.warning("未配置 CLAUDE_API_KEY，Claude 定时分析已禁用")
            return

        if self.enabled:
            try:
                # 初始化 Claude 客户端
                if self.base_url:
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key,
                        base_url=self.base_url
                    )
                    logger.info(f"Claude 定时分析器初始化成功 (间隔: {interval_minutes}分钟, 自定义端点: {self.base_url})")
                else:
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                    logger.info(f"Claude 定时分析器初始化成功 (间隔: {interval_minutes}分钟)")
            except Exception as e:
                self.enabled = False
                logger.error(f"Claude 客户端初始化失败: {e}")

    def should_analyze(self) -> bool:
        """
        判断是否应该进行分析

        Returns:
            是否应该分析
        """
        if not self.enabled:
            return False

        if self.last_analysis_time is None:
            return True

        elapsed = datetime.now() - self.last_analysis_time
        return elapsed.total_seconds() >= self.interval_minutes * 60

    def _format_market_data(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict] = None
    ) -> str:
        """
        格式化市场数据为 Claude 可理解的文本

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 持仓信息

        Returns:
            格式化的市场数据文本
        """
        # 计算价格变化
        price_change_24h = ((current_price - df['close'].iloc[-96]) / df['close'].iloc[-96] * 100) if len(df) >= 96 else 0
        price_change_4h = ((current_price - df['close'].iloc[-16]) / df['close'].iloc[-16] * 100) if len(df) >= 16 else 0
        price_change_1h = ((current_price - df['close'].iloc[-4]) / df['close'].iloc[-4] * 100) if len(df) >= 4 else 0

        # 获取技术指标（确保获取最后一个值）
        def get_last_value(indicators, key, default='N/A'):
            """安全获取指标的最后一个值"""
            value = indicators.get(key, default)
            if hasattr(value, 'iloc'):
                # 如果是 Series，获取最后一个值
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

        # 构建市场数据文本
        market_data = f"""
## 市场数据 (时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

### 价格信息
- 交易对: {config.SYMBOL}
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
- ATR: {atr}

**趋势强度:**
- ADX: {adx} ({'强趋势' if adx > 25 else '弱趋势/震荡'})
- +DI: {plus_di}
- -DI: {minus_di}
- DI方向: {'看涨' if plus_di > minus_di else '看跌'} (+DI {'>' if plus_di > minus_di else '<'} -DI)

**成交量:**
- 量比: {volume_ratio} ({'放量' if volume_ratio > 1.5 else '缩量' if volume_ratio < 0.8 else '正常'})
"""

        # 添加持仓信息
        if position_info:
            market_data += f"""
### 当前持仓
- 方向: {position_info.get('side', 'N/A')}
- 数量: {position_info.get('amount', 'N/A')}
- 入场价: {position_info.get('entry_price', 'N/A')}
- 当前价: {current_price:.2f}
- 未实现盈亏: {position_info.get('unrealized_pnl', 'N/A')} USDT
- 盈亏比例: {position_info.get('pnl_percent', 'N/A')}%
"""
        else:
            market_data += "\n### 当前持仓\n- 无持仓\n"

        return market_data

    def _build_analysis_prompt(
        self,
        market_data: str,
        has_position: bool
    ) -> str:
        """
        构建分析提示词

        Args:
            market_data: 格式化的市场数据
            has_position: 是否有持仓

        Returns:
            完整的提示词
        """
        # 根据详细程度调整提示词
        if self.detail_level == 'simple':
            analysis_depth = "简要分析，每个维度1-2句话"
        elif self.detail_level == 'detailed':
            analysis_depth = "详细分析，包含具体数据支撑和多个场景"
        else:  # standard
            analysis_depth = "标准分析，每个维度2-3句话"

        # 根据配置的模块构建分析要求
        analysis_modules = []
        if self.modules.get('market_trend', True):
            analysis_modules.append("1. **市场趋势分析**: 当前趋势方向、强度、可持续性")
        if self.modules.get('risk_assessment', True):
            analysis_modules.append("2. **风险评估**: 当前市场风险等级、主要风险因素")
        if self.modules.get('entry_opportunities', True):
            analysis_modules.append("3. **入场机会**: 是否有好的入场点、建议的入场价位和方向")
        if self.modules.get('position_advice', True):
            if has_position:
                analysis_modules.append("4. **持仓建议**: 是否应该继续持有、加仓、减仓或平仓")
            else:
                analysis_modules.append("4. **开仓建议**: 是否适合开仓、建议的仓位大小")
        if self.modules.get('market_sentiment', True):
            analysis_modules.append("5. **市场情绪**: 当前市场情绪（恐慌/贪婪）、情绪对价格的影响")

        modules_text = "\n".join(analysis_modules)

        prompt = f"""你是一个专业的量化交易分析师，请根据以下市场数据进行**定期市场分析**。

{market_data}

## 分析要求

{analysis_depth}

请从以下维度进行分析：

{modules_text}

## 输出格式（严格JSON）

```json
{{
  "market_trend": {{
    "direction": "上涨/下跌/震荡",
    "strength": "强/中/弱",
    "sustainability": "高/中/低",
    "summary": "趋势总结"
  }},
  "risk_assessment": {{
    "risk_level": "低/中/高",
    "risk_factors": ["风险因素1", "风险因素2"],
    "summary": "风险总结"
  }},
  "entry_opportunities": {{
    "has_opportunity": true/false,
    "direction": "做多/做空/观望",
    "entry_price": 价格数值或null,
    "confidence": 0-1,
    "summary": "机会总结"
  }},
  "position_advice": {{
    "action": "持有/加仓/减仓/平仓/开仓/观望",
    "reason": "建议原因",
    "position_size": "建议仓位大小（如10%、20%等）",
    "summary": "持仓建议总结"
  }},
  "market_sentiment": {{
    "sentiment": "极度恐慌/恐慌/中性/贪婪/极度贪婪",
    "impact": "情绪对价格的影响",
    "summary": "情绪总结"
  }},
  "overall_summary": "整体市场总结（2-3句话）",
  "key_points": ["关键点1", "关键点2", "关键点3"]
}}
```

**重要**: 只输出JSON，不要有任何其他文字。
"""
        return prompt

    def analyze_market(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        执行市场分析

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 持仓信息

        Returns:
            分析结果字典
        """
        if not self.enabled:
            logger.warning("Claude 定时分析未启用")
            return None

        try:
            # 格式化市场数据
            market_data = self._format_market_data(df, current_price, indicators, position_info)

            # 构建提示词
            has_position = position_info is not None
            prompt = self._build_analysis_prompt(market_data, has_position)

            # 调用 Claude API (添加超时控制)
            logger.info("正在调用 Claude API 进行定期市场分析...")

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=3000,
                    timeout=self.timeout,  # 添加超时控制
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            except Exception as api_error:
                # 捕获API调用异常（包括超时）
                error_msg = str(api_error)
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    logger.error(f"Claude API 调用超时 (超时设置: {self.timeout}秒): {error_msg}")
                else:
                    logger.error(f"Claude API 调用失败: {error_msg}")
                return None

            # 解析响应
            response_text = response.content[0].text
            logger.debug(f"Claude 响应: {response_text}")

            # 提取 JSON
            analysis = self._parse_response(response_text)

            if not analysis:
                logger.error("无法解析 Claude 响应")
                return None

            # 添加元数据
            analysis['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            analysis['analysis_count'] = self.analysis_count + 1
            analysis['current_price'] = current_price

            logger.info("Claude 市场分析完成")
            return analysis

        except Exception as e:
            logger.error(f"Claude 市场分析失败: {e}")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
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

    def _format_feishu_message(self, analysis: Dict) -> str:
        """
        格式化飞书消息

        Args:
            analysis: 分析结果

        Returns:
            格式化的飞书消息
        """
        timestamp = analysis.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        current_price = analysis.get('current_price', 'N/A')
        analysis_count = analysis.get('analysis_count', 0)

        # 构建消息
        message = f"""📊 Claude AI 市场分析报告 #{analysis_count}

⏰ 时间: {timestamp}
💰 当前价格: {current_price} USDT

"""

        # 市场趋势
        if 'market_trend' in analysis:
            trend = analysis['market_trend']
            direction = trend.get('direction', 'N/A')
            strength = trend.get('strength', 'N/A')
            summary = trend.get('summary', 'N/A')

            # 根据方向选择emoji
            if '上涨' in direction:
                emoji = '📈'
            elif '下跌' in direction:
                emoji = '📉'
            else:
                emoji = '📊'

            message += f"""{emoji} 市场趋势
方向: {direction} | 强度: {strength}
{summary}

"""

        # 风险评估
        if 'risk_assessment' in analysis:
            risk = analysis['risk_assessment']
            risk_level = risk.get('risk_level', 'N/A')
            summary = risk.get('summary', 'N/A')

            # 根据风险等级选择emoji
            if '高' in risk_level:
                emoji = '🔴'
            elif '中' in risk_level:
                emoji = '🟡'
            else:
                emoji = '🟢'

            message += f"""{emoji} 风险评估
风险等级: {risk_level}
{summary}

"""

        # 入场机会
        if 'entry_opportunities' in analysis:
            entry = analysis['entry_opportunities']
            has_opportunity = entry.get('has_opportunity', False)
            direction = entry.get('direction', 'N/A')
            confidence = entry.get('confidence', 0)
            summary = entry.get('summary', 'N/A')

            emoji = '✅' if has_opportunity else '⏸️'
            message += f"""{emoji} 入场机会
方向: {direction} | 置信度: {confidence:.0%}
{summary}

"""

        # 持仓建议
        if 'position_advice' in analysis:
            advice = analysis['position_advice']
            action = advice.get('action', 'N/A')
            position_size = advice.get('position_size', 'N/A')
            summary = advice.get('summary', 'N/A')

            message += f"""💡 持仓建议
操作: {action} | 仓位: {position_size}
{summary}

"""

        # 市场情绪
        if 'market_sentiment' in analysis:
            sentiment = analysis['market_sentiment']
            sentiment_text = sentiment.get('sentiment', 'N/A')
            summary = sentiment.get('summary', 'N/A')

            # 根据情绪选择emoji
            if '恐慌' in sentiment_text:
                emoji = '😨'
            elif '贪婪' in sentiment_text:
                emoji = '🤑'
            else:
                emoji = '😐'

            message += f"""{emoji} 市场情绪
情绪: {sentiment_text}
{summary}

"""

        # 整体总结
        overall_summary = analysis.get('overall_summary', 'N/A')
        message += f"""📝 整体总结
{overall_summary}

"""

        # 关键点
        key_points = analysis.get('key_points', [])
        if key_points:
            message += "🔑 关键点\n"
            for i, point in enumerate(key_points, 1):
                message += f"{i}. {point}\n"

        message += f"\n---\n🤖 由 Claude AI 生成 | 间隔: {self.interval_minutes}分钟"

        return message

    def check_and_analyze(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict] = None
    ) -> bool:
        """
        检查是否需要分析，如果需要则执行分析并推送

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 持仓信息

        Returns:
            是否成功执行分析
        """
        if not self.should_analyze():
            return False

        return self.analyze_now(df, current_price, indicators, position_info)

    def analyze_now(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict] = None
    ) -> bool:
        """
        立即执行分析并推送

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 持仓信息

        Returns:
            是否成功
        """
        try:
            logger.info("开始执行 Claude 定期市场分析...")

            # 执行分析
            analysis = self.analyze_market(df, current_price, indicators, position_info)

            if not analysis:
                logger.error("Claude 市场分析失败")
                # 即使失败也更新时间，避免无限重试
                # 等待下一个30分钟周期再尝试
                self.last_analysis_time = datetime.now()
                return False

            # 更新状态
            self.last_analysis_time = datetime.now()
            self.analysis_count += 1

            # 推送到飞书
            if self.push_to_feishu:
                message = self._format_feishu_message(analysis)
                success = notifier.feishu.send_message(message)

                if success:
                    logger.info("Claude 分析结果已推送到飞书")
                else:
                    logger.error("推送到飞书失败")
                    return False

            logger.info(f"Claude 定期分析完成 (第 {self.analysis_count} 次)")
            return True

        except Exception as e:
            logger.error(f"Claude 定期分析执行失败: {e}")
            return False

    def should_generate_daily_report(self) -> bool:
        """
        判断是否应该生成每日报告

        Returns:
            是否应该生成每日报告
        """
        if not self.enabled:
            return False

        # 检查是否启用每日报告
        if not getattr(config, 'ENABLE_CLAUDE_DAILY_REPORT', False):
            return False

        from datetime import timezone
        import pytz

        # 获取配置的时区和报告时间
        report_hour = getattr(config, 'CLAUDE_DAILY_REPORT_HOUR', 8)
        tz_name = getattr(config, 'CLAUDE_DAILY_REPORT_TIMEZONE', 'Asia/Shanghai')

        try:
            tz = pytz.timezone(tz_name)
        except Exception as e:
            logger.error(f"时区配置错误: {e}")
            tz = pytz.timezone('Asia/Shanghai')

        now = datetime.now(tz)
        today_date = now.date()

        # 如果今天已经生成过报告，跳过
        if self.last_daily_report_date == today_date:
            return False

        # 只在报告时间点的时间窗口内生成（例如8:00-8:10）
        # 这样避免了在过了报告时间后每次循环都尝试生成
        if now.hour == report_hour and now.minute < 10:
            return True

        return False

    def generate_daily_report(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict] = None,
        trades_history: Optional[List[Dict]] = None
    ) -> bool:
        """
        生成每日报告

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 当前持仓信息
            trades_history: 昨日交易历史

        Returns:
            是否成功
        """
        try:
            from datetime import timezone
            import pytz

            logger.info("开始生成 Claude 每日市场报告...")

            # 获取时区
            tz_name = getattr(config, 'CLAUDE_DAILY_REPORT_TIMEZONE', 'Asia/Shanghai')
            try:
                tz = pytz.timezone(tz_name)
            except:
                tz = pytz.timezone('Asia/Shanghai')

            now = datetime.now(tz)

            # 执行每日分析
            analysis = self._analyze_daily_report(
                df, current_price, indicators, position_info, trades_history
            )

            if not analysis:
                logger.error("Claude 每日报告生成失败")
                # 即使失败也更新日期，避免在时间窗口内无限重试
                # 等待明天的时间窗口再尝试
                self.last_daily_report_date = now.date()
                return False

            # 更新状态
            self.last_daily_report_date = now.date()

            # 推送到飞书
            if self.push_to_feishu:
                message = self._format_daily_report_message(analysis, now)
                success = notifier.feishu.send_message(message)

                if success:
                    logger.info("Claude 每日报告已推送到飞书")
                else:
                    logger.error("推送每日报告到飞书失败")
                    return False

            logger.info("Claude 每日报告生成完成")
            return True

        except Exception as e:
            logger.error(f"Claude 每日报告生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 即使发生异常也更新日期，避免无限重试
            try:
                import pytz
                tz_name = getattr(config, 'CLAUDE_DAILY_REPORT_TIMEZONE', 'Asia/Shanghai')
                tz = pytz.timezone(tz_name)
                self.last_daily_report_date = datetime.now(tz).date()
            except:
                pass
            return False

    def _analyze_daily_report(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        position_info: Optional[Dict],
        trades_history: Optional[List[Dict]]
    ) -> Optional[Dict]:
        """
        执行每日报告分析（包含网络检索）

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标
            position_info: 当前持仓
            trades_history: 昨日交易历史

        Returns:
            分析结果字典
        """
        try:
            # 格式化市场数据
            market_data = self._format_market_data(df, current_price, indicators, position_info)

            # 格式化交易历史
            trade_review = self._format_trade_history(trades_history) if trades_history else "昨日无交易记录"

            # 构建每日报告提示词
            prompt = self._build_daily_report_prompt(market_data, trade_review)

            # 调用 Claude API
            logger.info(f"调用 Claude API 生成每日报告 (模型: {self.model})")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,  # 每日报告可能更长
                timeout=self.timeout,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # 提取文本内容
            if not response.content:
                logger.error("Claude API 返回空内容")
                return None

            content = response.content[0].text
            logger.debug(f"Claude 返回内容长度: {len(content)}")

            # 解析JSON响应
            analysis = self._parse_json_response(content)

            if not analysis:
                logger.error("无法解析 Claude 返回的 JSON")
                return None

            logger.info("Claude 每日报告分析完成")
            return analysis

        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                logger.error(f"Claude API 调用超时 (超时设置: {self.timeout}秒): {error_msg}")
            else:
                logger.error(f"Claude API 调用失败: {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _format_trade_history(self, trades: List[Dict]) -> str:
        """
        格式化交易历史记录

        Args:
            trades: 交易历史列表

        Returns:
            格式化的交易历史文本
        """
        if not trades:
            return "昨日无交易记录"

        review_text = f"昨日共执行 {len(trades)} 笔交易：\n\n"

        for i, trade in enumerate(trades, 1):
            review_text += f"{i}. {trade.get('side', 'N/A').upper()} "
            review_text += f"@ ${trade.get('price', 0):.2f}, "
            review_text += f"数量: {trade.get('amount', 0):.4f}, "

            pnl = trade.get('pnl', 0)
            pnl_pct = trade.get('pnl_percent', 0)
            if pnl > 0:
                review_text += f"盈利: ${pnl:.2f} (+{pnl_pct:.2f}%)"
            elif pnl < 0:
                review_text += f"亏损: ${pnl:.2f} ({pnl_pct:.2f}%)"
            else:
                review_text += "盈亏: $0.00 (0.00%)"

            review_text += f", 策略: {trade.get('strategy', 'N/A')}\n"

        # 计算总盈亏
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        win_trades = len([t for t in trades if t.get('pnl', 0) > 0])
        lose_trades = len([t for t in trades if t.get('pnl', 0) < 0])

        review_text += f"\n总结：\n"
        review_text += f"- 总盈亏: ${total_pnl:.2f}\n"
        review_text += f"- 胜率: {win_trades}/{len(trades)} ({win_trades/len(trades)*100:.1f}%)\n"

        return review_text

    def _build_daily_report_prompt(self, market_data: str, trade_review: str) -> str:
        """
        构建每日报告分析提示词

        Args:
            market_data: 市场数据
            trade_review: 交易回顾

        Returns:
            提示词
        """
        prompt = f"""你是一位专业的加密货币交易分析师。请基于以下信息生成一份详细的每日市场报告：

## 当前市场数据
{market_data}

## 昨日交易回顾
{trade_review}

## 分析要求

请结合**实时网络信息**（如加密货币新闻、市场动态、重大事件等），完成以下分析：

1. **昨日市场回顾**
   - 分析昨日市场整体走势
   - 评价昨日交易决策的合理性
   - 指出昨日交易中的优点和不足

2. **当前市场状态**
   - 当前价格走势和技术指标分析
   - 市场趋势和强度评估
   - 关键支撑位和阻力位

3. **今日行情预测**
   - 结合实时网络信息，预测今日可能的走势
   - 分析可能影响价格的因素（新闻、事件等）
   - 给出多头/空头倾向和理由

4. **交易建议**
   - 今日的交易策略建议
   - 建议的入场位置和方向
   - 风险提示和止损建议

5. **风险因素**
   - 需要关注的风险点
   - 可能的黑天鹅事件
   - 建议的风险控制措施

## 输出格式

请以JSON格式输出，包含以下字段：
{{
    "yesterday_review": {{
        "market_summary": "昨日市场概况",
        "trade_evaluation": "交易评价（优点、不足）",
        "lessons_learned": "经验教训"
    }},
    "current_status": {{
        "price_trend": "当前价格走势",
        "technical_analysis": "技术指标分析",
        "key_levels": "关键价位"
    }},
    "today_forecast": {{
        "trend_prediction": "今日走势预测",
        "influencing_factors": "影响因素（含网络信息）",
        "bias": "多空倾向（bullish/bearish/neutral）",
        "confidence": 0.0-1.0
    }},
    "trading_advice": {{
        "strategy": "交易策略",
        "entry_suggestions": "入场建议",
        "stop_loss": "止损建议",
        "risk_reward": "风险回报比"
    }},
    "risk_factors": {{
        "risks": ["风险1", "风险2", ...],
        "black_swan_events": ["可能的黑天鹅事件"],
        "risk_control": "风险控制建议"
    }},
    "web_search_insights": "从网络检索到的重要信息和见解",
    "overall_sentiment": "整体市场情绪（fearful/neutral/greedy）",
    "confidence_level": 0.0-1.0
}}

请确保分析全面、客观、可操作。"""

        return prompt

    def _format_daily_report_message(self, analysis: Dict, report_time: datetime) -> str:
        """
        格式化每日报告飞书消息

        Args:
            analysis: 分析结果
            report_time: 报告时间

        Returns:
            格式化的飞书消息
        """
        time_str = report_time.strftime('%Y-%m-%d %H:%M')

        # 提取分析内容
        yesterday = analysis.get('yesterday_review', {})
        current = analysis.get('current_status', {})
        forecast = analysis.get('today_forecast', {})
        advice = analysis.get('trading_advice', {})
        risks = analysis.get('risk_factors', {})
        web_insights = analysis.get('web_search_insights', 'N/A')
        sentiment = analysis.get('overall_sentiment', 'neutral')
        confidence = analysis.get('confidence_level', 0.5)

        # 情绪表情
        sentiment_emoji = {
            'fearful': '😨',
            'neutral': '😐',
            'greedy': '🤑'
        }.get(sentiment, '😐')

        # 趋势表情
        bias = forecast.get('bias', 'neutral')
        bias_emoji = {
            'bullish': '📈',
            'bearish': '📉',
            'neutral': '➡️'
        }.get(bias, '➡️')

        message = f"""📊 **Claude AI 每日市场报告**

⏰ 报告时间：{time_str}
{sentiment_emoji} 市场情绪：{sentiment.upper()}
📊 置信度：{confidence*100:.0f}%

---

## 📅 昨日市场回顾

**市场概况**
{yesterday.get('market_summary', 'N/A')}

**交易评价**
{yesterday.get('trade_evaluation', 'N/A')}

**经验教训**
{yesterday.get('lessons_learned', 'N/A')}

---

## 📍 当前市场状态

**价格走势**
{current.get('price_trend', 'N/A')}

**技术分析**
{current.get('technical_analysis', 'N/A')}

**关键价位**
{current.get('key_levels', 'N/A')}

---

## 🔮 今日行情预测

{bias_emoji} **趋势预测**
{forecast.get('trend_prediction', 'N/A')}

**影响因素**
{forecast.get('influencing_factors', 'N/A')}

**多空倾向**
{bias.upper()} (置信度: {forecast.get('confidence', 0)*100:.0f}%)

---

## 💡 交易建议

**策略**
{advice.get('strategy', 'N/A')}

**入场建议**
{advice.get('entry_suggestions', 'N/A')}

**止损建议**
{advice.get('stop_loss', 'N/A')}

**风险回报比**
{advice.get('risk_reward', 'N/A')}

---

## ⚠️ 风险提示

**主要风险**
"""
        risk_list = risks.get('risks', [])
        if risk_list:
            for risk in risk_list:
                message += f"• {risk}\n"
        else:
            message += "无特别风险\n"

        message += f"\n**可能的黑天鹅事件**\n"
        black_swan = risks.get('black_swan_events', [])
        if black_swan:
            for event in black_swan:
                message += f"• {event}\n"
        else:
            message += "暂无\n"

        message += f"\n**风险控制**\n{risks.get('risk_control', 'N/A')}"

        message += f"\n\n---\n\n## 🌐 网络信息洞察\n\n{web_insights}"

        message += "\n\n---\n\n*本报告由 Claude AI 自动生成，仅供参考，不构成投资建议。*"

        return message


# 全局实例
_claude_periodic_analyzer: Optional[ClaudePeriodicAnalyzer] = None


def get_claude_periodic_analyzer() -> Optional[ClaudePeriodicAnalyzer]:
    """获取 Claude 定时分析器单例"""
    global _claude_periodic_analyzer

    if not getattr(config, 'ENABLE_CLAUDE_PERIODIC_ANALYSIS', False):
        return None

    if _claude_periodic_analyzer is None:
        interval = getattr(config, 'CLAUDE_PERIODIC_INTERVAL', 30)
        detail_level = getattr(config, 'CLAUDE_ANALYSIS_DETAIL_LEVEL', 'standard')
        _claude_periodic_analyzer = ClaudePeriodicAnalyzer(
            interval_minutes=interval,
            enabled=True,
            detail_level=detail_level
        )

    return _claude_periodic_analyzer
