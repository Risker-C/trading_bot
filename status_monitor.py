"""
状态监控模块

提供定期状态监控和推送功能，用于实时了解机器人运行状态。
特点：
1. 短周期推送（默认5分钟）
2. 包含最近N分钟行情变化
3. 飞书推送失败时自动发送邮件预警
4. 预留AI分析接口
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import time
import traceback
from collections import deque

import config
from logger_utils import get_logger, notifier, db


class PriceHistory:
    """价格历史记录器"""

    def __init__(self, max_minutes: int = 60):
        """
        初始化价格历史记录器

        Args:
            max_minutes: 保留最近多少分钟的数据
        """
        self.max_minutes = max_minutes
        self.prices: deque = deque(maxlen=max_minutes * 12)  # 假设每5秒记录一次
        self.logger = get_logger("price_history")

    def add_price(self, price: float, timestamp: Optional[datetime] = None):
        """
        添加价格记录

        Args:
            price: 价格
            timestamp: 时间戳，默认为当前时间
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.prices.append({
            'price': price,
            'timestamp': timestamp
        })

    def get_price_change(self, minutes: int) -> Optional[Dict[str, Any]]:
        """
        获取最近N分钟的价格变化

        Args:
            minutes: 分钟数

        Returns:
            dict: 包含价格变化信息，如果数据不足则返回None
        """
        if len(self.prices) < 2:
            return None

        now = datetime.now()
        cutoff_time = now - timedelta(minutes=minutes)

        # 找到N分钟前的价格
        old_price = None
        for record in self.prices:
            if record['timestamp'] >= cutoff_time:
                old_price = record['price']
                break

        if old_price is None:
            # 如果没有找到，使用最早的记录
            if len(self.prices) > 0:
                old_price = self.prices[0]['price']
            else:
                return None

        # 当前价格
        current_price = self.prices[-1]['price']

        # 计算变化
        change = current_price - old_price
        change_percent = (change / old_price * 100) if old_price > 0 else 0

        # 计算最高价和最低价
        prices_in_period = [r['price'] for r in self.prices if r['timestamp'] >= cutoff_time]
        if not prices_in_period:
            prices_in_period = [r['price'] for r in self.prices]

        highest = max(prices_in_period) if prices_in_period else current_price
        lowest = min(prices_in_period) if prices_in_period else current_price

        return {
            'old_price': old_price,
            'current_price': current_price,
            'change': change,
            'change_percent': change_percent,
            'highest': highest,
            'lowest': lowest,
            'volatility': ((highest - lowest) / lowest * 100) if lowest > 0 else 0
        }


class StatusMonitorScheduler:
    """状态监控调度器"""

    def __init__(self, interval_minutes: int = 5, enabled: bool = True):
        """
        初始化调度器

        Args:
            interval_minutes: 推送间隔（分钟）
            enabled: 是否启用
        """
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.last_push_time = None  # 上次推送时间
        self.start_time = datetime.now()  # 启动时间
        self.push_count = 0  # 已推送次数
        self.error_count = 0  # 错误次数
        self.last_error_time = None  # 上次错误时间
        self.logger = get_logger("status_monitor")

        # 价格历史记录器
        self.price_history = PriceHistory(max_minutes=60)

        if self.enabled:
            self.logger.info(f"✅ 状态监控调度器已启用，间隔: {interval_minutes}分钟")
        else:
            self.logger.info("⏭️  状态监控调度器已禁用")

    def should_push(self) -> bool:
        """
        判断是否应该推送

        Returns:
            bool: True表示应该推送
        """
        if not self.enabled:
            return False

        # 如果从未推送过，应该推送
        if self.last_push_time is None:
            return True

        # 检查是否到达推送时间
        elapsed = datetime.now() - self.last_push_time
        return elapsed.total_seconds() >= self.interval_minutes * 60

    def update_price(self, price: float):
        """
        更新价格记录

        Args:
            price: 当前价格
        """
        self.price_history.add_price(price)

    def check_and_push(self, trader, risk_manager) -> bool:
        """
        检查并推送状态（如果需要）

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例

        Returns:
            bool: True表示推送成功
        """
        if not self.should_push():
            return False

        return self.push_now(trader, risk_manager)

    def push_now(self, trader, risk_manager) -> bool:
        """
        立即推送状态

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例

        Returns:
            bool: True表示推送成功
        """
        try:
            self.logger.info("📊 状态监控: 开始生成状态报告")
            start_time = time.time()

            # 创建状态收集器
            collector = StatusMonitorCollector(
                trader,
                risk_manager,
                self.price_history,
                self.start_time,
                self.error_count
            )

            # 生成并推送报告
            success = collector.collect_and_push()

            elapsed = time.time() - start_time

            if success:
                self.last_push_time = datetime.now()
                self.push_count += 1
                self.logger.info(f"📊 状态监控: 推送成功 (第{self.push_count}次，耗时{elapsed:.2f}秒)")
                return True
            else:
                self.error_count += 1
                self.last_error_time = datetime.now()
                self.logger.warning(f"📊 状态监控: 推送失败 (错误次数: {self.error_count})")
                return False

        except Exception as e:
            self.error_count += 1
            self.last_error_time = datetime.now()
            self.logger.error(f"📊 状态监控: 推送异常 - {e}")
            self.logger.error(traceback.format_exc())
            return False

    def get_next_push_time(self) -> Optional[datetime]:
        """
        获取下次推送时间

        Returns:
            datetime: 下次推送时间，如果未启用则返回None
        """
        if not self.enabled or self.last_push_time is None:
            return None

        return self.last_push_time + timedelta(minutes=self.interval_minutes)

    def get_time_until_next_push(self) -> Optional[timedelta]:
        """
        获取距离下次推送的时间

        Returns:
            timedelta: 剩余时间，如果未启用则返回None
        """
        next_time = self.get_next_push_time()
        if next_time is None:
            return None

        remaining = next_time - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


class StatusMonitorCollector:
    """状态监控数据收集器"""

    def __init__(self, trader, risk_manager, price_history: PriceHistory,
                 start_time: datetime, error_count: int):
        """
        初始化收集器

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例
            price_history: 价格历史记录器
            start_time: 服务启动时间
            error_count: 错误次数
        """
        self.trader = trader
        self.risk_manager = risk_manager
        self.price_history = price_history
        self.start_time = start_time
        self.error_count = error_count
        self.logger = get_logger("status_collector")

    def collect_all(self) -> Dict[str, Any]:
        """
        收集所有状态数据

        Returns:
            dict: 状态数据字典
        """
        data = {}
        modules = config.STATUS_MONITOR_MODULES

        try:
            if modules.get('market_change', True):
                data['market_change'] = self._collect_market_change()
        except Exception as e:
            self.logger.warning(f"收集行情变化失败: {e}")
            data['market_change'] = {'error': str(e)}

        try:
            if modules.get('trade_activity', True):
                data['trade_activity'] = self._collect_trade_activity()
        except Exception as e:
            self.logger.warning(f"收集交易活动失败: {e}")
            data['trade_activity'] = {'error': str(e)}

        try:
            if modules.get('trend_analysis', True):
                data['trend_analysis'] = self._collect_trend_analysis()
        except Exception as e:
            self.logger.warning(f"收集趋势分析失败: {e}")
            data['trend_analysis'] = {'error': str(e)}

        try:
            if modules.get('service_status', True):
                data['service_status'] = self._collect_service_status()
        except Exception as e:
            self.logger.warning(f"收集服务状态失败: {e}")
            data['service_status'] = {'error': str(e)}

        try:
            if modules.get('account_info', True):
                data['account_info'] = self._collect_account_info()
        except Exception as e:
            self.logger.warning(f"收集账户信息失败: {e}")
            data['account_info'] = {'error': str(e)}

        return data

    def _collect_market_change(self) -> Dict[str, Any]:
        """收集最近N分钟行情变化"""
        interval = config.STATUS_MONITOR_INTERVAL

        # 获取价格变化
        price_change = self.price_history.get_price_change(interval)

        if price_change is None:
            return {
                'available': False,
                'reason': '数据不足'
            }

        return {
            'available': True,
            'interval_minutes': interval,
            'old_price': price_change['old_price'],
            'current_price': price_change['current_price'],
            'change': price_change['change'],
            'change_percent': price_change['change_percent'],
            'highest': price_change['highest'],
            'lowest': price_change['lowest'],
            'volatility': price_change['volatility']
        }

    def _collect_trade_activity(self) -> Dict[str, Any]:
        """收集开单情况"""
        interval = config.STATUS_MONITOR_INTERVAL

        # 从数据库获取最近N分钟的交易
        cutoff_time = datetime.now() - timedelta(minutes=interval)
        all_trades = db.get_trades(limit=100)

        recent_trades = []
        for trade in all_trades:
            try:
                trade_time_str = trade.get('created_at') or trade.get('timestamp', '')
                if trade_time_str:
                    try:
                        trade_time = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
                    except:
                        trade_time = datetime.strptime(trade_time_str, '%Y-%m-%d %H:%M:%S')

                    if trade_time >= cutoff_time:
                        recent_trades.append(trade)
            except:
                continue

        # 统计开仓和平仓
        open_count = sum(1 for t in recent_trades if t.get('action') == 'open')
        close_count = sum(1 for t in recent_trades if t.get('action') == 'close')

        # 统计盈亏
        total_pnl = sum(t.get('pnl', 0) for t in recent_trades if t.get('action') == 'close')

        # 获取最近一笔交易
        last_trade = None
        if recent_trades:
            latest = recent_trades[0]
            last_trade = {
                'time': latest.get('created_at') or latest.get('timestamp', 'N/A'),
                'side': latest.get('side', 'N/A'),
                'action': latest.get('action', 'N/A'),
                'price': latest.get('price', 0),
                'amount': latest.get('amount', 0)
            }

        return {
            'interval_minutes': interval,
            'open_count': open_count,
            'close_count': close_count,
            'total_trades': len(recent_trades),
            'total_pnl': total_pnl,
            'last_trade': last_trade
        }

    def _collect_trend_analysis(self) -> Dict[str, Any]:
        """收集趋势分析"""
        try:
            # 获取K线数据
            df = self.trader.get_klines(limit=200)
            if df is None or df.empty:
                return {'error': '数据获取失败'}

            # 检测市场状态
            from market_regime import MarketRegimeDetector
            detector = MarketRegimeDetector(df)
            regime_info = detector.detect()

            # 转换为字典格式
            state_map = {
                'ranging': '震荡市',
                'transitioning': '过渡市',
                'trending': '趋势市',
            }
            state = state_map.get(regime_info.regime.value, '未知')

            # 趋势描述
            trend_map = {
                1: '上涨',
                -1: '下跌',
                0: '横盘',
            }
            trend = trend_map.get(regime_info.trend_direction, '未知')

            # 波动率等级
            if regime_info.volatility < 0.01:
                volatility = '低'
            elif regime_info.volatility < 0.03:
                volatility = '中等'
            else:
                volatility = '高'

            return {
                'state': state,
                'confidence': int(regime_info.confidence * 100),
                'adx': regime_info.adx,
                'bb_width': regime_info.bb_width * 100,
                'trend': trend,
                'volatility': volatility,
                'tradeable': regime_info.confidence > 0.5
            }
        except Exception as e:
            return {'error': str(e)}

    def _collect_service_status(self) -> Dict[str, Any]:
        """收集服务状态"""
        now = datetime.now()
        uptime_seconds = (now - self.start_time).total_seconds()

        return {
            'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
            'uptime': self._format_duration(uptime_seconds),
            'uptime_seconds': uptime_seconds,
            'error_count': self.error_count,
            'status': 'running'
        }

    def _collect_account_info(self) -> Dict[str, Any]:
        """收集账户信息"""
        try:
            balance = self.trader.get_balance()
            positions = self.trader.get_positions()

            result = {
                'balance': balance,
                'has_position': len(positions) > 0
            }

            if positions:
                pos = positions[0]
                ticker = self.trader.get_ticker()
                current_price = ticker['last'] if ticker else pos['entry_price']

                # 计算盈亏百分比
                pnl_percent = 0
                if pos['entry_price'] > 0 and pos['amount'] > 0:
                    pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount']) * 100 * config.LEVERAGE)

                # 计算持仓时长
                duration = 'N/A'
                if hasattr(self.risk_manager, 'position') and self.risk_manager.position:
                    entry_time = self.risk_manager.position.entry_time
                    duration_seconds = (datetime.now() - entry_time).total_seconds()
                    duration = self._format_duration(duration_seconds)

                result['position'] = {
                    'side': pos['side'],
                    'amount': pos['amount'],
                    'entry_price': pos['entry_price'],
                    'current_price': current_price,
                    'pnl': pos['unrealized_pnl'],
                    'pnl_percent': pnl_percent,
                    'duration': duration
                }

            return result
        except Exception as e:
            return {'error': str(e)}

    def format_message(self, data: Dict[str, Any]) -> str:
        """
        格式化状态消息

        Args:
            data: 状态数据

        Returns:
            str: 格式化的消息文本
        """
        lines = []

        # 标题
        lines.append("🔔 系统状态推送")
        lines.append("━" * 30)
        lines.append("")

        # 服务状态
        if 'service_status' in data and 'error' not in data['service_status']:
            status = data['service_status']
            lines.append("⚙️ 服务状态")
            lines.append("━" * 30)
            lines.append(f"时间: {status.get('timestamp', 'N/A')}")
            lines.append(f"运行时长: {status.get('uptime', 'N/A')}")
            lines.append(f"错误次数: {status.get('error_count', 0)}")
            lines.append(f"状态: ✅ 正常运行")
            lines.append("")

        # 行情变化
        if 'market_change' in data and 'error' not in data['market_change']:
            market = data['market_change']
            if market.get('available', False):
                lines.append(f"📈 最近{market['interval_minutes']}分钟行情")
                lines.append("━" * 30)

                change = market['change']
                change_percent = market['change_percent']
                change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➖"

                lines.append(f"当前价格: ${market['current_price']:,.2f}")
                lines.append(f"价格变化: {change:+.2f} ({change_percent:+.2f}%) {change_emoji}")
                lines.append(f"区间最高: ${market['highest']:,.2f}")
                lines.append(f"区间最低: ${market['lowest']:,.2f}")
                lines.append(f"波动幅度: {market['volatility']:.2f}%")
                lines.append("")

        # 趋势分析
        if 'trend_analysis' in data and 'error' not in data['trend_analysis']:
            trend = data['trend_analysis']
            lines.append("🎯 趋势分析")
            lines.append("━" * 30)
            lines.append(f"市场状态: {trend.get('state', 'N/A')}")
            lines.append(f"置信度: {trend.get('confidence', 0)}%")
            lines.append(f"趋势方向: {trend.get('trend', 'N/A')}")
            lines.append(f"波动率: {trend.get('volatility', 'N/A')}")

            tradeable = trend.get('tradeable', False)
            tradeable_emoji = "✅" if tradeable else "❌"
            lines.append(f"适合交易: {tradeable_emoji}")
            lines.append("")

        # 交易活动
        if 'trade_activity' in data and 'error' not in data['trade_activity']:
            activity = data['trade_activity']
            lines.append(f"💼 最近{activity['interval_minutes']}分钟交易")
            lines.append("━" * 30)
            lines.append(f"开仓次数: {activity['open_count']}")
            lines.append(f"平仓次数: {activity['close_count']}")

            if activity['close_count'] > 0:
                pnl = activity['total_pnl']
                pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
                lines.append(f"盈亏: {pnl:+.2f} USDT {pnl_emoji}")

            if activity['last_trade']:
                last = activity['last_trade']
                lines.append(f"最近交易: {last['action']} {last['side']}")
            else:
                lines.append("最近交易: 无")
            lines.append("")

        # 账户信息
        if 'account_info' in data and 'error' not in data['account_info']:
            account = data['account_info']
            lines.append("💰 账户信息")
            lines.append("━" * 30)
            lines.append(f"可用余额: {account.get('balance', 0):.2f} USDT")

            if account.get('has_position', False) and 'position' in account:
                pos = account['position']
                side_emoji = "🟢" if pos['side'] == 'long' else "🔴"
                side_cn = "多单" if pos['side'] == 'long' else "空单"

                lines.append(f"持仓: {side_emoji} {side_cn}")
                lines.append(f"数量: {pos['amount']} BTC")
                lines.append(f"开仓价: ${pos['entry_price']:,.2f}")
                lines.append(f"当前价: ${pos['current_price']:,.2f}")

                pnl = pos['pnl']
                pnl_percent = pos['pnl_percent']
                pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
                lines.append(f"盈亏: {pnl:+.2f} USDT ({pnl_percent:+.2f}%) {pnl_emoji}")
                lines.append(f"持仓时长: {pos['duration']}")
            else:
                lines.append("持仓: 无")
            lines.append("")

        # AI分析（预留）
        if config.STATUS_MONITOR_ENABLE_AI:
            lines.append("🤖 AI分析")
            lines.append("━" * 30)
            lines.append("AI分析功能开发中...")
            lines.append("")

        # 结尾
        lines.append("━" * 30)
        lines.append(f"⏰ 下次推送: {config.STATUS_MONITOR_INTERVAL}分钟后")

        return "\n".join(lines)

    def collect_and_push(self) -> bool:
        """
        收集数据并推送

        Returns:
            bool: True表示推送成功
        """
        try:
            # 收集所有数据
            data = self.collect_all()

            # 格式化消息
            message = self.format_message(data)

            # 推送到飞书
            feishu_success = False
            if config.ENABLE_FEISHU:
                try:
                    feishu_success = notifier.feishu.send_message(message)
                    if feishu_success:
                        self.logger.info("✅ 飞书推送成功")
                    else:
                        self.logger.warning("❌ 飞书推送失败")
                except Exception as e:
                    self.logger.error(f"❌ 飞书推送异常: {e}")
                    feishu_success = False

            # 如果飞书推送失败，发送邮件预警
            if not feishu_success and config.STATUS_MONITOR_EMAIL_ON_FAILURE:
                self.logger.warning("⚠️ 飞书推送失败，尝试发送邮件预警")
                try:
                    if config.ENABLE_EMAIL:
                        email_subject = "⚠️ 交易机器人状态推送失败预警"
                        email_body = f"""
<h2>飞书推送失败预警</h2>
<p>交易机器人的飞书状态推送失败，请检查飞书配置。</p>
<p>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<h3>状态信息</h3>
<pre>{message}</pre>

<p>请及时检查系统状态和飞书配置。</p>
"""
                        email_success = notifier.email.send_message(email_subject, email_body, html=True)
                        if email_success:
                            self.logger.info("✅ 邮件预警发送成功")
                        else:
                            self.logger.error("❌ 邮件预警发送失败")
                except Exception as e:
                    self.logger.error(f"❌ 邮件预警发送异常: {e}")

            return feishu_success

        except Exception as e:
            self.logger.error(f"收集和推送失败: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def _format_duration(self, seconds: float) -> str:
        """
        格式化时长

        Args:
            seconds: 秒数

        Returns:
            str: 格式化的时长字符串
        """
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}分钟"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}小时{minutes}分钟"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}天{hours}小时"


# AI分析接口（预留）
class AIAnalyzer:
    """AI分析器（预留接口）"""

    def __init__(self):
        self.logger = get_logger("ai_analyzer")

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析状态数据并提供建议

        Args:
            data: 状态数据

        Returns:
            dict: 分析结果和建议
        """
        # TODO: 实现AI分析逻辑
        # 可以集成大语言模型API，对市场状态进行深度分析
        # 提供交易建议、风险提示等

        self.logger.info("AI分析功能待实现")

        return {
            'available': False,
            'message': 'AI分析功能开发中'
        }
