"""
套利引擎 - 主协调器，整合所有套利组件
"""
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime

from logger_utils import get_logger, db
from exchange.manager import ExchangeManager
from .spread_monitor import SpreadMonitor
from .opportunity_detector import OpportunityDetector
from .arbitrage_risk_manager import ArbitrageRiskManager
from .execution_coordinator import ExecutionCoordinator
from .position_tracker import CrossExchangePositionTracker
from .models import SpreadData, ArbitrageOpportunity, ArbitrageTrade, TradeStatus

logger = get_logger("arbitrage_engine")


class ArbitrageEngine:
    """套利引擎 - 主协调器"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化套利引擎

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 初始化各个组件
        logger.info("初始化套利引擎组件...")

        self.spread_monitor = SpreadMonitor(exchange_manager, config)
        self.opportunity_detector = OpportunityDetector(exchange_manager, config)
        self.risk_manager = ArbitrageRiskManager(exchange_manager, config)
        self.execution_coordinator = ExecutionCoordinator(exchange_manager, config)
        self.position_tracker = CrossExchangePositionTracker(exchange_manager, config)

        # 运行状态
        self.running = False
        self.paused = False
        self.engine_thread: Optional[threading.Thread] = None

        # 配置参数
        self.opportunity_scan_interval = config.get("opportunity_scan_interval", 2)
        self.arbitrage_position_size = config.get("arbitrage_position_size", 100)

        # 统计信息
        self.stats = {
            "total_opportunities": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_pnl": 0.0,
            "start_time": None
        }

        logger.info(f"套利引擎初始化完成: scan_interval={self.opportunity_scan_interval}s, "
                   f"position_size={self.arbitrage_position_size}")

    def start(self):
        """启动套利引擎"""
        if self.running:
            logger.warning("套利引擎已在运行")
            return

        logger.info("启动套利引擎...")
        self.running = True
        self.paused = False
        self.stats["start_time"] = datetime.now()

        # 启动价差监控
        self.spread_monitor.start()

        # 启动主引擎线程
        self.engine_thread = threading.Thread(target=self._engine_loop, daemon=True)
        self.engine_thread.start()

        logger.info("✅ 套利引擎已启动")

    def stop(self):
        """停止套利引擎"""
        if not self.running:
            logger.warning("套利引擎未运行")
            return

        logger.info("停止套利引擎...")
        self.running = False

        # 停止价差监控
        self.spread_monitor.stop()

        # 等待引擎线程结束
        if self.engine_thread:
            self.engine_thread.join(timeout=10)

        logger.info("✅ 套利引擎已停止")

    def pause(self):
        """暂停套利引擎"""
        if not self.running:
            logger.warning("套利引擎未运行")
            return

        self.paused = True
        logger.info("⏸️ 套利引擎已暂停")

    def resume(self):
        """恢复套利引擎"""
        if not self.running:
            logger.warning("套利引擎未运行")
            return

        self.paused = False
        logger.info("▶️ 套利引擎已恢复")

    def is_running(self) -> bool:
        """检查引擎是否运行中"""
        return self.running and not self.paused

    def _engine_loop(self):
        """主引擎循环"""
        logger.info("套利引擎主循环开始")

        while self.running:
            try:
                # 检查是否暂停
                if self.paused:
                    time.sleep(1)
                    continue

                # 步骤1: 获取最新价差
                spreads = self.spread_monitor.get_latest_spreads()
                if not spreads:
                    logger.debug("未获取到价差数据")
                    time.sleep(self.opportunity_scan_interval)
                    continue

                # 步骤2: 检测套利机会
                opportunities = self.opportunity_detector.detect_opportunities(
                    spreads,
                    test_amount=self.arbitrage_position_size
                )

                if opportunities:
                    self.stats["total_opportunities"] += len(opportunities)
                    logger.info(f"检测到 {len(opportunities)} 个套利机会")

                    # 记录机会到数据库
                    self._record_opportunities(opportunities)

                    # 步骤3: 处理最佳机会
                    best_opportunity = opportunities[0]
                    logger.info(f"最佳机会: {best_opportunity}")

                    # 步骤4: 风险验证
                    can_execute, reason = self.risk_manager.can_execute_arbitrage(
                        best_opportunity,
                        self.arbitrage_position_size
                    )

                    if can_execute:
                        # 步骤5: 执行套利
                        self._execute_arbitrage_opportunity(best_opportunity)
                    else:
                        logger.info(f"机会被风险管理器拒绝: {reason}")

                # 等待下一次扫描
                time.sleep(self.opportunity_scan_interval)

            except Exception as e:
                logger.error(f"引擎循环异常: {e}", exc_info=True)
                time.sleep(self.opportunity_scan_interval)

        logger.info("套利引擎主循环结束")

    def _execute_arbitrage_opportunity(self, opportunity: ArbitrageOpportunity):
        """
        执行套利机会

        Args:
            opportunity: 套利机会
        """
        try:
            logger.info(f"开始执行套利: {opportunity.buy_exchange}->{opportunity.sell_exchange}")

            # 记录套利开始
            self.risk_manager.record_arbitrage_start(opportunity, self.arbitrage_position_size)

            # 执行套利
            trade = self.execution_coordinator.execute_arbitrage(
                opportunity,
                self.arbitrage_position_size
            )

            # 更新统计
            self.stats["total_executions"] += 1
            if trade.is_completed():
                self.stats["successful_executions"] += 1
                self.stats["total_pnl"] += trade.actual_pnl or 0.0
                logger.info(f"✅ 套利执行成功: pnl={trade.actual_pnl:.4f}")

                # 记录套利完成
                self.risk_manager.record_arbitrage_complete(opportunity, self.arbitrage_position_size)
            else:
                self.stats["failed_executions"] += 1
                logger.error(f"❌ 套利执行失败: {trade.failure_reason}")

            # 更新持仓追踪
            if trade.buy_order and trade.buy_order.success:
                self.position_tracker.update_position(
                    opportunity.buy_exchange,
                    opportunity.symbol,
                    trade.buy_order.filled_quantity,
                    "buy"
                )

            if trade.sell_order and trade.sell_order.success:
                self.position_tracker.update_position(
                    opportunity.sell_exchange,
                    opportunity.symbol,
                    trade.sell_order.filled_quantity,
                    "sell"
                )

            # 记录交易到数据库
            self._record_trade(trade)

        except Exception as e:
            logger.error(f"执行套利机会异常: {e}", exc_info=True)

    def _record_opportunities(self, opportunities: List[ArbitrageOpportunity]):
        """
        记录套利机会到数据库

        Args:
            opportunities: 套利机会列表
        """
        try:
            conn = db._get_conn()
            cursor = conn.cursor()

            for opp in opportunities:
                cursor.execute("""
                    INSERT INTO arbitrage_opportunities (
                        buy_exchange, sell_exchange, symbol,
                        buy_price, sell_price, spread_pct,
                        gross_profit, net_profit,
                        buy_exchange_fee, sell_exchange_fee,
                        estimated_buy_slippage, estimated_sell_slippage,
                        buy_orderbook_depth, sell_orderbook_depth,
                        risk_score, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    opp.buy_exchange, opp.sell_exchange, opp.symbol,
                    opp.buy_price, opp.sell_price, opp.spread_pct,
                    opp.gross_profit, opp.net_profit,
                    opp.buy_exchange_fee, opp.sell_exchange_fee,
                    opp.estimated_buy_slippage, opp.estimated_sell_slippage,
                    opp.buy_orderbook_depth, opp.sell_orderbook_depth,
                    opp.risk_score, opp.timestamp
                ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"记录套利机会失败: {e}", exc_info=True)

    def _record_trade(self, trade: ArbitrageTrade):
        """
        记录套利交易到数据库

        Args:
            trade: 套利交易记录
        """
        try:
            conn = db._get_conn()
            cursor = conn.cursor()

            opp = trade.opportunity

            cursor.execute("""
                INSERT INTO arbitrage_trades (
                    buy_exchange, sell_exchange, symbol, amount, status,
                    buy_order_id, sell_order_id,
                    buy_price, sell_price,
                    expected_pnl, actual_pnl, failure_reason,
                    buy_execution_time, sell_execution_time, total_execution_time,
                    buy_executed_at, sell_executed_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp.buy_exchange, opp.sell_exchange, opp.symbol, trade.amount, trade.status,
                trade.buy_order.order_id if trade.buy_order else None,
                trade.sell_order.order_id if trade.sell_order else None,
                trade.buy_order.avg_price if trade.buy_order else None,
                trade.sell_order.avg_price if trade.sell_order else None,
                trade.expected_pnl, trade.actual_pnl, trade.failure_reason,
                trade.buy_execution_time, trade.sell_execution_time, trade.total_execution_time,
                trade.buy_executed_at, trade.sell_executed_at, trade.completed_at
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"记录套利交易失败: {e}", exc_info=True)

    def get_stats(self) -> Dict:
        """
        获取引擎统计信息

        Returns:
            统计信息字典
        """
        stats = dict(self.stats)

        # 计算运行时间
        if stats["start_time"]:
            runtime = datetime.now() - stats["start_time"]
            stats["runtime_seconds"] = runtime.total_seconds()
            stats["runtime_str"] = str(runtime).split('.')[0]

        # 计算成功率
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successful_executions"] / stats["total_executions"]
        else:
            stats["success_rate"] = 0.0

        # 添加风险管理器报告
        stats["risk_report"] = self.risk_manager.get_risk_report()

        # 添加持仓报告
        stats["position_report"] = self.position_tracker.get_position_report()

        return stats

    def get_status(self) -> Dict:
        """
        获取引擎状态

        Returns:
            状态字典
        """
        return {
            "running": self.running,
            "paused": self.paused,
            "is_active": self.is_running(),
            "stats": self.get_stats()
        }
