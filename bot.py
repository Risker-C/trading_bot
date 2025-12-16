import time
import signal
import sys
from datetime import datetime
from typing import Optional

import config
from trader import BitgetTrader
from risk_manager import RiskManager
from strategies import (
    Signal, TradeSignal,
    get_strategy, analyze_all_strategies, STRATEGY_MAP
)
from market_regime import MarketRegimeDetector
from logger_utils import get_logger, db, notifier
from status_monitor import StatusMonitorScheduler
from claude_analyzer import get_claude_analyzer
from claude_periodic_analyzer import get_claude_periodic_analyzer
from trend_filter import get_trend_filter
from indicators import IndicatorCalculator
from shadow_mode import get_shadow_tracker
from claude_guardrails import get_guardrails

logger = get_logger("bot")


class TradingBot:
    """量化交易机器人"""
    
    def __init__(self):
        self.trader = BitgetTrader()
        self.risk_manager = RiskManager(self.trader)
        # 确保trader使用同一个RiskManager实例，避免持仓状态不同步
        self.trader.risk_manager = self.risk_manager
        self.running = False
        self.current_position_side: Optional[str] = None
        self.current_strategy: Optional[str] = None
        self.current_trade_id: Optional[str] = None  # 用于影子模式追踪

        # 初始化状态监控调度器
        if hasattr(config, 'ENABLE_STATUS_MONITOR') and config.ENABLE_STATUS_MONITOR:
            self.status_monitor = StatusMonitorScheduler(
                interval_minutes=config.STATUS_MONITOR_INTERVAL,
                enabled=True
            )
        else:
            self.status_monitor = None

        # 初始化 Claude 定时分析器
        self.claude_periodic_analyzer = get_claude_periodic_analyzer()

        # 初始化 Claude 分析器和趋势过滤器
        self.claude_analyzer = get_claude_analyzer()
        self.trend_filter = get_trend_filter()

        # 初始化 P0 模块（影子模式、Claude护栏）
        self.shadow_tracker = get_shadow_tracker()
        self.guardrails = get_guardrails()

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info("收到退出信号，正在停止...")
        self.running = False
    
    def start(self):
        """启动机器人"""
        logger.info("=" * 50)
        logger.info("🤖 量化交易机器人启动")
        logger.info("=" * 50)

        # 检查交易所连接
        if self.trader.exchange is None:
            logger.error("交易所初始化失败，退出")
            return

        # 显示配置
        self._show_config()
        
        # 显示账户信息
        self._show_account_info()
        
        # 检查现有持仓
        self._check_existing_positions()
        
        # 主循环
        self.running = True
        logger.info(f"开始监控，检查间隔: {config.CHECK_INTERVAL} 秒")
        
        while self.running:
            try:
                self._main_loop()
            except Exception as e:
                import traceback
                logger.error(f"主循环异常: {e}")
                logger.error(traceback.format_exc())
                notifier.notify_error(str(e))
            
            # 等待下一次检查
            if self.running:
                time.sleep(config.CHECK_INTERVAL)
        
        logger.info("机器人已停止")
    
    def _show_config(self):
        """显示配置信息"""
        logger.info("\n📋 当前配置:")
        logger.info(f"   交易对: {config.SYMBOL}")
        logger.info(f"   杠杆: {config.LEVERAGE}x")
        logger.info(f"   保证金模式: {config.MARGIN_MODE}")
        logger.info(f"   仓位比例: {config.POSITION_SIZE_PERCENT:.0%}")
        logger.info(f"   止损: {config.STOP_LOSS_PERCENT:.0%}")
        logger.info(f"   止盈: {config.TAKE_PROFIT_PERCENT:.0%}")
        logger.info(f"   移动止损: {config.TRAILING_STOP_PERCENT:.0%}")
        logger.info(f"   K线周期: {config.TIMEFRAME}")
        logger.info(f"   启用策略: {', '.join(config.ENABLE_STRATEGIES)}")
    
    def _show_account_info(self):
        """显示账户信息"""
        balance = self.trader.get_balance()
        logger.info("\n💰 账户余额:")
        logger.info(f"   可用: {balance:.2f} USDT")

        # 记录余额快照
        db.log_balance_snapshot(balance, balance, 0)
    
    def _check_existing_positions(self):
        """检查现有持仓"""
        positions = self.trader.get_positions()

        if positions:
            logger.info("\n📊 现有持仓:")
            for pos in positions:
                # 获取当前价格
                ticker = self.trader.get_ticker()
                current_price = ticker['last'] if ticker else pos['entry_price']

                # 计算盈亏百分比
                pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount'])) * 100 if pos['amount'] > 0 else 0

                logger.info(f"   {pos['side'].upper()}: {pos['amount']} @ {pos['entry_price']:.2f}")
                logger.info(f"   未实现盈亏: {pos['unrealized_pnl']:.2f} USDT ({pnl_percent:.2f}%)")

                # 初始化风控状态
                self.current_position_side = pos['side']
                self.risk_manager.set_position(
                    side=pos['side'],
                    amount=pos['amount'],
                    entry_price=pos['entry_price']
                )
        else:
            logger.info("\n📊 当前无持仓")
    
    def _main_loop(self):
        """主循环逻辑"""
        # 获取K线数据
        df = self.trader.get_klines()
        if df is None or df.empty:
            logger.warning("获取K线数据失败")
            return

        # 获取当前价格
        ticker = self.trader.get_ticker()
        if not ticker:
            logger.warning("获取行情失败")
            return

        current_price = ticker['last']

        # 更新状态监控的价格历史
        if self.status_monitor:
            self.status_monitor.update_price(current_price)

        # 检查并推送状态监控
        if self.status_monitor:
            try:
                self.status_monitor.check_and_push(self.trader, self.risk_manager)
            except Exception as e:
                logger.error(f"状态监控推送失败: {e}")

        # 获取当前持仓
        positions = self.trader.get_positions()
        has_position = len(positions) > 0

        # 检查并执行Claude定时分析
        if self.claude_periodic_analyzer:
            try:
                # 计算技术指标
                indicator_calc = IndicatorCalculator(df)
                indicators = indicator_calc.calculate_all()

                # 准备持仓信息
                position_info = None
                if has_position:
                    pos = positions[0]
                    pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount'])) * 100 if pos['amount'] > 0 else 0
                    position_info = {
                        'side': pos['side'],
                        'amount': pos['amount'],
                        'entry_price': pos['entry_price'],
                        'unrealized_pnl': pos['unrealized_pnl'],
                        'pnl_percent': pnl_percent
                    }

                # 执行定时分析
                self.claude_periodic_analyzer.check_and_analyze(
                    df, current_price, indicators, position_info
                )
            except Exception as e:
                logger.error(f"Claude定时分析失败: {e}")

        if has_position:
            # 有持仓：检查风控和退出信号
            self._check_exit_conditions(df, current_price, positions[0])
        else:
            # 无持仓：检查开仓信号
            self._check_entry_conditions(df, current_price)
    
    def _check_entry_conditions(self, df, current_price: float):
        """检查开仓条件"""

        # 风控检查
        can_open, reason = self.risk_manager.can_open_position()
        if not can_open:
            logger.debug(f"风控限制: {reason}")
            return

        # 市场状态检测
        detector = MarketRegimeDetector(df)
        regime_info = detector.detect()

        # 检查是否适合交易
        can_trade, trade_reason = detector.should_trade(regime_info)
        if not can_trade:
            logger.debug(f"市场状态不适合交易: {trade_reason}")
            return

        # 根据市场状态动态选择策略
        if hasattr(config, 'USE_DYNAMIC_STRATEGY') and config.USE_DYNAMIC_STRATEGY:
            # 动态策略选择
            selected_strategies = detector.get_suitable_strategies(regime_info)
            logger.info(
                f"市场状态: {regime_info.regime.value.upper()} "
                f"(ADX={regime_info.adx:.1f}, 宽度={regime_info.bb_width:.2f}%) "
                f"→ 策略: {', '.join(selected_strategies)}"
            )
        else:
            # 使用配置文件中的固定策略
            selected_strategies = config.ENABLE_STRATEGIES

        # 运行选定的策略
        signals = analyze_all_strategies(df, selected_strategies)

        # 计算技术指标（用于趋势过滤和 Claude 分析）
        ind = IndicatorCalculator(df)
        indicators = {
            'rsi': ind.rsi().iloc[-1] if len(df) >= 14 else 50,
            'macd': ind.macd()['macd'].iloc[-1] if len(df) >= 26 else 0,
            'macd_signal': ind.macd()['signal'].iloc[-1] if len(df) >= 26 else 0,
            'macd_histogram': ind.macd()['histogram'].iloc[-1] if len(df) >= 26 else 0,
            'ema_short': ind.ema(config.EMA_SHORT).iloc[-1] if len(df) >= config.EMA_SHORT else current_price,
            'ema_long': ind.ema(config.EMA_LONG).iloc[-1] if len(df) >= config.EMA_LONG else current_price,
            'bb_upper': ind.bollinger_bands()['upper'].iloc[-1] if len(df) >= 20 else current_price * 1.02,
            'bb_middle': ind.bollinger_bands()['middle'].iloc[-1] if len(df) >= 20 else current_price,
            'bb_lower': ind.bollinger_bands()['lower'].iloc[-1] if len(df) >= 20 else current_price * 0.98,
            'bb_percent_b': ind.bollinger_bands()['percent_b'].iloc[-1] if len(df) >= 20 else 0.5,
            'adx': ind.adx()['adx'].iloc[-1] if len(df) >= 14 else 20,
            'plus_di': ind.adx()['plus_di'].iloc[-1] if len(df) >= 14 else 25,
            'minus_di': ind.adx()['minus_di'].iloc[-1] if len(df) >= 14 else 25,
            'volume_ratio': ind.volume_ratio().iloc[-1] if len(df) >= 20 else 1.0,
            'trend_direction': ind.trend_direction().iloc[-1] if len(df) >= 21 else 0,
            'trend_strength': ind.trend_strength().iloc[-1] if len(df) >= 21 else 0,
        }

        # 找到第一个有效的开仓信号
        for trade_signal in signals:
            if trade_signal.signal == Signal.LONG:
                # 生成唯一的trade_id用于影子模式追踪
                from datetime import datetime
                trade_id = f"{trade_signal.strategy}_{datetime.now().isoformat()}"

                # 趋势过滤检查
                trend_pass, trend_reason = self.trend_filter.check_signal(df, trade_signal, indicators)
                if not trend_pass:
                    logger.warning(f"❌ 趋势过滤拒绝: {trend_reason}")
                    # 影子模式：记录被趋势过滤拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=False,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="trend_filter",
                        rejection_reason=trend_reason,
                        trend_details={'pass': False, 'reason': trend_reason}
                    )
                    continue

                # Claude护栏：预算和缓存检查
                can_call_claude, budget_reason = self.guardrails.check_budget()
                if not can_call_claude:
                    logger.warning(f"❌ Claude护栏拒绝: {budget_reason}")
                    # 影子模式：记录被护栏拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=True,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="claude_guardrails",
                        rejection_reason=budget_reason,
                        trend_details={'pass': True, 'reason': trend_reason}
                    )
                    continue

                # Claude AI 分析
                claude_pass, claude_reason, claude_details = self.claude_analyzer.analyze_signal(
                    df, current_price, trade_signal, indicators
                )
                if not claude_pass:
                    logger.warning(f"❌ Claude 分析拒绝: {claude_reason}")
                    if claude_details.get('warnings'):
                        for warning in claude_details['warnings']:
                            logger.warning(f"   ⚠️  {warning}")
                    # 影子模式：记录被Claude拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=True,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="claude",
                        rejection_reason=claude_reason,
                        trend_details={'pass': True, 'reason': trend_reason},
                        claude_details=claude_details
                    )
                    continue

                # 通过所有检查，执行开多
                logger.info(f"✅ 信号通过所有检查 (趋势过滤 + Claude AI)")
                # 保存trade_id用于后续平仓时更新影子模式
                self.current_trade_id = trade_id
                # 影子模式：记录通过所有检查的信号
                self.shadow_tracker.record_decision(
                    trade_id=trade_id,
                    price=current_price,
                    market_regime=regime_info.regime.value,
                    volatility=regime_info.volatility,
                    signal=trade_signal,
                    would_execute_strategy=True,
                    would_execute_after_trend=True,
                    would_execute_after_claude=True,
                    would_execute_after_exec=True,
                    final_would_execute=True,
                    trend_details={'pass': True, 'reason': trend_reason},
                    claude_details=claude_details,
                    actually_executed=True,
                    actual_entry_price=current_price
                )
                self._execute_open_long(trade_signal, current_price, df)
                return

            elif trade_signal.signal == Signal.SHORT:
                # 生成唯一的trade_id用于影子模式追踪
                from datetime import datetime
                trade_id = f"{trade_signal.strategy}_{datetime.now().isoformat()}"

                # 趋势过滤检查
                trend_pass, trend_reason = self.trend_filter.check_signal(df, trade_signal, indicators)
                if not trend_pass:
                    logger.warning(f"❌ 趋势过滤拒绝: {trend_reason}")
                    # 影子模式：记录被趋势过滤拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=False,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="trend_filter",
                        rejection_reason=trend_reason,
                        trend_details={'pass': False, 'reason': trend_reason}
                    )
                    continue

                # Claude护栏：预算和缓存检查
                can_call_claude, budget_reason = self.guardrails.check_budget()
                if not can_call_claude:
                    logger.warning(f"❌ Claude护栏拒绝: {budget_reason}")
                    # 影子模式：记录被护栏拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=True,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="claude_guardrails",
                        rejection_reason=budget_reason,
                        trend_details={'pass': True, 'reason': trend_reason}
                    )
                    continue

                # Claude AI 分析
                claude_pass, claude_reason, claude_details = self.claude_analyzer.analyze_signal(
                    df, current_price, trade_signal, indicators
                )
                if not claude_pass:
                    logger.warning(f"❌ Claude 分析拒绝: {claude_reason}")
                    if claude_details.get('warnings'):
                        for warning in claude_details['warnings']:
                            logger.warning(f"   ⚠️  {warning}")
                    # 影子模式：记录被Claude拒绝的信号
                    self.shadow_tracker.record_decision(
                        trade_id=trade_id,
                        price=current_price,
                        market_regime=regime_info.regime.value,
                        volatility=regime_info.volatility,
                        signal=trade_signal,
                        would_execute_strategy=True,
                        would_execute_after_trend=True,
                        would_execute_after_claude=False,
                        would_execute_after_exec=False,
                        final_would_execute=False,
                        rejection_stage="claude",
                        rejection_reason=claude_reason,
                        trend_details={'pass': True, 'reason': trend_reason},
                        claude_details=claude_details
                    )
                    continue

                # 通过所有检查，执行开空
                logger.info(f"✅ 信号通过所有检查 (趋势过滤 + Claude AI)")
                # 保存trade_id用于后续平仓时更新影子模式
                self.current_trade_id = trade_id
                # 影子模式：记录通过所有检查的信号
                self.shadow_tracker.record_decision(
                    trade_id=trade_id,
                    price=current_price,
                    market_regime=regime_info.regime.value,
                    volatility=regime_info.volatility,
                    signal=trade_signal,
                    would_execute_strategy=True,
                    would_execute_after_trend=True,
                    would_execute_after_claude=True,
                    would_execute_after_exec=True,
                    final_would_execute=True,
                    trend_details={'pass': True, 'reason': trend_reason},
                    claude_details=claude_details,
                    actually_executed=True,
                    actual_entry_price=current_price
                )
                self._execute_open_short(trade_signal, current_price, df)
                return

        # 无信号或所有信号被过滤
        logger.debug(f"当前价格: {current_price:.2f} - 无有效开仓信号")
    
    def _check_exit_conditions(self, df, current_price: float, position):
        """检查退出条件"""

        # 使用 RiskManager 的 position 对象进行风控检查
        if not self.risk_manager.position:
            # 如果风控管理器中没有持仓，但交易所有持仓，说明状态不同步
            logger.warning(f"检测到持仓状态不同步: 交易所有持仓({position['side']} {position['amount']})但风控管理器未记录")
            logger.warning("建议手动平仓或重启机器人以同步状态")
            return

        # 1. 检查风控止损止盈
        result = self.risk_manager.check_stop_loss(current_price, self.risk_manager.position, df)
        if result.should_stop:
            logger.warning(f"风控触发: {result.reason}")
            self._execute_close_position(position, result.reason, "risk", current_price)
            return

        # 2. 检查策略退出信号
        if self.current_strategy and self.current_strategy in STRATEGY_MAP:
            strategy = get_strategy(self.current_strategy, df)
            exit_signal = strategy.check_exit(position['side'])

            if exit_signal.signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT]:
                logger.info(f"策略退出信号: {exit_signal.reason}")
                self._execute_close_position(position, exit_signal.reason, "strategy", current_price)
                return

        # 3. 显示持仓状态
        pnl_pct = result.pnl_percent
        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

        logger.info(
            f"持仓中 | {position['side'].upper()} | "
            f"入场: {position['entry_price']:.2f} | "
            f"现价: {current_price:.2f} | "
            f"{pnl_emoji} {pnl_pct:+.2f}%"
        )
    
    def _execute_open_long(self, signal: TradeSignal, current_price: float, df):
        """执行开多"""
        logger.info(f"📈 开多信号 [{signal.strategy}]: {signal.reason}")

        try:
            # 记录信号
            db.log_signal(
                signal.strategy, signal.signal.value,
                signal.reason, signal.strength, signal.confidence, signal.indicators
            )
        except Exception as e:
            logger.error(f"记录信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        try:
            # 计算仓位大小
            balance = self.trader.get_balance()
            amount = self.risk_manager.calculate_position_size(
                balance, current_price, df, signal.strength
            )

            if amount <= 0:
                logger.warning(f"计算的仓位大小无效: {amount}")
                return

            # 执行开仓
            result = self.trader.open_long(amount, df)
        except Exception as e:
            logger.error(f"执行开多失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

        if result:
            self.current_position_side = 'long'
            self.current_strategy = signal.strategy

            # 获取实际成交价格
            positions = self.trader.get_positions()
            entry_price = current_price
            if positions:
                entry_price = positions[0]['entry_price']

            # 发送通知
            notifier.notify_trade(
                'open', config.SYMBOL, 'long',
                amount, entry_price, reason=signal.reason
            )

            logger.info(f"✅ 开多成功: {amount} @ {entry_price:.2f}")
        else:
            logger.error(f"❌ 开多失败")
            notifier.notify_error(f"开多失败")
    
    def _execute_open_short(self, signal: TradeSignal, current_price: float, df):
        """执行开空"""
        logger.info(f"📉 开空信号 [{signal.strategy}]: {signal.reason}")

        try:
            # 记录信号
            db.log_signal(
                signal.strategy, signal.signal.value,
                signal.reason, signal.strength, signal.confidence, signal.indicators
            )
        except Exception as e:
            logger.error(f"记录信号失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        try:
            # 计算仓位大小
            balance = self.trader.get_balance()
            amount = self.risk_manager.calculate_position_size(
                balance, current_price, df, signal.strength
            )

            if amount <= 0:
                logger.warning(f"计算的仓位大小无效: {amount}")
                return

            # 执行开仓
            result = self.trader.open_short(amount, df)
        except Exception as e:
            logger.error(f"执行开空失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

        if result:
            self.current_position_side = 'short'
            self.current_strategy = signal.strategy

            # 获取实际成交价格
            positions = self.trader.get_positions()
            entry_price = current_price
            if positions:
                entry_price = positions[0]['entry_price']

            # 发送通知
            notifier.notify_trade(
                'open', config.SYMBOL, 'short',
                amount, entry_price, reason=signal.reason
            )

            logger.info(f"✅ 开空成功: {amount} @ {entry_price:.2f}")
        else:
            logger.error(f"❌ 开空失败")
            notifier.notify_error(f"开空失败")
    
    def _execute_close_position(self, position, reason: str, trigger_type: str, current_price: float):
        """执行平仓"""
        logger.info(f"📤 平仓触发 [{trigger_type}]: {reason}")

        # 计算盈亏
        entry_price = position['entry_price']
        amount = position['amount']

        if position['side'] == 'long':
            pnl = (current_price - entry_price) * amount
        else:
            pnl = (entry_price - current_price) * amount

        # 执行平仓（使用统一的 close_position 方法，传递持仓数据）
        success = self.trader.close_position(reason, position_data=position)

        # 计算盈亏百分比
        pnl_percent = (pnl / (entry_price * amount)) * 100 * config.LEVERAGE

        if success:
            # 更新风控状态
            self.risk_manager.record_trade_result(pnl)

            # 影子模式：更新实际交易结果
            if self.current_trade_id:
                self.shadow_tracker.update_actual_result(
                    trade_id=self.current_trade_id,
                    exit_price=current_price,
                    pnl=pnl,
                    pnl_pct=pnl_percent
                )

            # 重置当前持仓信息
            self.current_position_side = None
            self.current_strategy = None
            self.current_trade_id = None  # 重置trade_id

            # 记录交易
            db.log_trade(
                config.SYMBOL, position['side'], 'close',
                amount, current_price,
                order_id="",  # close_position 方法返回布尔值，没有order_id
                value_usdt=amount * current_price,
                pnl=pnl, pnl_percent=pnl_percent,
                strategy=self.current_strategy or "", reason=reason
            )

            # 记录风控事件
            db.log_risk_event(
                trigger_type, reason,
                current_price, entry_price, position['side']
            )

            # 发送通知
            notifier.notify_trade(
                'close', config.SYMBOL, position['side'],
                amount, current_price, pnl=pnl, reason=reason
            )

            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            logger.info(f"✅ 平仓成功: {amount} @ {current_price:.2f} | {pnl_emoji} {pnl:+.2f} USDT ({pnl_percent:+.2f}%)")
        else:
            logger.error(f"❌ 平仓失败")
            # 如果平仓失败（可能是交易所已经没有持仓），清除风控管理器的持仓状态
            if self.risk_manager.position:
                logger.warning("检测到平仓失败，清除风控管理器的持仓状态以避免重复尝试")
                self.risk_manager.position = None
                self.current_position_side = None
                self.current_trade_id = None  # 重置trade_id
                self.current_strategy = None
            notifier.notify_error(f"平仓失败")
    
    def get_status(self) -> dict:
        """获取机器人状态"""
        balance = self.trader.get_balance()
        positions = self.trader.get_positions()
        risk_status = self.risk_manager.get_status()

        # 获取当前价格用于计算盈亏百分比
        ticker = self.trader.get_ticker()
        current_price = ticker['last'] if ticker else 0

        return {
            'running': self.running,
            'balance': balance,
            'positions': [
                {
                    'side': p['side'],
                    'amount': p['amount'],
                    'entry_price': p['entry_price'],
                    'current_price': current_price,
                    'pnl': p['unrealized_pnl'],
                    'pnl_percent': (p['unrealized_pnl'] / (p['entry_price'] * p['amount']) * 100 * config.LEVERAGE) if p['entry_price'] > 0 and p['amount'] > 0 else 0,
                }
                for p in positions
            ],
            'risk': risk_status,
            'current_strategy': self.current_strategy,
        }
    
    def stop(self):
        """停止机器人"""
        self.running = False
        logger.info("机器人停止中...")
    
    def close_all(self):
        """紧急平仓"""
        logger.warning("执行紧急平仓")
        results = self.trader.close_all_positions()
        
        for result in results:
            if result.success:
                logger.info(f"平仓成功: {result.order_id}")
            else:
                logger.error(f"平仓失败: {result.error}")
        
        return results


def main():
    """主函数"""
    bot = TradingBot()
    
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        notifier.notify_error(str(e))
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    main()
