"""
定期市场分析报告模块

提供定期向飞书发送市场分析报告的功能，用于监控机器人运行状态和市场情况。
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time
import config
from logger_utils import get_logger, notifier


class PeriodicReportScheduler:
    """定期报告调度器"""

    def __init__(self, interval_minutes: int = 120, enabled: bool = True):
        """
        初始化调度器

        Args:
            interval_minutes: 发送间隔（分钟）
            enabled: 是否启用
        """
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.last_report_time = None  # 上次发送时间
        self.start_time = datetime.now()  # 启动时间
        self.report_count = 0  # 已发送报告数
        self.logger = get_logger("periodic_report")

        if self.enabled:
            self.logger.info(f"✅ 定期报告调度器已启用，间隔: {interval_minutes}分钟")
        else:
            self.logger.info("⏭️  定期报告调度器已禁用")

    def should_send_report(self) -> bool:
        """
        判断是否应该发送报告

        Returns:
            bool: True表示应该发送
        """
        if not self.enabled:
            return False

        # 如果从未发送过，应该发送
        if self.last_report_time is None:
            return True

        # 检查是否到达发送时间
        elapsed = datetime.now() - self.last_report_time
        return elapsed.total_seconds() >= self.interval_minutes * 60

    def check_and_send(self, trader, risk_manager) -> bool:
        """
        检查并发送报告（如果需要）

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例

        Returns:
            bool: True表示发送成功
        """
        if not self.should_send_report():
            return False

        return self.send_now(trader, risk_manager)

    def send_now(self, trader, risk_manager) -> bool:
        """
        立即发送报告（用于测试）

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例

        Returns:
            bool: True表示发送成功
        """
        try:
            self.logger.info("📊 定期报告: 开始生成报告")
            start_time = time.time()

            # 创建报告生成器
            generator = MarketReportGenerator(trader, risk_manager)

            # 生成并发送报告
            success = generator.send_report()

            elapsed = time.time() - start_time

            if success:
                self.last_report_time = datetime.now()
                self.report_count += 1
                self.logger.info(f"📊 定期报告: 发送成功 (第{self.report_count}次，耗时{elapsed:.2f}秒)")
                return True
            else:
                self.logger.warning("📊 定期报告: 发送失败")
                return False

        except Exception as e:
            self.logger.error(f"📊 定期报告: 发送异常 - {e}")
            import traceback
            traceback.print_exc()
            return False

    def reset_timer(self):
        """重置计时器"""
        self.last_report_time = None
        self.logger.info("📊 定期报告: 计时器已重置")

    def get_next_report_time(self) -> Optional[datetime]:
        """
        获取下次报告时间

        Returns:
            datetime: 下次报告时间，如果未启用则返回None
        """
        if not self.enabled or self.last_report_time is None:
            return None

        return self.last_report_time + timedelta(minutes=self.interval_minutes)

    def get_time_until_next_report(self) -> Optional[timedelta]:
        """
        获取距离下次报告的时间

        Returns:
            timedelta: 剩余时间，如果未启用则返回None
        """
        next_time = self.get_next_report_time()
        if next_time is None:
            return None

        remaining = next_time - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


class MarketReportGenerator:
    """市场报告生成器"""

    def __init__(self, trader, risk_manager):
        """
        初始化报告生成器

        Args:
            trader: 交易器实例
            risk_manager: 风险管理器实例
        """
        self.trader = trader
        self.risk_manager = risk_manager
        self.logger = get_logger("market_report")

    def generate_report(self) -> Dict[str, Any]:
        """
        生成完整报告数据

        Returns:
            dict: 报告数据字典
        """
        report = {}

        # 收集各模块数据（带降级处理）
        modules = config.PERIODIC_REPORT_MODULES

        if modules.get('system_info', True):
            report['system'] = self._collect_system_info()

        if modules.get('market_info', True):
            report['market'] = self._collect_market_info()

        if modules.get('market_state', True):
            report['market_state'] = self._collect_market_state()

        if modules.get('strategy_info', True):
            report['strategy'] = self._collect_strategy_info()

        if modules.get('position_info', True):
            report['position'] = self._collect_position_info()

        if modules.get('account_info', True):
            report['account'] = self._collect_account_info()

        if modules.get('trade_stats', True):
            report['stats'] = self._collect_trade_stats()

        return report

    def format_message(self, report_data: Dict[str, Any]) -> str:
        """
        格式化报告消息

        Args:
            report_data: 报告数据

        Returns:
            str: 格式化的消息文本
        """
        lines = []

        # 标题
        lines.append("📊 市场分析报告")
        lines.append("━" * 30)
        lines.append("")

        # 系统信息
        if 'system' in report_data:
            sys_info = report_data['system']
            lines.append(f"⏰ 时间: {sys_info.get('timestamp', 'N/A')}")
            lines.append(f"🤖 运行时长: {sys_info.get('uptime', 'N/A')}")
            lines.append("")

        # 市场信息
        if 'market' in report_data:
            market = report_data['market']
            if 'error' not in market:
                lines.append("💹 市场信息")
                lines.append("━" * 30)
                lines.append(f"交易对: {market.get('symbol', 'N/A')}")
                lines.append(f"当前价格: ${market.get('price', 0):,.2f}")

                change_24h = market.get('change_24h', 0)
                change_emoji = "↗️" if change_24h > 0 else "↘️" if change_24h < 0 else "→"
                lines.append(f"24h涨跌: {change_24h:+.2f}% {change_emoji}")

                volume_24h = market.get('volume_24h', 0)
                if volume_24h >= 1_000_000_000:
                    volume_str = f"{volume_24h / 1_000_000_000:.2f}B"
                elif volume_24h >= 1_000_000:
                    volume_str = f"{volume_24h / 1_000_000:.2f}M"
                else:
                    volume_str = f"{volume_24h:,.0f}"
                lines.append(f"24h成交量: {volume_str} USDT")
                lines.append("")

        # 市场状态
        if 'market_state' in report_data:
            state = report_data['market_state']
            if 'error' not in state:
                lines.append("📈 市场状态")
                lines.append("━" * 30)

                state_name = state.get('state', 'UNKNOWN')
                state_map = {
                    'RANGING': '震荡市',
                    'TRENDING': '趋势市',
                    'VOLATILE': '高波动',
                }
                state_cn = state_map.get(state_name, state_name)
                lines.append(f"状态: {state_cn}")
                lines.append(f"置信度: {state.get('confidence', 0)}%")
                lines.append(f"ADX: {state.get('adx', 0):.1f}")
                lines.append(f"布林带宽度: {state.get('bb_width', 0):.2f}%")
                lines.append(f"趋势: {state.get('trend', 'N/A')}")
                lines.append(f"波动率: {state.get('volatility', 'N/A')}")

                tradeable = state.get('tradeable', False)
                tradeable_emoji = "✅" if tradeable else "❌"
                lines.append(f"适合交易: {tradeable_emoji} {'是' if tradeable else '否'}")
                lines.append("")

        # 策略信息
        if 'strategy' in report_data:
            strategy = report_data['strategy']
            lines.append("🎯 策略信息")
            lines.append("━" * 30)

            enabled = strategy.get('enabled', [])
            if enabled:
                lines.append("启用策略:")
                for s in enabled:
                    lines.append(f"  • {s}")
            else:
                lines.append("启用策略: 无")

            reason = strategy.get('reason', '')
            if reason:
                lines.append(f"说明: {reason}")
            lines.append("")

        # 持仓信息
        if 'position' in report_data:
            position = report_data['position']
            lines.append("💼 持仓信息")
            lines.append("━" * 30)

            if position.get('has_position', False):
                side = position.get('side', '')
                side_emoji = "🟢" if side == 'long' else "🔴"
                side_cn = "多单" if side == 'long' else "空单"

                lines.append(f"方向: {side_emoji} {side_cn}")
                lines.append(f"数量: {position.get('amount', 0)} BTC")
                lines.append(f"开仓价: ${position.get('entry_price', 0):,.2f}")
                lines.append(f"当前价: ${position.get('current_price', 0):,.2f}")

                pnl = position.get('pnl', 0)
                pnl_percent = position.get('pnl_percent', 0)
                pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
                lines.append(f"盈亏: {pnl:+.2f} USDT ({pnl_percent:+.2f}%) {pnl_emoji}")

                duration = position.get('duration', 'N/A')
                lines.append(f"持仓时长: {duration}")

                # 风险管理信息
                if 'stop_loss' in position:
                    lines.append("")
                    lines.append("⚠️ 风险管理")
                    lines.append(f"止损价: ${position.get('stop_loss', 0):,.2f}")
                    lines.append(f"止盈价: ${position.get('take_profit', 0):,.2f}")
                    if 'liquidation' in position:
                        lines.append(f"清算价: ${position.get('liquidation', 0):,.2f}")
            else:
                lines.append("当前持仓: 无")

            lines.append("")

        # 账户信息
        if 'account' in report_data:
            account = report_data['account']
            lines.append("💰 账户信息")
            lines.append("━" * 30)
            lines.append(f"可用余额: {account.get('balance', 0):.2f} USDT")

            if 'equity' in account:
                lines.append(f"总权益: {account.get('equity', 0):.2f} USDT")
            if 'margin_used' in account:
                lines.append(f"保证金占用: {account.get('margin_used', 0):.2f} USDT")

            lines.append("")

        # 交易统计
        if 'stats' in report_data:
            stats = report_data['stats']
            lines.append("📊 24h交易统计")
            lines.append("━" * 30)
            lines.append(f"交易次数: {stats.get('trades_24h', 0)}")

            pnl_24h = stats.get('pnl_24h', 0)
            pnl_emoji = "📈" if pnl_24h > 0 else "📉" if pnl_24h < 0 else "➖"
            lines.append(f"盈亏: {pnl_24h:+.2f} USDT {pnl_emoji}")

            last_trade = stats.get('last_trade')
            if last_trade:
                lines.append(f"最近交易: {last_trade.get('time', 'N/A')} - {last_trade.get('side', 'N/A')} {last_trade.get('action', 'N/A')}")

            lines.append("")

        # 结尾
        lines.append("━" * 30)
        lines.append("✅ 系统运行正常")

        return "\n".join(lines)

    def send_report(self) -> bool:
        """
        生成并发送报告

        Returns:
            bool: True表示发送成功
        """
        try:
            # 生成报告数据
            report_data = self.generate_report()

            # 格式化消息
            message = self.format_message(report_data)

            # 发送到飞书
            if config.ENABLE_FEISHU:
                # 使用 feishu 子对象的 send_message 方法
                success = notifier.feishu.send_message(message)
                return success
            else:
                self.logger.warning("飞书通知未启用，跳过发送")
                return False

        except Exception as e:
            self.logger.error(f"报告发送失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ==================== 私有方法：数据收集 ====================

    def _collect_system_info(self) -> Dict[str, Any]:
        """收集系统信息"""
        try:
            now = datetime.now()
            timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

            # 计算运行时长
            if hasattr(self.risk_manager, 'start_time'):
                start_time = self.risk_manager.start_time
            else:
                # 如果没有start_time，使用当前时间作为近似
                start_time = now

            uptime_seconds = (now - start_time).total_seconds()
            uptime = self._format_duration(uptime_seconds)

            return {
                'timestamp': timestamp,
                'uptime': uptime,
                'uptime_seconds': uptime_seconds,
            }
        except Exception as e:
            self.logger.warning(f"系统信息收集失败: {e}")
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'uptime': 'N/A',
            }

    def _collect_market_info(self) -> Dict[str, Any]:
        """收集市场信息"""
        try:
            ticker = self.trader.get_ticker()
            if not ticker:
                return {'error': '数据获取失败'}

            # 获取24小时数据
            price = ticker.get('last', 0)
            change_24h = ticker.get('percentage', 0)
            volume_24h = ticker.get('quoteVolume', 0)

            return {
                'symbol': config.SYMBOL,
                'price': price,
                'change_24h': change_24h,
                'volume_24h': volume_24h,
            }
        except Exception as e:
            self.logger.warning(f"市场信息收集失败: {e}")
            return {'error': '数据获取失败'}

    def _collect_market_state(self) -> Dict[str, Any]:
        """收集市场状态"""
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
                'ranging': 'RANGING',
                'transitioning': 'TRANSITIONING',
                'trending': 'TRENDING',
            }
            state = state_map.get(regime_info.regime.value, 'UNKNOWN')

            # 计算置信度百分比
            confidence = int(regime_info.confidence * 100)

            # 趋势描述
            trend_map = {
                1: '上涨',
                -1: '下跌',
                0: '横盘整理',
            }
            trend = trend_map.get(regime_info.trend_direction, '未知')

            # 波动率等级
            if regime_info.volatility < 0.01:
                volatility = '低'
            elif regime_info.volatility < 0.03:
                volatility = '中等'
            else:
                volatility = '高'

            # 是否适合交易
            tradeable = regime_info.confidence > 0.5

            return {
                'state': state,
                'confidence': confidence,
                'adx': regime_info.adx,
                'bb_width': regime_info.bb_width * 100,  # 转换为百分比
                'trend': trend,
                'volatility': volatility,
                'tradeable': tradeable,
            }
        except Exception as e:
            self.logger.warning(f"市场状态收集失败: {e}")
            return {'error': '数据获取失败'}

    def _collect_strategy_info(self) -> Dict[str, Any]:
        """收集策略信息"""
        try:
            enabled_strategies = config.ENABLE_STRATEGIES

            # 获取推荐策略
            try:
                df = self.trader.get_klines(limit=200)
                if df is not None and not df.empty:
                    from market_regime import MarketRegimeDetector
                    detector = MarketRegimeDetector(df)
                    regime_info = detector.detect()

                    # 根据市场状态推荐策略
                    if regime_info.regime.value == 'ranging':
                        recommended = ['bollinger_breakthrough', 'rsi_divergence', 'kdj_cross']
                        reason = '震荡市 → 使用均值回归策略'
                    elif regime_info.regime.value == 'trending':
                        recommended = ['macd_cross', 'ema_cross', 'adx_trend']
                        reason = '趋势市 → 使用趋势跟踪策略'
                    else:
                        recommended = enabled_strategies
                        reason = '过渡市 → 使用综合策略'
                else:
                    recommended = enabled_strategies
                    reason = ''
            except:
                recommended = enabled_strategies
                reason = ''

            return {
                'enabled': enabled_strategies,
                'recommended': recommended,
                'reason': reason,
            }
        except Exception as e:
            self.logger.warning(f"策略信息收集失败: {e}")
            return {
                'enabled': config.ENABLE_STRATEGIES,
                'recommended': [],
                'reason': '',
            }

    def _collect_position_info(self) -> Dict[str, Any]:
        """收集持仓信息"""
        try:
            positions = self.trader.get_positions()

            if not positions:
                return {'has_position': False}

            # 获取第一个持仓
            pos = positions[0]

            # 获取当前价格
            ticker = self.trader.get_ticker()
            current_price = ticker['last'] if ticker else 0

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

            result = {
                'has_position': True,
                'side': pos['side'],
                'amount': pos['amount'],
                'entry_price': pos['entry_price'],
                'current_price': current_price,
                'pnl': pos['unrealized_pnl'],
                'pnl_percent': pnl_percent,
                'duration': duration,
            }

            # 添加风险管理信息
            if hasattr(self.risk_manager, 'position') and self.risk_manager.position:
                rm_pos = self.risk_manager.position
                result['stop_loss'] = rm_pos.stop_loss_price
                result['take_profit'] = rm_pos.take_profit_price

            # 添加清算价格
            if 'liquidation_price' in pos:
                result['liquidation'] = pos['liquidation_price']

            return result

        except Exception as e:
            self.logger.warning(f"持仓信息收集失败: {e}")
            return {'has_position': False}

    def _collect_account_info(self) -> Dict[str, Any]:
        """收集账户信息"""
        try:
            balance = self.trader.get_balance()

            result = {
                'balance': balance,
            }

            # 如果有持仓，添加权益和保证金信息
            positions = self.trader.get_positions()
            if positions:
                pos = positions[0]
                # 总权益 = 余额 + 未实现盈亏
                equity = balance + pos.get('unrealized_pnl', 0)
                # 保证金占用 = 持仓价值 / 杠杆
                margin_used = (pos['entry_price'] * pos['amount']) / config.LEVERAGE

                result['equity'] = equity
                result['margin_used'] = margin_used

            return result

        except Exception as e:
            self.logger.warning(f"账户信息收集失败: {e}")
            return {'balance': 0}

    def _collect_trade_stats(self) -> Dict[str, Any]:
        """收集交易统计"""
        try:
            from logger_utils import TradeDatabase
            from datetime import datetime, timedelta

            db = TradeDatabase()

            # 获取最近的交易记录
            all_trades = db.get_trades(limit=100)

            # 过滤24小时内的交易
            now = datetime.now()
            cutoff_time = now - timedelta(hours=24)

            trades_24h = []
            for trade in all_trades:
                try:
                    # 解析时间戳
                    trade_time_str = trade.get('created_at') or trade.get('timestamp', '')
                    if trade_time_str:
                        # 尝试解析时间戳
                        try:
                            trade_time = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
                        except:
                            # 如果解析失败，尝试其他格式
                            trade_time = datetime.strptime(trade_time_str, '%Y-%m-%d %H:%M:%S')

                        if trade_time >= cutoff_time:
                            trades_24h.append(trade)
                except:
                    # 如果时间解析失败，跳过这条记录
                    continue

            # 统计交易次数
            trade_count = len(trades_24h)

            # 计算24小时盈亏
            pnl_24h = 0.0
            for trade in trades_24h:
                if trade.get('action') == 'close':
                    pnl_24h += trade.get('pnl', 0)

            # 获取最近一笔交易
            last_trade = None
            if all_trades:
                latest = all_trades[0]
                last_trade = {
                    'time': latest.get('created_at') or latest.get('timestamp', 'N/A'),
                    'side': latest.get('side', 'N/A'),
                    'action': latest.get('action', 'N/A'),
                    'result': 'success',
                }

            return {
                'trades_24h': trade_count,
                'pnl_24h': pnl_24h,
                'last_trade': last_trade,
            }

        except Exception as e:
            self.logger.warning(f"交易统计收集失败: {e}")
            return {
                'trades_24h': 0,
                'pnl_24h': 0.0,
                'last_trade': None,
            }

    # ==================== 辅助方法 ====================

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
