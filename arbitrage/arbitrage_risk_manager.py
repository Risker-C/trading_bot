"""
套利风险管理器 - 仓位限制、频率限制、健康检查
"""
import time
from typing import Dict, Tuple, Optional
from collections import deque
from datetime import datetime, timedelta

from utils.logger_utils import get_logger
from exchange.manager import ExchangeManager
from .models import ArbitrageOpportunity

logger = get_logger("arbitrage_risk_manager")


class ArbitrageRiskManager:
    """套利风险管理器"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化风险管理器

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 仓位限制配置
        self.max_position_per_exchange = config.get("max_position_per_exchange", 500)  # USDT
        self.max_total_exposure = config.get("max_total_exposure", 1000)  # USDT
        self.max_position_count_per_exchange = config.get("max_position_count_per_exchange", 3)

        # 频率限制配置
        self.max_arbitrage_per_hour = config.get("max_arbitrage_per_hour", 10)
        self.max_arbitrage_per_day = config.get("max_arbitrage_per_day", 50)
        self.min_interval_between_arbitrage = config.get("min_interval_between_arbitrage", 30)  # 秒

        # 盈利阈值配置
        self.min_spread_threshold = config.get("min_spread_threshold", 0.3)  # %
        self.min_net_profit_threshold = config.get("min_net_profit_threshold", 1.0)  # USDT
        self.min_profit_ratio = config.get("min_profit_ratio", 0.5)

        # 订单簿深度配置
        self.min_orderbook_depth_multiplier = config.get("min_orderbook_depth_multiplier", 3.0)
        self.min_orderbook_depth_usdt = config.get("min_orderbook_depth_usdt", 5000)

        # 交易所健康配置
        self.max_api_latency_ms = config.get("max_api_latency_ms", 500)

        # 运行时状态
        self.position_tracker: Dict[str, float] = {}  # 交易所 -> 持仓金额
        self.position_count: Dict[str, int] = {}  # 交易所 -> 持仓数量
        self.arbitrage_history: deque = deque(maxlen=100)  # 套利历史
        self.last_arbitrage_time: Optional[float] = None

        logger.info(f"风险管理器初始化: max_position={self.max_position_per_exchange}, "
                   f"max_exposure={self.max_total_exposure}")

    def can_execute_arbitrage(self, opportunity: ArbitrageOpportunity,
                             amount: float) -> Tuple[bool, str]:
        """
        执行前的综合风险检查

        Args:
            opportunity: 套利机会
            amount: 交易金额

        Returns:
            (是否可以执行, 原因)
        """
        # 1. 仓位限制检查
        can_position, reason = self._check_position_limits(opportunity, amount)
        if not can_position:
            return False, f"仓位限制: {reason}"

        # 2. 频率限制检查
        can_frequency, reason = self._check_frequency_limits()
        if not can_frequency:
            return False, f"频率限制: {reason}"

        # 3. 盈利能力检查
        can_profit, reason = self._check_profitability(opportunity, amount)
        if not can_profit:
            return False, f"盈利能力: {reason}"

        # 4. 订单簿深度检查
        can_depth, reason = self._check_orderbook_depth(opportunity, amount)
        if not can_depth:
            return False, f"订单簿深度: {reason}"

        # 5. 交易所健康检查
        can_health, reason = self._check_exchange_health(opportunity)
        if not can_health:
            return False, f"交易所健康: {reason}"

        # 6. 余额检查
        can_balance, reason = self._check_balances(opportunity, amount)
        if not can_balance:
            return False, f"余额: {reason}"

        return True, "所有检查通过"

    def _check_position_limits(self, opportunity: ArbitrageOpportunity,
                               amount: float) -> Tuple[bool, str]:
        """检查仓位限制"""
        buy_exchange = opportunity.buy_exchange
        sell_exchange = opportunity.sell_exchange

        # 检查单交易所仓位限制
        buy_position = self.position_tracker.get(buy_exchange, 0)
        if buy_position + amount > self.max_position_per_exchange:
            return False, f"{buy_exchange}仓位超限 ({buy_position + amount:.2f} > {self.max_position_per_exchange})"

        sell_position = self.position_tracker.get(sell_exchange, 0)
        if sell_position + amount > self.max_position_per_exchange:
            return False, f"{sell_exchange}仓位超限 ({sell_position + amount:.2f} > {self.max_position_per_exchange})"

        # 检查总敞口限制
        total_exposure = sum(self.position_tracker.values()) + amount * 2
        if total_exposure > self.max_total_exposure:
            return False, f"总敞口超限 ({total_exposure:.2f} > {self.max_total_exposure})"

        # 检查持仓数量限制
        buy_count = self.position_count.get(buy_exchange, 0)
        if buy_count >= self.max_position_count_per_exchange:
            return False, f"{buy_exchange}持仓数量超限 ({buy_count} >= {self.max_position_count_per_exchange})"

        sell_count = self.position_count.get(sell_exchange, 0)
        if sell_count >= self.max_position_count_per_exchange:
            return False, f"{sell_exchange}持仓数量超限 ({sell_count} >= {self.max_position_count_per_exchange})"

        return True, "仓位检查通过"

    def _check_frequency_limits(self) -> Tuple[bool, str]:
        """检查频率限制"""
        now = time.time()

        # 检查最小间隔
        if self.last_arbitrage_time:
            elapsed = now - self.last_arbitrage_time
            if elapsed < self.min_interval_between_arbitrage:
                return False, f"间隔不足 ({elapsed:.1f}s < {self.min_interval_between_arbitrage}s)"

        # 检查每小时限制
        one_hour_ago = now - 3600
        recent_hour = [t for t in self.arbitrage_history if t > one_hour_ago]
        if len(recent_hour) >= self.max_arbitrage_per_hour:
            return False, f"每小时限制 ({len(recent_hour)} >= {self.max_arbitrage_per_hour})"

        # 检查每日限制
        one_day_ago = now - 86400
        recent_day = [t for t in self.arbitrage_history if t > one_day_ago]
        if len(recent_day) >= self.max_arbitrage_per_day:
            return False, f"每日限制 ({len(recent_day)} >= {self.max_arbitrage_per_day})"

        return True, "频率检查通过"

    def _check_profitability(self, opportunity: ArbitrageOpportunity,
                            amount: float) -> Tuple[bool, str]:
        """检查盈利能力"""
        # 检查价差
        if opportunity.spread_pct < self.min_spread_threshold:
            return False, f"价差不足 ({opportunity.spread_pct:.3f}% < {self.min_spread_threshold}%)"

        # 检查净利润
        if opportunity.net_profit < self.min_net_profit_threshold:
            return False, f"净利润不足 ({opportunity.net_profit:.2f} < {self.min_net_profit_threshold})"

        # 检查利润比例
        profit_ratio = opportunity.net_profit / opportunity.gross_profit if opportunity.gross_profit > 0 else 0
        if profit_ratio < self.min_profit_ratio:
            return False, f"利润比例不足 ({profit_ratio:.2f} < {self.min_profit_ratio})"

        return True, "盈利检查通过"

    def _check_orderbook_depth(self, opportunity: ArbitrageOpportunity,
                               amount: float) -> Tuple[bool, str]:
        """检查订单簿深度"""
        # 检查买入交易所深度
        if opportunity.buy_orderbook_depth:
            if opportunity.buy_orderbook_depth < self.min_orderbook_depth_usdt:
                return False, f"{opportunity.buy_exchange}深度不足 ({opportunity.buy_orderbook_depth:.0f} < {self.min_orderbook_depth_usdt})"

            required_depth = amount * self.min_orderbook_depth_multiplier
            if opportunity.buy_orderbook_depth < required_depth:
                return False, f"{opportunity.buy_exchange}深度不足 ({opportunity.buy_orderbook_depth:.0f} < {required_depth:.0f})"

        # 检查卖出交易所深度
        if opportunity.sell_orderbook_depth:
            if opportunity.sell_orderbook_depth < self.min_orderbook_depth_usdt:
                return False, f"{opportunity.sell_exchange}深度不足 ({opportunity.sell_orderbook_depth:.0f} < {self.min_orderbook_depth_usdt})"

            required_depth = amount * self.min_orderbook_depth_multiplier
            if opportunity.sell_orderbook_depth < required_depth:
                return False, f"{opportunity.sell_exchange}深度不足 ({opportunity.sell_orderbook_depth:.0f} < {required_depth:.0f})"

        return True, "深度检查通过"

    def _check_exchange_health(self, opportunity: ArbitrageOpportunity) -> Tuple[bool, str]:
        """检查交易所健康状态"""
        # 简化实现: 检查交易所是否连接
        try:
            buy_exchange = self.exchange_manager.get_exchange(opportunity.buy_exchange)
            if not buy_exchange.is_connected():
                return False, f"{opportunity.buy_exchange}未连接"

            sell_exchange = self.exchange_manager.get_exchange(opportunity.sell_exchange)
            if not sell_exchange.is_connected():
                return False, f"{opportunity.sell_exchange}未连接"

            return True, "健康检查通过"

        except Exception as e:
            return False, f"健康检查失败: {e}"

    def _check_balances(self, opportunity: ArbitrageOpportunity,
                       amount: float) -> Tuple[bool, str]:
        """检查余额"""
        try:
            # 检查买入交易所余额
            buy_exchange = self.exchange_manager.get_exchange(opportunity.buy_exchange)
            buy_balance = buy_exchange.get_balance()

            if buy_balance < amount:
                return False, f"{opportunity.buy_exchange}余额不足 ({buy_balance:.2f} < {amount:.2f})"

            # 检查卖出交易所余额 (需要有足够的币)
            # 简化: 假设卖出交易所也需要有USDT余额
            sell_exchange = self.exchange_manager.get_exchange(opportunity.sell_exchange)
            sell_balance = sell_exchange.get_balance()

            if sell_balance < amount:
                return False, f"{opportunity.sell_exchange}余额不足 ({sell_balance:.2f} < {amount:.2f})"

            return True, "余额检查通过"

        except Exception as e:
            return False, f"余额检查失败: {e}"

    def record_arbitrage_start(self, opportunity: ArbitrageOpportunity, amount: float):
        """记录套利开始"""
        now = time.time()
        self.arbitrage_history.append(now)
        self.last_arbitrage_time = now

        # 更新仓位追踪
        buy_exchange = opportunity.buy_exchange
        sell_exchange = opportunity.sell_exchange

        self.position_tracker[buy_exchange] = self.position_tracker.get(buy_exchange, 0) + amount
        self.position_tracker[sell_exchange] = self.position_tracker.get(sell_exchange, 0) + amount

        self.position_count[buy_exchange] = self.position_count.get(buy_exchange, 0) + 1
        self.position_count[sell_exchange] = self.position_count.get(sell_exchange, 0) + 1

        logger.info(f"记录套利开始: {buy_exchange}->{sell_exchange}, amount={amount:.2f}")

    def record_arbitrage_complete(self, opportunity: ArbitrageOpportunity, amount: float):
        """记录套利完成"""
        buy_exchange = opportunity.buy_exchange
        sell_exchange = opportunity.sell_exchange

        # 更新仓位追踪
        self.position_tracker[buy_exchange] = max(0, self.position_tracker.get(buy_exchange, 0) - amount)
        self.position_tracker[sell_exchange] = max(0, self.position_tracker.get(sell_exchange, 0) - amount)

        self.position_count[buy_exchange] = max(0, self.position_count.get(buy_exchange, 0) - 1)
        self.position_count[sell_exchange] = max(0, self.position_count.get(sell_exchange, 0) - 1)

        logger.info(f"记录套利完成: {buy_exchange}->{sell_exchange}, amount={amount:.2f}")

    def get_risk_report(self) -> Dict:
        """获取风险报告"""
        now = time.time()
        one_hour_ago = now - 3600
        one_day_ago = now - 86400

        recent_hour = [t for t in self.arbitrage_history if t > one_hour_ago]
        recent_day = [t for t in self.arbitrage_history if t > one_day_ago]

        return {
            "position_tracker": dict(self.position_tracker),
            "position_count": dict(self.position_count),
            "total_exposure": sum(self.position_tracker.values()),
            "arbitrage_count_hour": len(recent_hour),
            "arbitrage_count_day": len(recent_day),
            "last_arbitrage_time": self.last_arbitrage_time,
        }
