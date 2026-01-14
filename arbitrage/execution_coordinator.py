"""
执行协调器 - 原子化双腿套利执行和回滚机制
"""
import time
from typing import Dict, Optional, Tuple
from datetime import datetime

from utils.logger_utils import get_logger
from exchange.manager import ExchangeManager
from exchange.interface import OrderResult
from .models import ArbitrageOpportunity, ArbitrageTrade, TradeStatus

logger = get_logger("execution_coordinator")


class ExecutionCoordinator:
    """套利执行协调器 - 负责原子化双腿执行"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化执行协调器

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 执行配置
        self.max_execution_time_per_leg = config.get("max_execution_time_per_leg", 10)
        self.max_total_execution_time = config.get("max_total_execution_time", 30)
        self.max_slippage_tolerance = config.get("max_slippage_tolerance", 0.2)
        self.enable_atomic_execution = config.get("enable_atomic_execution", True)

        logger.info(f"执行协调器初始化: atomic={self.enable_atomic_execution}, "
                   f"max_time_per_leg={self.max_execution_time_per_leg}s")

    def execute_arbitrage(self, opportunity: ArbitrageOpportunity,
                         amount: float) -> ArbitrageTrade:
        """
        执行套利交易（原子化双腿执行）

        状态机:
        PENDING → EXECUTING_BUY → EXECUTING_SELL → COMPLETED/FAILED

        Args:
            opportunity: 套利机会
            amount: 交易金额(USDT)

        Returns:
            套利交易记录
        """
        trade = ArbitrageTrade(
            opportunity=opportunity,
            status=TradeStatus.PENDING,
            amount=amount,
            expected_pnl=opportunity.net_profit
        )

        start_time = time.time()

        try:
            logger.info(f"开始执行套利: {opportunity.buy_exchange}->{opportunity.sell_exchange}, "
                       f"amount={amount:.2f}, expected_pnl={opportunity.net_profit:.4f}")

            # 阶段1: 执行买腿
            trade.status = TradeStatus.EXECUTING_BUY
            buy_success, buy_order = self._execute_buy_leg(opportunity, amount)
            trade.buy_order = buy_order
            trade.buy_executed_at = datetime.now()

            if not buy_success:
                trade.status = TradeStatus.FAILED
                trade.failure_reason = f"买腿失败: {buy_order.error if buy_order else 'unknown'}"
                trade.completed_at = datetime.now()
                trade.calculate_execution_time()
                logger.error(f"套利失败 - 买腿失败: {trade.failure_reason}")
                return trade

            logger.info(f"买腿执行成功: {opportunity.buy_exchange}, "
                       f"order_id={buy_order.order_id}, price={buy_order.avg_price:.2f}")

            # 阶段2: 执行卖腿
            trade.status = TradeStatus.EXECUTING_SELL
            sell_success, sell_order = self._execute_sell_leg(opportunity, amount)
            trade.sell_order = sell_order
            trade.sell_executed_at = datetime.now()

            if not sell_success:
                # 卖腿失败 - 需要回滚买腿
                if self.enable_atomic_execution:
                    trade.status = TradeStatus.ROLLING_BACK
                    logger.warning(f"卖腿失败，开始回滚买腿: {sell_order.error if sell_order else 'unknown'}")
                    self._rollback_buy_position(opportunity, buy_order, amount)

                trade.status = TradeStatus.FAILED
                trade.failure_reason = f"卖腿失败: {sell_order.error if sell_order else 'unknown'}"
                trade.completed_at = datetime.now()
                trade.calculate_execution_time()
                logger.error(f"套利失败 - 卖腿失败: {trade.failure_reason}")
                return trade

            logger.info(f"卖腿执行成功: {opportunity.sell_exchange}, "
                       f"order_id={sell_order.order_id}, price={sell_order.avg_price:.2f}")

            # 成功: 计算实际盈亏
            trade.status = TradeStatus.COMPLETED
            trade.actual_pnl = self._calculate_actual_pnl(buy_order, sell_order, amount)
            trade.completed_at = datetime.now()
            trade.calculate_execution_time()

            execution_time = time.time() - start_time
            logger.info(f"套利执行成功: actual_pnl={trade.actual_pnl:.4f}, "
                       f"execution_time={execution_time:.2f}s")

            return trade

        except Exception as e:
            # 紧急异常处理
            trade.status = TradeStatus.FAILED
            trade.failure_reason = f"执行异常: {str(e)}"
            trade.completed_at = datetime.now()
            trade.calculate_execution_time()
            logger.error(f"套利执行异常: {e}", exc_info=True)

            # 尝试紧急回滚
            if trade.buy_order and trade.buy_order.success and self.enable_atomic_execution:
                try:
                    logger.warning("尝试紧急回滚买腿")
                    self._rollback_buy_position(opportunity, trade.buy_order, amount)
                except Exception as rollback_error:
                    logger.error(f"紧急回滚失败: {rollback_error}", exc_info=True)

            return trade

    def _execute_buy_leg(self, opportunity: ArbitrageOpportunity,
                        amount: float) -> Tuple[bool, Optional[OrderResult]]:
        """
        执行买腿

        Args:
            opportunity: 套利机会
            amount: 交易金额(USDT)

        Returns:
            (是否成功, 订单结果)
        """
        try:
            exchange = self.exchange_manager.get_exchange(opportunity.buy_exchange)
            symbol = opportunity.symbol

            # 计算买入数量 (amount / price)
            quantity = amount / opportunity.buy_price

            logger.info(f"执行买腿: {opportunity.buy_exchange}, symbol={symbol}, "
                       f"quantity={quantity:.6f}, price={opportunity.buy_price:.2f}")

            # 执行市价买单
            order_result = exchange.place_order(
                symbol=symbol,
                side="buy",
                order_type="market",
                quantity=quantity
            )

            if not order_result or not order_result.success:
                logger.error(f"买腿下单失败: {order_result.error if order_result else 'unknown'}")
                return False, order_result

            # 监控订单执行
            final_order = self._monitor_order(exchange, order_result.order_id, symbol)

            if not final_order or not final_order.success:
                logger.error(f"买腿执行失败: {final_order.error if final_order else 'timeout'}")
                return False, final_order

            return True, final_order

        except Exception as e:
            logger.error(f"买腿执行异常: {e}", exc_info=True)
            return False, None

    def _execute_sell_leg(self, opportunity: ArbitrageOpportunity,
                         amount: float) -> Tuple[bool, Optional[OrderResult]]:
        """
        执行卖腿

        Args:
            opportunity: 套利机会
            amount: 交易金额(USDT)

        Returns:
            (是否成功, 订单结果)
        """
        try:
            exchange = self.exchange_manager.get_exchange(opportunity.sell_exchange)
            symbol = opportunity.symbol

            # 计算卖出数量 (amount / price)
            quantity = amount / opportunity.sell_price

            logger.info(f"执行卖腿: {opportunity.sell_exchange}, symbol={symbol}, "
                       f"quantity={quantity:.6f}, price={opportunity.sell_price:.2f}")

            # 执行市价卖单
            order_result = exchange.place_order(
                symbol=symbol,
                side="sell",
                order_type="market",
                quantity=quantity
            )

            if not order_result or not order_result.success:
                logger.error(f"卖腿下单失败: {order_result.error if order_result else 'unknown'}")
                return False, order_result

            # 监控订单执行
            final_order = self._monitor_order(exchange, order_result.order_id, symbol)

            if not final_order or not final_order.success:
                logger.error(f"卖腿执行失败: {final_order.error if final_order else 'timeout'}")
                return False, final_order

            return True, final_order

        except Exception as e:
            logger.error(f"卖腿执行异常: {e}", exc_info=True)
            return False, None

    def _rollback_buy_position(self, opportunity: ArbitrageOpportunity,
                               buy_order: OrderResult, amount: float):
        """
        回滚买入仓位（卖出已买入的币）

        Args:
            opportunity: 套利机会
            buy_order: 买入订单结果
            amount: 交易金额
        """
        try:
            exchange = self.exchange_manager.get_exchange(opportunity.buy_exchange)
            symbol = opportunity.symbol

            # 计算回滚数量（使用实际成交数量）
            quantity = buy_order.filled_quantity if buy_order.filled_quantity else amount / buy_order.avg_price

            logger.warning(f"开始回滚买入仓位: {opportunity.buy_exchange}, "
                          f"symbol={symbol}, quantity={quantity:.6f}")

            # 执行市价卖单平仓
            rollback_order = exchange.place_order(
                symbol=symbol,
                side="sell",
                order_type="market",
                quantity=quantity
            )

            if rollback_order and rollback_order.success:
                logger.info(f"回滚成功: order_id={rollback_order.order_id}")
            else:
                logger.error(f"回滚失败: {rollback_order.error if rollback_order else 'unknown'}")

        except Exception as e:
            logger.error(f"回滚异常: {e}", exc_info=True)

    def _monitor_order(self, exchange, order_id: str, symbol: str,
                      timeout: Optional[float] = None) -> Optional[OrderResult]:
        """
        监控订单执行状态

        Args:
            exchange: 交易所实例
            order_id: 订单ID
            symbol: 交易对
            timeout: 超时时间（秒）

        Returns:
            最终订单结果
        """
        if timeout is None:
            timeout = self.max_execution_time_per_leg

        start_time = time.time()
        check_interval = 0.5  # 每0.5秒检查一次

        try:
            while time.time() - start_time < timeout:
                # 查询订单状态
                order_status = exchange.get_order_status(order_id, symbol)

                if not order_status:
                    logger.warning(f"无法获取订单状态: {order_id}")
                    time.sleep(check_interval)
                    continue

                # 检查订单是否完成
                if order_status.success and order_status.filled_quantity > 0:
                    elapsed = time.time() - start_time
                    logger.info(f"订单执行完成: {order_id}, elapsed={elapsed:.2f}s")
                    return order_status

                # 检查订单是否失败
                if order_status.error:
                    logger.error(f"订单执行失败: {order_id}, error={order_status.error}")
                    return order_status

                time.sleep(check_interval)

            # 超时
            logger.error(f"订单监控超时: {order_id}, timeout={timeout}s")
            return None

        except Exception as e:
            logger.error(f"订单监控异常: {e}", exc_info=True)
            return None

    def _calculate_actual_pnl(self, buy_order: OrderResult, sell_order: OrderResult,
                             amount: float) -> float:
        """
        计算实际盈亏

        Args:
            buy_order: 买入订单结果
            sell_order: 卖出订单结果
            amount: 交易金额

        Returns:
            实际盈亏(USDT)
        """
        try:
            # 买入成本 = 平均买入价 * 数量
            buy_cost = buy_order.avg_price * buy_order.filled_quantity

            # 卖出收入 = 平均卖出价 * 数量
            sell_revenue = sell_order.avg_price * sell_order.filled_quantity

            # 买入手续费
            buy_fee = buy_order.fee if buy_order.fee else buy_cost * 0.0006

            # 卖出手续费
            sell_fee = sell_order.fee if sell_order.fee else sell_revenue * 0.0006

            # 实际盈亏 = 卖出收入 - 买入成本 - 手续费
            actual_pnl = sell_revenue - buy_cost - buy_fee - sell_fee

            logger.debug(f"PnL计算: buy_cost={buy_cost:.4f}, sell_revenue={sell_revenue:.4f}, "
                        f"fees={buy_fee + sell_fee:.4f}, pnl={actual_pnl:.4f}")

            return actual_pnl

        except Exception as e:
            logger.error(f"PnL计算异常: {e}", exc_info=True)
            return 0.0

