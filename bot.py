import time
import signal
import sys
from datetime import datetime
from typing import Optional, List, Dict

import config
from config_validator import validate_config
from exchange.manager import ExchangeManager
from exchange.legacy_adapter import LegacyAdapter
from risk_manager import RiskManager
from strategies import (
    Signal, TradeSignal,
    get_strategy, analyze_all_strategies, STRATEGY_MAP
)
from market_regime import MarketRegimeDetector
from logger_utils import get_logger, db, notifier, MetricsLogger
from status_monitor import StatusMonitorScheduler
from claude_analyzer import get_claude_analyzer
from claude_periodic_analyzer import get_claude_periodic_analyzer
from trend_filter import get_trend_filter
from direction_filter import get_direction_filter
from indicators import IndicatorCalculator
from shadow_mode import get_shadow_tracker
from claude_guardrails import get_guardrails
from policy_layer import get_policy_layer
from claude_policy_analyzer import get_claude_policy_analyzer
from trading_context_builder import get_context_builder
from ml_predictor import get_ml_predictor  # 原版ML预测器
from ml_predictor_lite import get_ml_predictor_lite  # 优化版ML预测器
from execution_filter import ExecutionFilter  # 执行层风控
from order_health_monitor import get_order_health_monitor  # 订单健康监控

# 套利引擎（可选）
if getattr(config, 'ENABLE_ARBITRAGE', False):
    from arbitrage.engine import ArbitrageEngine

logger = get_logger("bot")


class TradingBot:
    """量化交易机器人"""
    
    def __init__(self):
        # 验证配置
        logger.info("🔍 验证配置...")
        if not validate_config(config):
            raise ValueError("配置验证失败，请检查配置文件")
        logger.info("✅ 配置验证通过")

        # 使用多交易所管理器
        self.exchange_manager = ExchangeManager()
        self.exchange_manager.initialize()
        # 使用适配器包装，解决类型不匹配问题
        raw_exchange = self.exchange_manager.get_current_exchange()
        self.trader = LegacyAdapter(raw_exchange)

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

        # 初始化方向过滤器（解决做多胜率低的问题）
        self.direction_filter = get_direction_filter()

        # 初始化 P0 模块（影子模式、Claude护栏）
        self.shadow_tracker = get_shadow_tracker()
        self.guardrails = get_guardrails()

        # 初始化性能指标记录器（Phase 0）
        self.metrics_logger = MetricsLogger()

        # 初始化 Policy Layer（策略治理层）
        if getattr(config, 'ENABLE_POLICY_LAYER', False):
            self.policy_layer = get_policy_layer()
            self.policy_analyzer = get_claude_policy_analyzer()
            self.context_builder = get_context_builder(self.risk_manager)
            self.last_policy_update = None
            policy_mode = getattr(config, 'POLICY_LAYER_MODE', 'shadow')
            logger.info(f"✅ Policy Layer 已启用 (模式: {policy_mode})")
        else:
            self.policy_layer = None
            self.policy_analyzer = None
            self.context_builder = None
            logger.info("⚠️ Policy Layer 未启用")

        # 初始化 ML 信号过滤器
        if getattr(config, 'ENABLE_ML_FILTER', False):
            # Phase 2: 检查是否强制使用轻量版
            force_lite = getattr(config, 'ML_FORCE_LITE', False)
            use_lite = getattr(config, 'ML_USE_LITE_VERSION', True)

            if force_lite:
                self.ml_predictor = get_ml_predictor_lite()
                version = "优化版（强制）"
                if not use_lite:
                    logger.warning("⚠️ ML_FORCE_LITE已启用，忽略ML_USE_LITE_VERSION=False设置")
            elif use_lite:
                self.ml_predictor = get_ml_predictor_lite()
                version = "优化版"
            else:
                self.ml_predictor = get_ml_predictor()
                version = "原版"

            ml_mode = getattr(config, 'ML_MODE', 'shadow')
            logger.info(f"✅ ML信号过滤器已启用 ({version}, 模式: {ml_mode})")
        else:
            self.ml_predictor = None
            logger.info("⚠️ ML信号过滤器未启用")

        # 初始化执行层风控过滤器
        self.execution_filter = ExecutionFilter()
        logger.info("✅ 执行层风控过滤器已初始化")

        # 初始化订单健康监控器
        if getattr(config, 'ORDER_HEALTH_CHECK_ENABLED', True):
            self.order_health_monitor = get_order_health_monitor(self.trader)
            logger.info("✅ 订单健康监控器已初始化")
        else:
            self.order_health_monitor = None
            logger.info("⚠️ 订单健康监控器未启用")

        # 初始化套利引擎（可选）
        if getattr(config, 'ENABLE_ARBITRAGE', False):
            arbitrage_config = {
                "symbol": getattr(config, 'ARBITRAGE_SYMBOL', 'BTCUSDT'),
                "exchanges": getattr(config, 'ARBITRAGE_EXCHANGES', ['bitget', 'binance', 'okx']),
                "monitor_interval": getattr(config, 'SPREAD_MONITOR_INTERVAL', 1),
                "history_size": getattr(config, 'SPREAD_HISTORY_SIZE', 100),
                "min_spread_threshold": getattr(config, 'MIN_SPREAD_THRESHOLD', 0.3),
                "min_net_profit_threshold": getattr(config, 'MIN_NET_PROFIT_THRESHOLD', 1.0),
                "min_profit_ratio": getattr(config, 'MIN_PROFIT_RATIO', 0.5),
                "opportunity_scan_interval": getattr(config, 'OPPORTUNITY_SCAN_INTERVAL', 2),
                "arbitrage_position_size": getattr(config, 'ARBITRAGE_POSITION_SIZE', 100),
                "max_position_per_exchange": getattr(config, 'MAX_POSITION_PER_EXCHANGE', 500),
                "max_total_arbitrage_exposure": getattr(config, 'MAX_TOTAL_ARBITRAGE_EXPOSURE', 1000),
                "max_position_count_per_exchange": getattr(config, 'MAX_POSITION_COUNT_PER_EXCHANGE', 3),
                "max_arbitrage_per_hour": getattr(config, 'MAX_ARBITRAGE_PER_HOUR', 10),
                "max_arbitrage_per_day": getattr(config, 'MAX_ARBITRAGE_PER_DAY', 50),
                "min_interval_between_arbitrage": getattr(config, 'MIN_INTERVAL_BETWEEN_ARBITRAGE', 30),
                "max_execution_time_per_leg": getattr(config, 'MAX_EXECUTION_TIME_PER_LEG', 10),
                "max_total_execution_time": getattr(config, 'MAX_TOTAL_EXECUTION_TIME', 30),
                "max_slippage_tolerance": getattr(config, 'MAX_SLIPPAGE_TOLERANCE', 0.2),
                "enable_atomic_execution": getattr(config, 'ENABLE_ATOMIC_EXECUTION', True),
                "min_orderbook_depth_multiplier": getattr(config, 'MIN_ORDERBOOK_DEPTH_MULTIPLIER', 3.0),
                "min_orderbook_depth_usdt": getattr(config, 'MIN_ORDERBOOK_DEPTH_USDT', 5000),
                "max_api_latency_ms": getattr(config, 'MAX_API_LATENCY_MS', 500),
                "fee_rates": getattr(config, 'ARBITRAGE_FEE_RATES', {
                    "bitget": {"maker": 0.0002, "taker": 0.0006},
                    "binance": {"maker": 0.0002, "taker": 0.0004},
                    "okx": {"maker": 0.0002, "taker": 0.0005},
                }),
            }
            # 为套利引擎创建独立的 ExchangeManager 实例（避免线程安全问题）
            arbitrage_exchange_manager = ExchangeManager()
            arbitrage_exchange_manager.initialize()
            self.arbitrage_engine = ArbitrageEngine(arbitrage_exchange_manager, arbitrage_config)
            arbitrage_mode = getattr(config, 'ARBITRAGE_MODE', 'conservative')
            logger.info(f"✅ 套利引擎已启用 (模式: {arbitrage_mode}, 独立交易所实例)")
        else:
            self.arbitrage_engine = None
            logger.info("⚠️ 套利引擎未启用")

        # 日志优化：添加计数器以减少冗余日志
        self.no_signal_count = 0  # 无信号计数器
        self.NO_SIGNAL_LOG_INTERVAL = 12  # 每12次（约1分钟）打印一次
        self.last_market_state = None  # 上次市场状态（用于检测变化）
        self.heartbeat_count = 0  # 心跳计数器
        self.HEARTBEAT_INTERVAL = 60  # 每60次循环（约5分钟）打印一次心跳

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
        logger.info(f"开始监控，默认检查间隔: {config.DEFAULT_CHECK_INTERVAL} 秒")
        if config.ENABLE_DYNAMIC_CHECK_INTERVAL:
            logger.info(f"动态价格更新已启用，持仓时检查间隔: {config.POSITION_CHECK_INTERVAL} 秒")

        # 启动套利引擎（如果启用）
        if self.arbitrage_engine:
            self.arbitrage_engine.start()
            logger.info("✅ 套利引擎已启动")

        while self.running:
            try:
                self._main_loop()
            except Exception as e:
                import traceback
                logger.error(f"主循环异常: {e}")
                logger.error(traceback.format_exc())
                notifier.notify_error(str(e))

            # 等待下一次检查 - 动态调整检查间隔
            if self.running:
                # 根据是否有持仓动态调整检查间隔
                if config.ENABLE_DYNAMIC_CHECK_INTERVAL and self.risk_manager.has_position():
                    check_interval = config.POSITION_CHECK_INTERVAL
                else:
                    check_interval = config.DEFAULT_CHECK_INTERVAL

                time.sleep(check_interval)
        
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
        logger.info(f"   移动止损: {config.TRAILING_STOP_PERCENT:.1%}")
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
                current_price = ticker.last if ticker else pos['entry_price']

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
        # Phase 0: 记录循环开始时间
        loop_start = time.time()

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

        current_price = ticker.last

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

                # 场景2：执行30分钟定时分析
                self.claude_periodic_analyzer.check_and_analyze(
                    df, current_price, indicators, position_info
                )

                # 场景3：检查是否需要生成每日报告（每天早上8点）
                if self.claude_periodic_analyzer.should_generate_daily_report():
                    # 获取昨日交易历史
                    trades_history = self._get_yesterday_trades()

                    # 生成每日报告
                    self.claude_periodic_analyzer.generate_daily_report(
                        df, current_price, indicators, position_info, trades_history
                    )

            except Exception as e:
                logger.error(f"Claude定时分析失败: {e}")

        # Policy Layer 定期更新（新增）
        if self.policy_layer and self._should_update_policy():
            try:
                # 计算技术指标（如果还没有计算）
                if 'indicators' not in locals():
                    indicator_calc = IndicatorCalculator(df)
                    indicators = indicator_calc.calculate_all()

                self._update_policy_layer(df, current_price, indicators)
            except Exception as e:
                logger.error(f"Policy Layer 更新失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        if has_position:
            # 有持仓：检查风控和退出信号
            self._check_exit_conditions(df, current_price, positions[0])
        else:
            # 无持仓：检查开仓信号
            self._check_entry_conditions(df, current_price)

        # Phase 0: 记录循环总延迟
        loop_duration = (time.time() - loop_start) * 1000  # 转换为毫秒
        self.metrics_logger.record_latency("main_loop", loop_duration)

    def _get_yesterday_trades(self) -> List[Dict]:
        """
        获取昨日交易历史

        Returns:
            昨日交易列表
        """
        try:
            from datetime import datetime, timedelta
            import pytz

            # 获取昨日日期范围
            tz = pytz.timezone('Asia/Shanghai')
            now = datetime.now(tz)
            yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

            # 从交易历史中筛选昨日交易
            # 注意：这里需要从实际的交易记录中获取，目前返回空列表
            # 如果有交易数据库或日志，可以在这里查询
            trades = []

            # TODO: 从交易记录中查询昨日交易
            # 可能需要从self.trader或其他模块获取交易历史

            return trades

        except Exception as e:
            logger.error(f"获取昨日交易历史失败: {e}")
            return []

    def _check_entry_conditions(self, df, current_price: float):
        """检查开仓条件"""

        # 心跳日志：定期输出系统运行状态
        self.heartbeat_count += 1
        if self.heartbeat_count >= self.HEARTBEAT_INTERVAL:
            # 快速检测市场状态用于心跳日志
            detector_temp = MarketRegimeDetector(df)
            regime_temp = detector_temp.detect()
            logger.info(f"💓 系统运行中 | 价格: {current_price:.2f} | 市场: {regime_temp.regime.value.upper()} | 无持仓")
            self.heartbeat_count = 0

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

            # 仅在市场状态变化时打印日志，减少冗余
            current_state = f"{regime_info.regime.value}_{regime_info.adx:.0f}"
            if current_state != self.last_market_state:
                logger.info(
                    f"市场状态: {regime_info.regime.value.upper()} "
                    f"(ADX={regime_info.adx:.1f}, 宽度={regime_info.bb_width:.2f}%) "
                    f"→ 策略: {', '.join(selected_strategies)}"
                )
                self.last_market_state = current_state
        else:
            # 使用配置文件中的固定策略
            selected_strategies = config.ENABLE_STRATEGIES

        # 运行选定的策略
        signals = analyze_all_strategies(df, selected_strategies)

        # ML信号过滤（如果启用）
        if self.ml_predictor is not None and signals:
            try:
                filtered_signals, predictions = self.ml_predictor.filter_signals(signals, df)

                # 记录过滤结果
                if config.ML_LOG_PREDICTIONS and predictions:
                    for pred in predictions:
                        if not pred['passed'] and config.ML_VERBOSE_LOGGING:
                            logger.info(
                                f"ML过滤: {pred['strategy']} {pred['signal']} "
                                f"质量={pred.get('quality_score', 0):.2f} < {pred['threshold']:.2f}"
                            )

                # 使用过滤后的信号
                signals = filtered_signals

            except Exception as e:
                logger.error(f"ML过滤失败: {e}，使用原始信号")

        # 计算策略一致性（用于方向过滤）
        strategy_agreement = 0.0
        if signals:
            # 统计做多和做空信号的数量
            long_signals = sum(1 for s in signals if s.signal == Signal.LONG)
            short_signals = sum(1 for s in signals if s.signal == Signal.SHORT)
            total_signals = len(signals)

            # 策略一致性 = 主导方向的信号数量 / 总信号数量
            if total_signals > 0:
                strategy_agreement = max(long_signals, short_signals) / total_signals

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

                # 方向过滤检查（对做多信号要求更严格）
                direction_pass, direction_reason = self.direction_filter.filter_signal(
                    trade_signal, df, strategy_agreement
                )
                if not direction_pass:
                    logger.warning(f"❌ 方向过滤拒绝: {direction_reason}")
                    # 影子模式：记录被方向过滤拒绝的信号
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
                        rejection_stage="direction_filter",
                        rejection_reason=direction_reason,
                        trend_details={'pass': True, 'reason': trend_reason}
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

                # 方向过滤检查（对做空信号使用正常标准）
                direction_pass, direction_reason = self.direction_filter.filter_signal(
                    trade_signal, df, strategy_agreement
                )
                if not direction_pass:
                    logger.warning(f"❌ 方向过滤拒绝: {direction_reason}")
                    # 影子模式：记录被方向过滤拒绝的信号
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
                        rejection_stage="direction_filter",
                        rejection_reason=direction_reason,
                        trend_details={'pass': True, 'reason': trend_reason}
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

        # 无信号或所有信号被过滤 - 使用计数器减少日志冗余
        self.no_signal_count += 1
        if self.no_signal_count >= self.NO_SIGNAL_LOG_INTERVAL:
            logger.debug(f"当前价格: {current_price:.2f} - 无有效开仓信号 (已检查{self.no_signal_count}次)")
            self.no_signal_count = 0
    
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

            # 计算波动率（用于动态Maker订单）
            volatility = 0.03  # 默认值
            if df is not None:
                try:
                    volatility = self.risk_manager._calculate_current_volatility(df)
                    logger.debug(f"当前波动率: {volatility:.2%}")
                except Exception as e:
                    logger.warning(f"计算波动率失败: {e}，使用默认值")

            # 执行开仓（传递信号强度和波动率）
            result = self.trader.open_long(
                amount,
                df,
                strategy=signal.strategy,
                reason=signal.reason,
                signal_strength=signal.strength,
                volatility=volatility
            )
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

            # 计算波动率（用于动态Maker订单）
            volatility = 0.03  # 默认值
            if df is not None:
                try:
                    volatility = self.risk_manager._calculate_current_volatility(df)
                    logger.debug(f"当前波动率: {volatility:.2%}")
                except Exception as e:
                    logger.warning(f"计算波动率失败: {e}，使用默认值")

            # 执行开仓（传递信号强度和波动率）
            result = self.trader.open_short(
                amount,
                df,
                strategy=signal.strategy,
                reason=signal.reason,
                signal_strength=signal.strength,
                volatility=volatility
            )
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
            # 注意：不在这里更新风控状态，因为 trader.close_position() 内部已经调用了 record_trade_result()
            # 避免重复记录导致统计错误

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

            # 注意：不在这里记录交易，因为 trader.close_position() 内部已经调用了 db.log_trade()
            # 避免重复记录到数据库

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
        current_price = ticker.last if ticker else 0

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

        # 停止套利引擎（如果启用）
        if self.arbitrage_engine:
            self.arbitrage_engine.stop()
            logger.info("✅ 套利引擎已停止")

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

    def _should_update_policy(self) -> bool:
        """判断是否应该更新 Policy"""
        if not self.last_policy_update:
            # 首次运行，检查是否启用启动时分析
            if getattr(config, 'POLICY_ANALYZE_ON_STARTUP', True):
                return True
            else:
                # 不在启动时分析，设置初始时间
                self.last_policy_update = datetime.now()
                return False

        interval = getattr(config, 'POLICY_UPDATE_INTERVAL', 30) * 60
        elapsed = (datetime.now() - self.last_policy_update).total_seconds()
        return elapsed >= interval

    def _update_policy_layer(self, df, current_price, indicators):
        """更新 Policy Layer"""
        try:
            logger.info("🔄 开始 Policy Layer 更新...")

            # 1. 构建交易上下文
            context = self.context_builder.build_context(df, current_price, indicators)

            # 2. 调用 Claude 进行策略治理分析
            decision = self.policy_analyzer.analyze_for_policy(context, df, indicators)

            if not decision:
                logger.warning("Policy 分析失败，保持当前参数")
                self.last_policy_update = datetime.now()
                return

            # 3. 验证并应用决策
            mode = getattr(config, 'POLICY_LAYER_MODE', 'active')

            if mode == 'shadow':
                # 影子模式：只记录不生效
                logger.info(f"🔍 [Shadow Mode] Policy 决策: {decision.reason}")
                logger.info(f"   市场制度: {decision.regime.value} (置信度: {decision.regime_confidence:.2f})")
                if decision.suggested_risk_mode:
                    logger.info(f"   风控模式建议: {decision.suggested_risk_mode.value}")
                if decision.suggested_stop_loss_pct:
                    logger.info(f"   止损建议: {decision.suggested_stop_loss_pct:.2%}")
                if decision.suggested_take_profit_pct:
                    logger.info(f"   止盈建议: {decision.suggested_take_profit_pct:.2%}")
                if decision.suggested_position_multiplier:
                    logger.info(f"   仓位倍数建议: {decision.suggested_position_multiplier:.2f}x")
                logger.info(f"   [Shadow Mode] 决策已记录但未应用")
            else:
                # 主动模式：真实应用
                success, reason, actions = self.policy_layer.validate_and_apply_decision(decision, context)

                if success:
                    logger.info(f"✅ Policy 决策已应用: {reason}")
                    # 可选：推送到飞书
                    if getattr(config, 'ENABLE_FEISHU', False) and getattr(config, 'CLAUDE_PUSH_TO_FEISHU', False):
                        self._notify_policy_update(decision, actions)
                else:
                    logger.warning(f"⚠️ Policy 决策未应用: {reason}")

            self.last_policy_update = datetime.now()

        except Exception as e:
            logger.error(f"Policy Layer 更新失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def _notify_policy_update(self, decision, actions):
        """通知 Policy 更新（可选）"""
        try:
            message = f"""🤖 Policy Layer 参数更新

市场制度: {decision.regime.value} (置信度: {decision.regime_confidence:.0%})
"""
            if decision.suggested_risk_mode:
                message += f"风控模式: {decision.suggested_risk_mode.value}\n"

            if actions:
                message += f"\n应用的调整:\n"
                for action in actions:
                    action_name = action.value.replace('_', ' ').title()
                    message += f"• {action_name}\n"

            message += f"\n原因: {decision.reason}"

            # 添加当前生效的参数
            params = self.policy_layer.get_current_parameters()
            message += f"\n\n当前参数:"
            message += f"\n• 止损: {params.stop_loss_pct:.2%}"
            message += f"\n• 止盈: {params.take_profit_pct:.2%}"
            message += f"\n• 移动止损: {params.trailing_stop_pct:.2%}"
            message += f"\n• 仓位倍数: {params.position_size_multiplier:.2f}x"
            message += f"\n• 风控模式: {params.risk_mode.value}"

            notifier.feishu.send_message(message)
            logger.debug("Policy 更新通知已发送到飞书")

        except Exception as e:
            logger.error(f"发送 Policy 更新通知失败: {e}")


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
