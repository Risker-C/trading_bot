import time
import asyncio
import signal
import sys
import json
import os
from datetime import datetime
from typing import Optional, List, Dict

import pandas as pd

from config.settings import settings as config
from config.validator import validate_config
from exchange.manager import ExchangeManager
from exchange.legacy_adapter import LegacyAdapter
from risk.risk_manager import RiskManager
from strategies.strategies import (
    Signal, TradeSignal,
    get_strategy, analyze_all_strategies, STRATEGY_MAP,
    BandLimitedHedgingStrategy
)
from strategies.market_regime import MarketRegimeDetector
from utils.logger_utils import get_logger, db, notifier, MetricsLogger
from monitoring.status_monitor import StatusMonitorScheduler
from ai.claude_analyzer import get_claude_analyzer
from ai.claude_periodic_analyzer import get_claude_periodic_analyzer
from strategies.trend_filter import get_trend_filter
from strategies.direction_filter import get_direction_filter
from strategies.indicators import IndicatorCalculator
from core.shadow_mode import get_shadow_tracker
from ai.claude_guardrails import get_guardrails
from ai.policy_layer import get_policy_layer
from ai.claude_policy_analyzer import get_claude_policy_analyzer
from core.trading_context_builder import get_context_builder
from ai.ml_predictor import get_ml_predictor  # 原版ML预测器
from ai.ml_predictor_lite import get_ml_predictor_lite  # 优化版ML预测器
from risk.execution_filter import ExecutionFilter  # 执行层风控
from monitoring.order_health_monitor import get_order_health_monitor  # 订单健康监控

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

        # Band-Limited Hedging 模式状态
        self.is_band_limited_mode: bool = False
        self.band_limited_strategy = None
        self.band_limited_params: Dict = {
            "MES": 0.009,  # 9 * fee_rate (与回测系统一致)
            "alpha": 0.5,
            "base_position_ratio": 0.95,
            "min_rebalance_profit": 0.0,
            "min_rebalance_profit_ratio": 1.0,
            "fee_rate": 0.001,
            "eta": 0.2,
            "exit_mes_ratio": 0.7,
            "exit_sigma_k": 0.01,
            "exit_sigma_consecutive": 10,
        }

        # 小额订单累积器 (用于解决低于最小下单量的问题)
        self.pending_orders_file = "data/pending_orders.json"
        self.pending_orders: Dict[str, float] = {"long": 0.0, "short": 0.0}
        self.pending_close_orders: Dict[str, float] = {"long": 0.0, "short": 0.0}
        self._load_pending_orders()  # 从文件加载累积订单

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
        self.cycle_count = 0  # Phase 4: 循环计数器，用于定期内存监控

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

        # 初始化 Band-Limited Hedging 模式
        self._init_band_limited_mode()

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info("收到退出信号，正在停止...")
        self.running = False

    def _init_band_limited_mode(self):
        """检测并初始化 Band-Limited Hedging 模式"""
        strategies = getattr(config, 'ENABLE_STRATEGIES', [])
        logger.info(f"🔍 检测策略配置: {strategies}")

        if "band_limited_hedging" not in strategies:
            logger.info("未启用 Band-Limited Hedging 策略")
            return

        # 检查是否为单策略模式
        if len(strategies) > 1:
            logger.warning(f"Band-Limited Hedging 需要单策略模式运行，当前配置了多个策略: {strategies}")
            return

        self.is_band_limited_mode = True

        # 从配置覆盖默认参数
        config_params = getattr(config, 'BAND_LIMITED_PARAMS', {})
        for key, value in config_params.items():
            if key in self.band_limited_params:
                self.band_limited_params[key] = value

        logger.info("✅ Band-Limited Hedging 模式已启用")
        logger.info(f"   参数: MES={self.band_limited_params['MES']}, "
                    f"alpha={self.band_limited_params['alpha']}, "
                    f"base_ratio={self.band_limited_params['base_position_ratio']}")
    
    def start(self):
        """启动机器人"""
        # 检查是否启用异步主循环
        if getattr(config, 'USE_ASYNC_MAIN_LOOP', False):
            logger.info("检测到异步主循环配置，使用异步模式启动")
            # 使用 asyncio.run() 启动异步版本
            try:
                asyncio.run(self.start_async())
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在停止...")
                self.stop()
            return
        
        # 原有同步启动逻辑
        logger.info("=" * 50)
        logger.info("🤖 量化交易机器人启动")
        logger.info("=" * 50)

        # 检查交易所连接
        if self.trader is None or not self.trader.is_connected():
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

        consecutive_errors = 0
        max_consecutive_errors = getattr(config, 'MAX_CONSECUTIVE_ERRORS', 5)
        error_backoff_seconds = getattr(config, 'ERROR_BACKOFF_SECONDS', 10)

        while self.running:
            try:
                self._main_loop()
                consecutive_errors = 0  # 成功执行，重置错误计数
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在停止...")
                break
            except Exception as e:
                import traceback
                consecutive_errors += 1
                logger.error(f"主循环异常 (连续错误: {consecutive_errors}/{max_consecutive_errors}): {e}")
                logger.error(traceback.format_exc())

                # 通知错误
                try:
                    notifier.notify_error(f"主循环异常: {str(e)}")
                except Exception as notify_err:
                    logger.warning(f"通知发送失败: {notify_err}")

                # 检查是否超过最大连续错误次数
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"连续错误次数达到上限 ({max_consecutive_errors})，停止机器人")
                    self.running = False
                    break

                # 错误退避：等待一段时间后重试
                backoff_time = error_backoff_seconds * consecutive_errors
                logger.warning(f"等待 {backoff_time} 秒后重试...")
                time.sleep(backoff_time)
                continue


            # 刷新数据库缓冲区
            try:
                db.flush_buffers()
            except Exception as e:
                logger.error(f"刷新数据库缓冲区失败: {e}")
            # 等待下一次检查 - 动态调整检查间隔
            if self.running:
                # 根据是否有持仓动态调整检查间隔
                if config.ENABLE_DYNAMIC_CHECK_INTERVAL and self.risk_manager.has_position():
                    check_interval = config.POSITION_CHECK_INTERVAL
                else:
                    check_interval = config.DEFAULT_CHECK_INTERVAL

                time.sleep(check_interval)
        
        logger.info("机器人已停止")
    

    async def start_async(self):
        """启动机器人（异步版本）"""
        logger.info("=" * 50)
        logger.info("🤖 量化交易机器人启动 (异步模式)")
        logger.info("=" * 50)

        # 检查交易所连接
        if self.trader is None or not self.trader.is_connected():
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

        # 记录异步模式启动时间
        async_start_time = time.time()

        while self.running:
            try:
                await self._main_loop_async()
            except Exception as e:
                import traceback
                logger.error(f"主循环异常: {e}")
                logger.error(traceback.format_exc())
                notifier.notify_error(str(e))

            
            # 刷新数据库缓冲区
            try:
                db.flush_buffers()
            except Exception as e:
                logger.error(f"刷新数据库缓冲区失败: {e}")
            
            # 等待下一次检查 - 动态调整检查间隔（使用异步sleep）
            if self.running:
                # 根据是否有持仓动态调整检查间隔
                if config.ENABLE_DYNAMIC_CHECK_INTERVAL and self.risk_manager.has_position():
                    check_interval = config.POSITION_CHECK_INTERVAL
                else:
                    check_interval = config.DEFAULT_CHECK_INTERVAL

                await asyncio.sleep(check_interval)
        
        # 记录异步模式运行时长
        async_duration = time.time() - async_start_time
        logger.info(f"异步模式运行时长: {async_duration:.2f}秒")
        logger.info("机器人已停止")


    async def _main_loop_async(self):
        """主循环逻辑（异步版本）"""
        # Phase 0: 记录循环开始时间
        loop_start = time.time()

        # Phase 4: 增加循环计数器
        self.cycle_count += 1

        # Phase 4: 每10个循环周期记录一次内存使用
        if self.cycle_count % 10 == 0:
            try:
                mem_usage = self.metrics_logger.get_memory_usage()
                logger.debug(f"[异步] 内存使用: RSS={mem_usage.get('rss', 0):.1f}MB")
            except Exception as e:
                logger.debug(f"获取内存使用失败: {e}")
        
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

        # Band-Limited Hedging 模式：使用专门的循环逻辑
        if self.is_band_limited_mode:
            self._run_band_limited_cycle(df, current_price)
            # Phase 0: 记录循环总延迟
            loop_duration = (time.time() - loop_start) * 1000
            self.metrics_logger.record_latency("main_loop_async", loop_duration)
            if self.cycle_count % 50 == 0:
                logger.info(f"[异步模式-Band-Limited] 第 {self.cycle_count} 次循环完成，耗时: {loop_duration:.2f}ms")
            return

        if has_position:
            # 有持仓：检查风控和退出信号
            self._check_exit_conditions(df, current_price, positions[0])
        else:
            # 无持仓：检查开仓信号
            self._check_entry_conditions(df, current_price)

        # Phase 0: 记录循环总延迟
        loop_duration = (time.time() - loop_start) * 1000  # 转换为毫秒
        self.metrics_logger.record_latency("main_loop_async", loop_duration)

        # 记录性能对比日志
        if self.cycle_count % 50 == 0:
            logger.info(f"[异步模式] 第 {self.cycle_count} 次循环完成，耗时: {loop_duration:.2f}ms")

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

        # Band-Limited 模式：处理双向持仓
        if self.is_band_limited_mode:
            self._check_existing_band_limited_positions(positions)
            return

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

    def _check_existing_band_limited_positions(self, positions: List[Dict]):
        """检查并恢复 Band-Limited 双向持仓"""
        long_pos = None
        short_pos = None

        for pos in positions:
            if pos['side'] == 'long':
                long_pos = pos
            elif pos['side'] == 'short':
                short_pos = pos

        if long_pos or short_pos:
            logger.info("\n📊 [Band-Limited] 现有持仓:")
            if long_pos:
                pnl_pct = (long_pos['unrealized_pnl'] / (long_pos['entry_price'] * long_pos['amount'])) * 100 if long_pos['amount'] > 0 else 0
                logger.info(f"   LONG: {long_pos['amount']:.6f} @ {long_pos['entry_price']:.2f} (PnL: {pnl_pct:+.2f}%)")
            if short_pos:
                pnl_pct = (short_pos['unrealized_pnl'] / (short_pos['entry_price'] * short_pos['amount'])) * 100 if short_pos['amount'] > 0 else 0
                logger.info(f"   SHORT: {short_pos['amount']:.6f} @ {short_pos['entry_price']:.2f} (PnL: {pnl_pct:+.2f}%)")
            logger.info("   策略将在首次循环时同步状态")
        else:
            logger.info("\n📊 [Band-Limited] 当前无持仓 - 将初始化双向持仓")
    
    def _main_loop(self):
        """主循环逻辑"""
        # Phase 0: 记录循环开始时间
        loop_start = time.time()


        # Phase 4: 增加循环计数器
        self.cycle_count += 1

        # Phase 4: 每10个循环周期记录一次内存使用
        if self.cycle_count % 10 == 0:
            try:
                mem_usage = self.metrics_logger.get_memory_usage()
                logger.debug(f"内存使用: RSS={mem_usage.get('rss', 0):.1f}MB")
            except Exception as e:
                logger.debug(f"获取内存使用失败: {e}")
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

        # Band-Limited Hedging 模式：使用专门的循环逻辑
        if self.is_band_limited_mode:
            self._run_band_limited_cycle(df, current_price)
            # Phase 0: 记录循环总延迟
            loop_duration = (time.time() - loop_start) * 1000
            self.metrics_logger.record_latency("main_loop", loop_duration)
            return

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

        # Band-Limited 模式下，过滤掉通用策略列表中的 band_limited_hedging
        # 该策略有专用循环 _run_band_limited_cycle()，不应通过通用路径创建实例
        if self.is_band_limited_mode:
            selected_strategies = [s for s in selected_strategies if s != "band_limited_hedging"]

        # 运行选定的策略（如果有）
        signals = []
        if selected_strategies:
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
            db.log_signal_buffered(
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
            db.log_signal_buffered(
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

    def _execute_band_limited_actions(self, actions: List[Dict], current_price: float) -> bool:
        """
        执行 Band-Limited 策略的 actions 列表

        Actions 格式:
        {
            "side": "long" | "short",
            "action": "open" | "close",
            "qty": float,
            "price": float,
            "fee": float,
            "pnl": float,  # 仅 close 操作有值
            "reason": str
        }
        """
        if not actions:
            return True

        success_count = 0
        for action in actions:
            side = action.get("side")
            action_type = action.get("action")
            qty = action.get("qty", 0)
            reason = action.get("reason", "")

            if qty <= 0:
                continue

            try:
                if action_type == "open":
                    result = self._execute_band_limited_open(side, qty, current_price, reason)
                elif action_type == "close":
                    result = self._execute_band_limited_close(side, qty, current_price, reason, action)
                else:
                    logger.warning(f"未知的 action 类型: {action_type}")
                    continue

                if result:
                    success_count += 1

            except Exception as e:
                logger.error(f"执行 action 失败 {action}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue

        return success_count > 0

    def _execute_band_limited_open(self, side: str, qty: float, price: float, reason: str) -> bool:
        """执行 Band-Limited 策略的开仓操作"""
        # 验证 side 参数
        if side not in ("long", "short"):
            logger.error(f"[Band-Limited] 无效的 side 参数: {side}")
            return False

        # 获取交易所最小下单量
        min_amount = self._get_min_order_amount()

        # 如果订单量低于最小值，累积到待处理订单
        if qty < min_amount:
            self.pending_orders[side] += qty
            self._save_pending_orders()  # 持久化累积订单
            logger.info(f"[Band-Limited] 开{side}仓数量 {qty:.6f} 低于最小量 {min_amount:.6f}，累积到待处理订单 (当前累积: {self.pending_orders[side]:.6f})")

            # 检查累积量是否达到最小下单量
            if self.pending_orders[side] >= min_amount:
                actual_qty = self.pending_orders[side]
                logger.info(f"[Band-Limited] 累积订单达到最小量，执行开{side}仓: {actual_qty:.6f}")
                result = self._execute_band_limited_open_internal(side, actual_qty, price, reason)
                # 只有成功执行后才清空累积
                if result:
                    self.pending_orders[side] = 0.0
                    self._save_pending_orders()  # 持久化清空状态
                return result
            else:
                return False

        # 订单量足够，直接执行
        return self._execute_band_limited_open_internal(side, qty, price, reason)

    def _execute_band_limited_open_internal(self, side: str, qty: float, price: float, reason: str) -> bool:
        """内部方法：实际执行开仓操作"""
        logger.info(f"[Band-Limited] 开{side}仓: {qty:.6f} @ {price:.2f} - {reason}")

        try:
            # 记录信号
            db.log_signal_buffered(
                "band_limited_hedging", f"open_{side}",
                reason, 1.0, 1.0, {}
            )
        except Exception as e:
            logger.error(f"记录信号失败: {e}")

        try:
            if side == "long":
                result = self.trader.open_long(
                    qty,
                    strategy="band_limited_hedging",
                    reason=reason
                )
            else:
                result = self.trader.open_short(
                    qty,
                    strategy="band_limited_hedging",
                    reason=reason
                )

            if result:
                notifier.notify_trade('open', config.SYMBOL, side, qty, price, reason=reason)
                logger.info(f"✅ [Band-Limited] 开{side}仓成功")
            else:
                logger.error(f"❌ [Band-Limited] 开{side}仓失败")

            return result

        except Exception as e:
            logger.error(f"执行开{side}仓失败: {e}")
            return False

    def _get_min_order_amount(self) -> float:
        """获取交易所最小下单量"""
        # 从配置中获取
        exchange_config = config.EXCHANGES_CONFIG.get(config.ACTIVE_EXCHANGE, {})
        min_amount = exchange_config.get("min_amount", 0.01)
        return min_amount

    def _execute_band_limited_close(self, side: str, qty: float, price: float, reason: str, action: Dict) -> bool:
        """执行 Band-Limited 策略的平仓操作"""
        # 验证 side 参数
        if side not in ("long", "short"):
            logger.error(f"[Band-Limited] 无效的 side 参数: {side}")
            return False

        pnl = action.get("pnl", 0)
        fee = action.get("fee", 0)
        net_pnl = pnl - fee

        # 获取交易所最小下单量
        min_amount = self._get_min_order_amount()

        # 如果平仓量低于最小值，累积到待处理平仓订单
        if qty < min_amount:
            self.pending_close_orders[side] += qty
            self._save_pending_orders()  # 持久化累积订单
            logger.info(f"[Band-Limited] 平{side}仓数量 {qty:.6f} 低于最小量 {min_amount:.6f}，累积到待处理订单 (当前累积: {self.pending_close_orders[side]:.6f})")

            # 检查累积量是否达到最小下单量
            if self.pending_close_orders[side] >= min_amount:
                actual_qty = self.pending_close_orders[side]
                logger.info(f"[Band-Limited] 累积平仓订单达到最小量，执行平{side}仓: {actual_qty:.6f}")
                result = self._execute_band_limited_close_internal(side, actual_qty, price, reason, net_pnl)
                # 只有成功执行后才清空累积
                if result:
                    self.pending_close_orders[side] = 0.0
                    self._save_pending_orders()  # 持久化清空状态
                return result
            else:
                return False

        # 订单量足够，直接执行
        return self._execute_band_limited_close_internal(side, qty, price, reason, net_pnl)

    def _execute_band_limited_close_internal(self, side: str, qty: float, price: float, reason: str, net_pnl: float) -> bool:
        """内部方法：实际执行平仓操作"""
        logger.info(f"[Band-Limited] 平{side}仓: {qty:.6f} @ {price:.2f} - {reason} (PnL: {net_pnl:+.2f})")

        try:
            # 获取持仓均价
            entry_price = price
            if self.band_limited_strategy and self.band_limited_strategy.state:
                entry_price = self.band_limited_strategy.state.get(f"{side}_avg", price)

            # 构造持仓数据
            position_data = {
                'side': side,
                'amount': qty,
                'entry_price': entry_price,
            }

            result = self.trader.close_position(reason=reason, position_data=position_data)

            if result:
                notifier.notify_trade('close', config.SYMBOL, side, qty, price, pnl=net_pnl, reason=reason)
                pnl_emoji = "🟢" if net_pnl >= 0 else "🔴"
                logger.info(f"✅ [Band-Limited] 平{side}仓成功 | {pnl_emoji} {net_pnl:+.2f} USDT")
            else:
                logger.error(f"❌ [Band-Limited] 平{side}仓失败")

                # 平仓失败时，检查交易所实际持仓状态
                try:
                    positions = self.trader.get_positions()
                    has_position = any(p.get('side') == side for p in positions) if positions else False

                    if not has_position:
                        # 交易所确实没有该侧持仓，同步策略内部状态
                        if self.band_limited_strategy and self.band_limited_strategy.state:
                            old_qty = self.band_limited_strategy.state.get(f"{side}_qty", 0)
                            self.band_limited_strategy.state[f"{side}_qty"] = 0.0
                            logger.warning(
                                f"⚠️ [Band-Limited] 检测到交易所无{side}持仓，已同步策略状态 "
                                f"({old_qty:.6f} → 0.0)"
                            )
                            # 如果双边都没有持仓，重置参考价格
                            if (self.band_limited_strategy.state.get("long_qty", 0) == 0 and
                                self.band_limited_strategy.state.get("short_qty", 0) == 0):
                                self.band_limited_strategy.state["p_ref"] = None
                                logger.warning("⚠️ [Band-Limited] 双边持仓已清空，重置参考价格")
                except Exception as sync_error:
                    logger.error(f"同步策略状态失败: {sync_error}")

            return result

        except Exception as e:
            logger.error(f"执行平{side}仓失败: {e}")
            return False

    def _run_band_limited_cycle(self, df: pd.DataFrame, current_price: float):
        """
        运行一个 Band-Limited Hedging 策略循环
        与 backtest/engine.py:_run_band_limited() 保持一致
        """
        # 首次运行：初始化策略实例
        if self.band_limited_strategy is None:
            self._initialize_band_limited_strategy(df)
            # 只有在没有现有持仓时才执行初始化建仓
            if self.band_limited_strategy.state["p_ref"] is None:
                signal = self.band_limited_strategy.analyze()
                if signal and isinstance(signal.indicators, dict):
                    actions = signal.indicators.get("actions", []) or []
                    if actions:
                        logger.info(f"[Band-Limited] 执行初始化建仓: {len(actions)} 个操作")
                        self._execute_band_limited_actions(actions, current_price)
            return

        # 更新策略窗口 (与 backtest/engine.py:226-229 一致)
        if hasattr(self.band_limited_strategy, "update_window"):
            self.band_limited_strategy.update_window(df)
        else:
            self.band_limited_strategy.df = df

        # 获取信号 (与 backtest/engine.py:230 一致)
        signal = self.band_limited_strategy.analyze()

        # 提取 actions (与 backtest/engine.py:232-233 一致)
        actions = []
        if signal and isinstance(signal.indicators, dict):
            actions = signal.indicators.get("actions", []) or []

        # 获取策略状态用于日志
        state = signal.indicators.get("state", {}) if signal else {}
        mode = state.get("mode", "unknown")
        long_qty = state.get("long_qty", 0)
        short_qty = state.get("short_qty", 0)
        p_ref = state.get("p_ref", 0)

        # 执行 actions
        if actions:
            logger.info(
                f"[Band-Limited] 模式: {mode.upper()} | "
                f"价格: {current_price:.2f} (参考: {p_ref:.2f}) | "
                f"Long: {long_qty:.6f} | Short: {short_qty:.6f} | "
                f"Actions: {len(actions)}"
            )
            self._execute_band_limited_actions(actions, current_price)
        else:
            # 心跳日志
            self.heartbeat_count += 1
            if self.heartbeat_count >= self.HEARTBEAT_INTERVAL:
                logger.info(
                    f"💓 [Band-Limited] 模式: {mode.upper()} | "
                    f"价格: {current_price:.2f} | "
                    f"Long: {long_qty:.6f} | Short: {short_qty:.6f} | "
                    f"{signal.reason if signal else 'No signal'}"
                )
                self.heartbeat_count = 0

    def _initialize_band_limited_strategy(self, df: pd.DataFrame):
        """
        初始化 Band-Limited 策略实例
        与 backtest/engine.py:219 保持一致
        """
        # 获取初始资金
        balance = self.trader.get_balance()

        # 准备参数
        params = dict(self.band_limited_params)
        params["initial_capital"] = balance
        params["E_max"] = balance
        params["leverage"] = config.LEVERAGE  # 传递杠杆倍数

        # 创建策略实例 (与 backtest/engine.py:219 一致)
        self.band_limited_strategy = get_strategy("band_limited_hedging", df, **params)

        logger.info(f"[Band-Limited] 策略已初始化")
        logger.info(f"   初始资金: {balance:.2f} USDT")
        logger.info(f"   杠杆: {config.LEVERAGE}x")
        logger.info(f"   MES: {params['MES']}")
        logger.info(f"   alpha: {params['alpha']}")
        logger.info(f"   base_position_ratio: {params['base_position_ratio']}")
        logger.info(f"   min_rebalance_profit: {params['min_rebalance_profit']}")
        logger.info(f"   min_rebalance_profit_ratio: {params['min_rebalance_profit_ratio']}")

        # 检查并恢复现有持仓状态
        self._restore_band_limited_positions()

    def _restore_band_limited_positions(self):
        """恢复现有的 Band-Limited 双向持仓到策略状态"""
        try:
            positions = self.trader.get_positions()
            long_pos = None
            short_pos = None

            for pos in positions:
                if pos['side'] == 'long':
                    long_pos = pos
                elif pos['side'] == 'short':
                    short_pos = pos

            if long_pos or short_pos:
                logger.info("[Band-Limited] 检测到现有持仓，恢复策略状态")

                if long_pos:
                    self.band_limited_strategy.state["long_qty"] = float(long_pos['amount'])
                    self.band_limited_strategy.state["long_avg"] = float(long_pos['entry_price'])
                    logger.info(f"   恢复 LONG 持仓: {long_pos['amount']:.6f} @ {long_pos['entry_price']:.2f}")

                if short_pos:
                    self.band_limited_strategy.state["short_qty"] = float(short_pos['amount'])
                    self.band_limited_strategy.state["short_avg"] = float(short_pos['entry_price'])
                    logger.info(f"   恢复 SHORT 持仓: {short_pos['amount']:.6f} @ {short_pos['entry_price']:.2f}")

                # 设置参考价格（使用现有持仓均价的平均值）
                if long_pos and short_pos:
                    avg_entry = (float(long_pos['entry_price']) + float(short_pos['entry_price'])) / 2
                    self.band_limited_strategy.state["p_ref"] = avg_entry
                    logger.info(f"   设置参考价格: {avg_entry:.2f}")
                elif long_pos:
                    self.band_limited_strategy.state["p_ref"] = float(long_pos['entry_price'])
                    logger.info(f"   设置参考价格: {long_pos['entry_price']:.2f}")
                elif short_pos:
                    self.band_limited_strategy.state["p_ref"] = float(short_pos['entry_price'])
                    logger.info(f"   设置参考价格: {short_pos['entry_price']:.2f}")

                # 设置最后再平衡时间为当前时间
                self.band_limited_strategy.state["last_rebalance_ts"] = time.time()

                logger.info("[Band-Limited] 持仓状态已恢复，将继续运行策略")
            else:
                logger.info("[Band-Limited] 未检测到现有持仓，将在首次分析时建立双向持仓")
        except Exception as e:
            logger.error(f"恢复持仓状态失败: {e}")
            logger.warning("[Band-Limited] 将跳过状态恢复，策略将重新初始化")

    def _load_pending_orders(self):
        """从文件加载累积的待处理订单"""
        try:
            if os.path.exists(self.pending_orders_file):
                with open(self.pending_orders_file, 'r') as f:
                    data = json.load(f)
                    # 验证数据格式
                    if not isinstance(data, dict):
                        raise ValueError("Invalid data format: expected dict")

                    open_orders = data.get("open", {})
                    close_orders = data.get("close", {})

                    # 验证并转换为float
                    if isinstance(open_orders, dict):
                        self.pending_orders["long"] = float(open_orders.get("long", 0.0))
                        self.pending_orders["short"] = float(open_orders.get("short", 0.0))
                    if isinstance(close_orders, dict):
                        self.pending_close_orders["long"] = float(close_orders.get("long", 0.0))
                        self.pending_close_orders["short"] = float(close_orders.get("short", 0.0))

                    if any(v > 0 for v in self.pending_orders.values()) or any(v > 0 for v in self.pending_close_orders.values()):
                        logger.info(f"[Band-Limited] 已加载累积订单: 开仓={self.pending_orders}, 平仓={self.pending_close_orders}")
        except json.JSONDecodeError as e:
            logger.error(f"累积订单文件损坏，将备份并重置: {e}")
            # 备份损坏的文件
            if os.path.exists(self.pending_orders_file):
                backup_file = f"{self.pending_orders_file}.corrupt.{int(time.time())}"
                os.rename(self.pending_orders_file, backup_file)
                logger.info(f"已备份损坏文件到: {backup_file}")
        except Exception as e:
            logger.warning(f"加载累积订单失败: {e}")

    def _save_pending_orders(self):
        """保存累积的待处理订单到文件（原子写入）"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.pending_orders_file), exist_ok=True)
            data = {
                "open": self.pending_orders,
                "close": self.pending_close_orders,
                "updated_at": datetime.now().isoformat()
            }
            # 原子写入：先写临时文件，再重命名
            tmp_file = self.pending_orders_file + ".tmp"
            with open(tmp_file, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_file, self.pending_orders_file)  # 原子操作
        except Exception as e:
            logger.warning(f"保存累积订单失败: {e}")

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

        # 强制刷新数据库缓冲区
        try:
            db.flush_buffers(force=True)
            logger.info("✅ 数据库缓冲区已刷新")
        except Exception as e:
            logger.error(f"刷新数据库缓冲区失败: {e}")

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


def create_trading_engine_demo(run_once: bool = False):
    """
    TradingEngine 集成示例（不影响现有 TradingBot）。

    Args:
        run_once: 是否执行一次引擎周期示例
    """
    from core.engine import TradingEngine
    from core.adapters import (
        StrategyEngineAdapter,
        RiskEngineAdapter,
        ExecutionEngineAdapter,
        MonitoringEngineAdapter,
    )
    from core.trader import BitgetTrader

    # 使用现有模块构建四层适配器
    trader = BitgetTrader()
    risk_manager = trader.risk_manager

    strategy_engine = StrategyEngineAdapter(config.ENABLE_STRATEGIES)
    risk_engine = RiskEngineAdapter(risk_manager)
    execution_engine = ExecutionEngineAdapter(trader)
    monitoring_engine = MonitoringEngineAdapter()

    engine = TradingEngine(
        strategy_engine=strategy_engine,
        risk_engine=risk_engine,
        execution_engine=execution_engine,
        monitoring_engine=monitoring_engine,
    )

    if run_once:
        df = trader.get_klines()
        if df is not None and not df.empty:
            engine.start()
            engine.run_cycle(df)
            engine.stop()

    return engine


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
